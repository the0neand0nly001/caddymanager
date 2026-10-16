"""Read-only system overview and checks limited to configured proxy targets."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import socket
import subprocess
from urllib.parse import urlsplit

from .backend import request_admin_api, uses_admin_api
from .caddy import get_routes
from .config import load_config
from .domains import configured_domains


def target_address(target):
    if not target or target == "Unknown":
        return None
    try:
        parsed = urlsplit(target if "://" in target else "//" + target)
        if parsed.scheme and parsed.scheme not in {"http", "https"}:
            return None
        if (
            parsed.hostname
            and parsed.port
            and not parsed.username
            and not parsed.password
        ):
            return parsed.hostname, parsed.port
    except ValueError:
        pass
    return None


def caddy_status():
    if uses_admin_api():
        result = request_admin_api("/config/", timeout=3)
        try:
            responding = result.returncode == 0 and isinstance(
                json.loads(result.stdout), dict
            )
        except (ValueError, TypeError):
            responding = False
        return {
            "state": "responding" if responding else "unavailable",
            "source": "Admin API",
        }
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "caddy"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        active = result.returncode == 0 and result.stdout.strip() == "active"
        return {"state": "active" if active else "inactive", "source": "systemd"}
    except (OSError, subprocess.TimeoutExpired):
        return {"state": "unknown", "source": "systemd"}


def overview():
    routes = [
        dict(route, checkable=target_address(route["target"]) is not None)
        for route in get_routes()
    ]
    return {
        "services": routes,
        "totals": {
            "routes": len(routes),
            "domains": len(configured_domains(load_config())),
        },
        "caddy": caddy_status(),
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }


def check_services(domain=None):
    routes = get_routes()
    if domain is not None:
        routes = [route for route in routes if route["domain"] == domain]
        if not routes:
            raise ValueError(
                "That route is no longer configured. Refresh the dashboard."
            )
    addresses = {route["target"]: target_address(route["target"]) for route in routes}

    def probe(target):
        address = addresses[target]
        if address is None:
            return target, {"status": "unconfigured", "checked_at": None}
        try:
            with socket.create_connection(address, timeout=2):
                status = "online"
        except OSError:
            status = "down"
        return target, {
            "status": status,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = dict(pool.map(probe, addresses))
    return [dict(route, **results[route["target"]]) for route in routes]
