"""Validate route forms, update Caddy and set response messages."""

import ipaddress
import re

from flask import redirect, request, session, url_for

from .audit import log_audit
from .backend import reload_caddy, validate_caddyfile
from .caddy import (
    append_caddyfile,
    build_route_block,
    get_routes,
    read_caddyfile,
    remove_route_block,
    write_caddyfile,
)
from .domains import domain_tls_mode


def add_route(caddyfile_path, domains_list, config=None):
    if not domains_list:
        session["flash_message"] = "Add a base domain before creating a route."
        session["flash_error"] = True
        return redirect(url_for("index"))
    name = request.form.get("name", "").strip().lower()
    ip_str = request.form.get("ip", "").strip()
    port_str = request.form.get("port", "").strip()
    protocol = request.form.get("protocol", "http")
    selected_domain = request.form.get("base_domain", domains_list[0]).strip()

    if not re.match(r"^[a-z0-9-]+$", name):
        session["flash_message"] = (
            "Invalid subdomain name. Only lowercase letters, numbers, and hyphens are allowed."
        )
        session["flash_error"] = True
        log_audit("VALIDATION_ERROR", f"Invalid subdomain attempted: {name}")
        return redirect(url_for("index"))

    try:
        ipaddress.ip_address(ip_str)
    except ValueError:
        session["flash_message"] = "Invalid IP address format."
        session["flash_error"] = True
        log_audit("VALIDATION_ERROR", f"Invalid IP format attempted: {ip_str}")
        return redirect(url_for("index"))

    if not port_str.isdigit() or not (1 <= int(port_str) <= 65535):
        session["flash_message"] = "Invalid port number. Must be between 1 and 65535."
        session["flash_error"] = True
        log_audit("VALIDATION_ERROR", f"Invalid port attempted: {port_str}")
        return redirect(url_for("index"))

    if protocol not in ["http", "https"]:
        session["flash_message"] = "Invalid protocol selected."
        session["flash_error"] = True
        return redirect(url_for("index"))

    if selected_domain not in domains_list:
        session["flash_message"] = "Unauthorized base domain selection."
        session["flash_error"] = True
        return redirect(url_for("index"))

    subdomain = f"{name}.{selected_domain}"

    routes_check = get_routes()
    if any(r["domain"] == subdomain for r in routes_check):
        session["flash_message"] = f"Route for {subdomain} already exists!"
        session["flash_error"] = True
        return redirect(url_for("index"))

    block = build_route_block(
        subdomain,
        ip_str,
        port_str,
        protocol,
        domain_tls_mode(config or {}, selected_domain),
    )

    try:
        old_content = read_caddyfile(caddyfile_path)

        if not append_caddyfile(caddyfile_path, block):
            session["flash_message"] = (
                "Failed to write to Caddyfile. Check sudo permissions."
            )
            session["flash_error"] = True
            return redirect(url_for("index"))

        valid = validate_caddyfile(caddyfile_path)
        reload_res = reload_caddy(caddyfile_path)

        if valid.returncode != 0 and reload_res.returncode != 0:
            write_caddyfile(caddyfile_path, old_content)
            session["flash_message"] = (
                "Caddy configuration validation/reload failed. Changes were rolled back safely."
            )
            session["flash_error"] = True
            log_audit(
                "ROUTE_ADD_FAILED", f"Validation/Reload failed for route {subdomain}"
            )
        else:
            session["flash_message"] = (
                f"Successfully added and reloaded route for {subdomain}!"
            )
            session["flash_error"] = False
            log_audit(
                "ROUTE_ADDED",
                f"Successfully added route {subdomain} pointing to {protocol}://{ip_str}:{port_str}",
            )
    except Exception:
        session["flash_message"] = (
            "An unexpected error occurred while modifying the Caddyfile."
        )
        session["flash_error"] = True
        log_audit("ROUTE_ADD_ERROR", f"Exception while adding route {subdomain}")


def remove_route(caddyfile_path):
    target_route = request.form.get("route", "").strip()

    valid_routes = [r["domain"] for r in get_routes()]
    if target_route not in valid_routes:
        session["flash_message"] = "Invalid route selection for removal."
        session["flash_error"] = True
        return redirect(url_for("index"))

    try:
        content = read_caddyfile(caddyfile_path)

        new_content = remove_route_block(content, target_route)

        if not write_caddyfile(caddyfile_path, new_content):
            session["flash_message"] = (
                "Failed to update Caddyfile. Check sudo permissions."
            )
            session["flash_error"] = True
            return redirect(url_for("index"))

        reload_caddy(caddyfile_path, check=True)
        session["flash_message"] = f"Successfully removed route: {target_route}"
        session["flash_error"] = False
        log_audit("ROUTE_REMOVED", f"Successfully removed route {target_route}")
    except Exception:
        session["flash_message"] = "An error occurred while removing the route."
        session["flash_error"] = True
        log_audit(
            "ROUTE_REMOVE_ERROR", f"Exception while removing route {target_route}"
        )
