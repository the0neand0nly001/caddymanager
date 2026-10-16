"""Process metrics and TCP backend health checks."""

import os
import re
import socket

import psutil

from .caddy import get_routes

try:
    caddy_proc = psutil.Process(os.getpid())
    caddy_proc.cpu_percent(interval=None)
except Exception:
    caddy_proc = None


def check_service_status(target):
    # Parse target string like "192.168.1.50:8080" or "http://192.168.1.50:8080"
    clean_target = re.sub(r"^https?://", "", target)
    parts = clean_target.split(":")

    if len(parts) != 2:
        return "Down"

    ip, port_str = parts[0], parts[1].split("/")[0]

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(2.0)
            result = sock.connect_ex((ip, int(port_str)))
            if result == 0:
                return "Online"
            else:
                return "Down"
    except Exception:
        return "Down"


def get_metrics():
    cpu_usage = 0.0
    ram_mb = 0.0

    global caddy_proc
    try:
        if not caddy_proc:
            caddy_proc = psutil.Process(os.getpid())

        cpu_usage = round(caddy_proc.cpu_percent(interval=None), 1)
        ram_bytes = caddy_proc.memory_info().rss
        ram_mb = round(ram_bytes / (1024 * 1024), 1)
    except Exception:
        pass

    route_count = len(get_routes())

    return {"cpu": cpu_usage, "ram_mb": ram_mb, "routes": route_count}
