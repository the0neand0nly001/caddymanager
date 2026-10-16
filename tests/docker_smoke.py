"""Exercise a local Compose stack with temporary HTTP and HTTPS backends."""

import argparse
import base64
import http.client
import http.cookiejar
import json
from pathlib import Path
import re
import shutil
import socket
import ssl
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]


def command(*args, **kwargs):
    return subprocess.run(
        args, check=True, capture_output=True, text=True, **kwargs
    ).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="caddymanager-preview")
    parser.add_argument(
        "--compose-file", type=Path, default=ROOT / "docker-compose.yml"
    )
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--manager-url", default="http://127.0.0.1:5080")
    parser.add_argument("--proxy-host", default="127.0.0.1")
    parser.add_argument("--proxy-port", default=8443, type=int)
    parser.add_argument("--http-proxy-port", default=8080, type=int)
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin")
    parser.add_argument("--domain", default="home.lab")
    parser.add_argument("--recreate", action="store_true")
    options = parser.parse_args()
    compose = ["docker", "compose", "-p", options.project]
    if options.env_file:
        compose.extend(["--env-file", str(options.env_file.resolve())])
    compose.extend(["-f", str(options.compose_file.resolve())])

    def compose_command(*args):
        return command(*compose, *args, cwd=options.compose_file.resolve().parent)

    def manager_python(source):
        return compose_command(
            "exec", "-T", "manager", "/opt/venv/bin/python", "-c", source
        )

    manager_id = compose_command("ps", "-q", "manager").strip()
    if not manager_id:
        raise RuntimeError("Start the Compose stack before running this check")
    networks = json.loads(
        command(
            "docker",
            "inspect",
            manager_id,
            "--format",
            "{{json .NetworkSettings.Networks}}",
        )
    )
    network = next(iter(networks))
    original = manager_python(
        "from pathlib import Path; import base64; print(base64.b64encode(Path('/etc/caddy/Caddyfile').read_bytes()).decode())"
    ).strip()
    original_config = manager_python(
        "from pathlib import Path; import base64; print(base64.b64encode(Path('/data/config.yml').read_bytes()).decode())"
    ).strip()

    def restore_file(encoded):
        manager_python(
            "from pathlib import Path; import base64; "
            f"Path('/etc/caddy/Caddyfile').write_bytes(base64.b64decode({encoded!r})); "
            "from caddy_manager.backend import reload_caddy; reload_caddy('/etc/caddy/Caddyfile', check=True)"
        )

    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )

    def request(path, fields=None, json_body=None, token=None):
        time.sleep(0.25)
        headers = {}
        data = None
        if fields is not None:
            data = urllib.parse.urlencode(fields).encode()
        if json_body is not None:
            data = json.dumps(json_body).encode()
            headers = {"Content-Type": "application/json", "X-CSRFToken": token}
        with opener.open(
            urllib.request.Request(
                options.manager_url + path, data=data, headers=headers
            ),
            timeout=15,
        ) as response:
            return response.read(), dict(response.headers)

    def token_from(page):
        return re.search(rb'name="csrf_token" value="([^"]+)"', page).group(1).decode()

    def add_route(name, port, protocol):
        page, _ = request(
            "/",
            fields={
                "csrf_token": token,
                "action": "add",
                "name": name,
                "ip": backend_ip,
                "port": port,
                "protocol": protocol,
                "base_domain": options.domain,
            },
        )
        if b"Successfully added and reloaded route" not in page:
            raise AssertionError("Route addition failed")

    def check_proxy(domain):
        context = ssl.create_default_context(cadata=certificate.decode())
        last_error = None
        for _ in range(10):
            try:
                connection = http.client.HTTPConnection(
                    options.proxy_host, options.proxy_port, timeout=10
                )
                raw = socket.create_connection(
                    (options.proxy_host, options.proxy_port), timeout=10
                )
                connection.sock = context.wrap_socket(raw, server_hostname=domain)
                try:
                    connection.request("GET", "/", headers={"Host": domain})
                    response = connection.getresponse()
                    body = response.read()
                    if (
                        response.status == 200
                        and b"Caddy Manager smoke backend" in body
                    ):
                        return
                    last_error = RuntimeError(f"Proxy response: {response.status}")
                finally:
                    connection.close()
            except (OSError, ssl.SSLError) as error:
                last_error = error
            time.sleep(0.5)
        raise AssertionError(f"Proxy check failed: {last_error}")

    def state_fingerprints():
        return json.loads(
            manager_python(
                "import hashlib,json; from pathlib import Path; "
                "paths=['/data/config.yml','/data/.credentials','/data/.flask-secret-key','/etc/caddy/Caddyfile']; "
                "print(json.dumps({p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}))"
            )
        )

    backend_name = options.project + "-smoke-" + uuid.uuid4().hex[:8]
    created = False
    try:
        with tempfile.TemporaryDirectory(prefix="caddymanager-tls-") as temporary:
            temporary = Path(temporary)
            openssl = shutil.which("openssl")
            if not openssl:
                bundled = Path(r"C:\Program Files\Git\usr\bin\openssl.exe")
                openssl = str(bundled) if bundled.exists() else None
            if not openssl:
                raise RuntimeError(
                    "OpenSSL is required to create the temporary HTTPS backend certificate"
                )
            command(
                openssl,
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "1",
                "-subj",
                "/CN=smoke-backend",
                "-keyout",
                str(temporary / "key.pem"),
                "-out",
                str(temporary / "cert.pem"),
            )
            server = """import http.server,ssl,threading
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Caddy Manager smoke backend')
plain=http.server.ThreadingHTTPServer(('0.0.0.0',8081),Handler)
tls=http.server.ThreadingHTTPServer(('0.0.0.0',8444),Handler)
context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain('/certs/cert.pem','/certs/key.pem')
tls.socket=context.wrap_socket(tls.socket,server_side=True)
threading.Thread(target=plain.serve_forever,daemon=True).start()
tls.serve_forever()
"""
            command(
                "docker",
                "run",
                "--rm",
                "-d",
                "--name",
                backend_name,
                "--network",
                network,
                "--mount",
                f"type=bind,source={temporary},target=/certs,readonly",
                "--entrypoint",
                "/usr/bin/python",
                "reg.mini.dev/python:3.13",
                "-c",
                server,
            )
            created = True
            backend_ip = json.loads(
                command(
                    "docker",
                    "inspect",
                    backend_name,
                    "--format",
                    "{{json .NetworkSettings.Networks}}",
                )
            )[network]["IPAddress"]
            login, _ = request("/login")
            page, _ = request(
                "/login",
                fields={
                    "username": options.username,
                    "password": options.password,
                    "csrf_token": token_from(login),
                },
            )
            assert b"Sign Out" in page and b"V2.0.0" in page
            token = token_from(page)
            # A private test domain avoids changing any existing domain defaults.
            options.domain = "smoke-" + uuid.uuid4().hex[:8] + ".test"

            def domain_action(action, mode="internal"):
                result, _ = request(
                    "/",
                    fields={
                        "csrf_token": token,
                        "action": action,
                        "domain": options.domain,
                        "tls_mode": mode,
                    },
                )
                return result

            assert b"Added base domain" in domain_action("add_domain")
            assert b"already exists" in domain_action("add_domain")
            assert b"Updated base domain" in domain_action("update_domain", "http")
            add_route("plain", "8081", "http")

            def check_plain_proxy():
                connection = http.client.HTTPConnection(
                    options.proxy_host, options.http_proxy_port, timeout=10
                )
                try:
                    connection.request(
                        "GET", "/", headers={"Host": "plain." + options.domain}
                    )
                    response = connection.getresponse()
                    assert response.status == 200
                    assert b"Caddy Manager smoke backend" in response.read()
                finally:
                    connection.close()

            check_plain_proxy()
            assert b"Removed base domain" in domain_action("remove_domain")
            check_plain_proxy()
            assert b"Added base domain" in domain_action("add_domain", "auto")
            # Adapt automatic HTTPS offline; do not request public certificates.
            manager_python(
                "from caddy_manager.caddy import build_route_block; "
                "from caddy_manager.config import load_config; "
                "from caddy_manager.domains import domain_tls_mode; "
                "from caddy_manager.backend import request_admin_api; "
                f"mode=domain_tls_mode(load_config(), {options.domain!r}); "
                f"block=build_route_block('auto.' + {options.domain!r}, '192.0.2.1', '80', 'http', mode); "
                "assert mode == 'auto' and 'tls internal' not in block; "
                "request_admin_api('/adapt', block).check_returncode()"
            )
            assert b"Updated base domain" in domain_action("update_domain", "internal")
            print(
                "Base-domain add/update/remove, duplicate rejection and HTTP-only proxying passed; removal preserved the live route."
            )
            metrics, _ = request("/api/metrics")
            assert {"cpu", "ram_mb", "routes"} == set(json.loads(metrics))
            certificate, headers = request("/download-ca")
            assert b"BEGIN CERTIFICATE" in certificate
            assert "caddy-root-ca.crt" in headers["Content-Disposition"]
            name = "smoke" + uuid.uuid4().hex[:8]
            add_route(name, "8081", "http")
            check_proxy(name + "." + options.domain)
            health, _ = request(
                "/api/check-status",
                json_body={"target": backend_ip + ":8081"},
                token=token,
            )
            assert json.loads(health) == {"status": "Online"}
            health, _ = request(
                "/api/check-status",
                json_body={"target": backend_ip + ":1"},
                token=token,
            )
            assert json.loads(health) == {"status": "Down"}
            add_route(name + "down", "1", "http")
            overview_data, _ = request("/api/overview")
            overview_data = json.loads(overview_data)
            assert overview_data["caddy"]["state"] == "responding"
            assert overview_data["totals"]["routes"] == len(overview_data["services"])
            batch, _ = request("/api/services/check", json_body={}, token=token)
            batch = {item["domain"]: item for item in json.loads(batch)["services"]}
            assert batch[name + "." + options.domain]["status"] == "online"
            assert batch[name + "down." + options.domain]["status"] == "down"
            assert batch["localhost"]["status"] == "unconfigured"
            individual, _ = request(
                "/api/services/check",
                json_body={"domain": name + "." + options.domain},
                token=token,
            )
            assert len(json.loads(individual)["services"]) == 1
            activity_data, _ = request("/api/activity")
            activity_data = json.loads(activity_data)
            assert any(
                entry["action"] == "ROUTE_ADDED" and name in entry["details"]
                for entry in activity_data["entries"]
            )
            if activity_data["next_cursor"] is not None:
                older, _ = request(
                    "/api/activity?before=" + str(activity_data["next_cursor"])
                )
                assert json.loads(older)["entries"]
            print(
                "System overview, batch and individual backend health, real unreachable/no-target states and audit-log paging passed."
            )
            page, _ = request(
                "/",
                fields={
                    "csrf_token": token,
                    "action": "remove",
                    "route": name + "." + options.domain,
                },
            )
            assert b"Successfully removed route" in page
            add_route(name, "8081", "http")
            add_route(name + "tls", "8444", "https")
            check_proxy(name + "tls." + options.domain)
            print(
                "Login, metrics, CA download, health checks, HTTP/HTTPS upstreams and HTTP route removal passed."
            )

            good = manager_python(
                "from pathlib import Path; import base64; print(base64.b64encode(Path('/etc/caddy/Caddyfile').read_bytes()).decode())"
            ).strip()
            try:
                result = manager_python(
                    "from pathlib import Path; Path('/etc/caddy/Caddyfile').write_text('invalid { {'); from caddy_manager.backend import reload_caddy; print(reload_caddy('/etc/caddy/Caddyfile').returncode)"
                )
                assert result.strip() == "1"
                check_proxy(name + "." + options.domain)
            finally:
                restore_file(good)
            print("A failed real Caddy reload leaves the running routes available.")

            if options.recreate:
                before = state_fingerprints()
                compose_command(
                    "up", "-d", "--force-recreate", "--wait", "--wait-timeout", "120"
                )
                assert before == state_fingerprints()
                page, _ = request("/")
                assert b"Sign Out" in page
                current_certificate, _ = request("/download-ca")
                assert current_certificate == certificate
                check_proxy(name + "." + options.domain)
                check_proxy(name + "tls." + options.domain)
                check_plain_proxy()
                print(
                    "Recreation preserved configuration, credentials, session, routes and the certificate authority."
                )
    finally:
        try:
            restore_file(original)
        finally:
            try:
                manager_python(
                    "from pathlib import Path; import base64; "
                    f"Path('/data/config.yml').write_bytes(base64.b64decode({original_config!r}))"
                )
            finally:
                if created:
                    command("docker", "rm", "-f", backend_name)
    print(
        "Temporary domains, routes and backend removed; original configuration and Caddyfile restored."
    )


if __name__ == "__main__":
    main()
