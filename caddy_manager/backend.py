"""Caddy validation, reloads and public certificates for each deployment type."""

import json
import os
import subprocess
import urllib.error
import urllib.request


def uses_admin_api():
    return bool(os.environ.get("CADDY_ADMIN_URL", "").strip())


def request_admin_api(endpoint, content=None, timeout=10):
    url = os.environ["CADDY_ADMIN_URL"].rstrip("/") + endpoint
    data = content.encode("utf-8") if content is not None else None
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "text/caddyfile"}
    )
    command = [request.get_method(), url]
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return subprocess.CompletedProcess(
                command, 0, stdout=response.read().decode("utf-8"), stderr=""
            )
    except urllib.error.HTTPError as error:
        return subprocess.CompletedProcess(
            command, 1, stdout="", stderr=error.read().decode("utf-8", errors="replace")
        )
    except (OSError, urllib.error.URLError) as error:
        return subprocess.CompletedProcess(command, 1, stdout="", stderr=str(error))


def validate_caddyfile(caddyfile_path):
    if uses_admin_api():
        with open(caddyfile_path, encoding="utf-8") as file:
            return request_admin_api("/adapt", file.read())
    return subprocess.run(
        ["sudo", "caddy", "validate", "--config", caddyfile_path],
        capture_output=True,
        text=True,
    )


def reload_caddy(caddyfile_path, check=False):
    if uses_admin_api():
        with open(caddyfile_path, encoding="utf-8") as file:
            result = request_admin_api("/load", file.read())
        if check:
            result.check_returncode()
        return result
    command = ["sudo", "systemctl", "reload", "caddy"]
    if check:
        return subprocess.run(command, check=True)
    return subprocess.run(command, capture_output=True, text=True)


def get_root_certificate():
    result = request_admin_api("/pki/ca/local")
    result.check_returncode()
    return json.loads(result.stdout)["root_certificate"]
