#!/usr/bin/python3
"""Minimal init adapter for testing real native services inside disposable Docker."""

import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

if not Path("/.dockerenv").exists():
    sys.exit("The native test init adapter is only for disposable Docker containers")

state = Path("/run/caddymanager-native-test")
state.mkdir(exist_ok=True)
action = sys.argv[1]
service = sys.argv[2] if len(sys.argv) > 2 else ""
pid_file = state / (service + ".pid")


def running():
    try:
        os.kill(int(pid_file.read_text()), 0)
        return True
    except (FileNotFoundError, ProcessLookupError):
        return False
    except PermissionError:
        return True  # The unprivileged app cannot signal the root-owned wrapper.


if action in {"daemon-reload", "enable", "disable"}:
    sys.exit(0)
if action == "is-active":
    print("active" if running() else "inactive")
    sys.exit(0 if running() else 3)
if action == "reload" and service == "caddy":
    sys.exit(
        subprocess.run(
            ["/usr/bin/caddy", "reload", "--config", "/etc/caddy/Caddyfile"]
        ).returncode
    )
if action not in {"restart", "stop"} or service not in {"caddy", "caddy-manager"}:
    sys.exit("Unsupported native-test init command")
if running():
    os.killpg(int(pid_file.read_text()), signal.SIGTERM)
    time.sleep(0.5)
if action == "stop":
    sys.exit(0)

if service == "caddy":
    command = [
        "runuser",
        "-u",
        "caddy",
        "--",
        "env",
        "HOME=/var/lib/caddy",
        "caddy",
        "run",
        "--config",
        "/etc/caddy/Caddyfile",
    ]
    port = 2019
else:
    command = ["runuser", "-u", "caddyman", "--", "/usr/bin/python3", "app.py"]
    port = 5000
with open(state / (service + ".log"), "ab") as log:
    process = subprocess.Popen(
        command,
        cwd="/opt/caddy-manager",
        stdout=log,
        stderr=log,
        start_new_session=True,
    )
pid_file.write_text(str(process.pid))
for _ in range(100):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            sys.exit(0)
    except OSError:
        if process.poll() is not None:
            sys.exit("Native-test service exited; inspect its container log")
        time.sleep(0.1)
sys.exit("Native-test service did not become ready")
