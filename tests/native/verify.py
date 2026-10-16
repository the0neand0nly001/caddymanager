"""Verify installed native files, real sudo/Caddy operations and update persistence."""

import hashlib
import http.client
import http.cookiejar
import json
from pathlib import Path
import re
import socket
import ssl
import subprocess
import sys
import time
import urllib.parse
import urllib.request

phase = sys.argv[1]
root = Path("/opt/caddy-manager")
opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
)


def request(path, fields=None):
    time.sleep(0.2)
    body = urllib.parse.urlencode(fields).encode() if fields is not None else None
    return opener.open("http://127.0.0.1:5000" + path, data=body, timeout=15).read()


def csrf(page):
    return re.search(rb'name="csrf_token"\s+value="([^"]+)"', page).group(1).decode()


login = request("/login")
page = request(
    "/login",
    {
        "username": "native-test-owner",
        "password": "test'quoted-password",
        "csrf_token": csrf(login),
    },
)
assert b"Sign Out" in page
token = csrf(page)
assert json.loads(request("/api/overview"))["caddy"]["state"] == "active"

if phase == "install":
    page = request(
        "/",
        {
            "action": "add_domain",
            "domain": "native.test",
            "tls_mode": "http",
            "csrf_token": token,
        },
    )
    assert b"Added base domain" in page
    page = request(
        "/",
        {
            "action": "add",
            "name": "native-check",
            "base_domain": "home.lab",
            "ip": "127.0.0.1",
            "port": "5000",
            "protocol": "http",
            "csrf_token": token,
        },
    )
    assert b"Successfully added and reloaded route" in page
    subprocess.run(
        [
            "runuser",
            "-u",
            "caddyman",
            "--",
            "sudo",
            "-n",
            "/usr/bin/caddy",
            "validate",
            "--config",
            "/etc/caddy/Caddyfile",
        ],
        check=True,
        capture_output=True,
    )

certificate = request("/download-ca").decode()
assert "BEGIN CERTIFICATE" in certificate
context = ssl.create_default_context(cadata=certificate)
connection = http.client.HTTPConnection("127.0.0.1", 443, timeout=10)
connection.sock = context.wrap_socket(
    socket.create_connection(("127.0.0.1", 443), timeout=10),
    server_hostname="native-check.home.lab",
)
connection.request("GET", "/login", headers={"Host": "native-check.home.lab"})
response = connection.getresponse()
assert response.status == 200 and b"Caddy Manager" in response.read()
connection.close()
assert json.loads(request("/api/activity"))["entries"]
assert (root / ".credentials").stat().st_mode & 0o777 == 0o600
assert (root / "config.yml").stat().st_uid != 0

paths = [
    root / "config.yml",
    root / ".credentials",
    Path("/etc/caddy/Caddyfile"),
    Path("/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt"),
]
fingerprints = {
    str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
}
state_file = Path("/tmp/native-test-fingerprints.json")
if phase == "install":
    state_file.write_text(json.dumps(fingerprints))
else:
    assert fingerprints == json.loads(state_file.read_text())
print(
    f"Native {phase}: quoted-password login, system status, domain persistence, real sudo validation/reload, HTTPS proxy and CA download passed."
)
