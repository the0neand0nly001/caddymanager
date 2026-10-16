"""Dashboard, JSON API, certificate download and CSRF request handlers."""

import os
import subprocess

from flask import (
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_wtf.csrf import CSRFError

from .audit import log_audit
from .activity import read_activity
from .dashboard import check_services, overview
from .backend import get_root_certificate, uses_admin_api
from .caddy import get_routes
from .config import get_data_dir, load_config
from .domains import TLS_MODES, change_domain, configured_domains, domain_tls_mode
from .monitoring import check_service_status, get_metrics
from .route_actions import add_route, remove_route


def check_status():
    data = request.get_json() or {}
    target = data.get("target", "")
    return jsonify({"status": check_service_status(target)})


def api_metrics():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(get_metrics())


def api_overview():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(overview())


def api_services():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True)
    if data is None:
        data = {}
    if not isinstance(data, dict) or (
        "domain" in data and not isinstance(data["domain"], str)
    ):
        return jsonify({"error": "Choose a configured route."}), 400
    try:
        return jsonify({"services": check_services(data.get("domain"))})
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


def api_activity():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        before = int(request.args["before"]) if "before" in request.args else None
        return jsonify(read_activity(before=before))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except OSError:
        return (
            jsonify(
                {
                    "error": "The audit log could not be read. Check log file permissions."
                }
            ),
            503,
        )


def handle_csrf_error(e):
    log_audit("CSRF_ERROR", "Invalid or missing CSRF token encountered")
    return render_template(
        "dashboard.html",
        message="Cross-Site Request Forgery (CSRF) token missing or invalid.",
        is_error=True,
        routes=get_routes(),
        domains=[],
    )


def download_ca():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    src_path = "/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt"
    dest_path = os.path.join(get_data_dir(), "root.crt")

    try:
        if uses_admin_api():
            with open(dest_path, "wb") as file:
                file.write(get_root_certificate().encode("utf-8"))
        else:
            # Copy file using our authorized sudo cp rule and fix ownership.
            subprocess.run(["sudo", "/usr/bin/cp", src_path, dest_path], check=True)
            subprocess.run(
                ["sudo", "/usr/bin/chown", "caddyman:caddyman", dest_path], check=True
            )

        if os.path.exists(dest_path):
            log_audit("DOWNLOAD_CA", "Downloaded Caddy root CA certificate.")
            return send_file(
                dest_path, as_attachment=True, download_name="caddy-root-ca.crt"
            )
    except Exception as e:
        print(f"[ERROR] Failed to serve CA cert: {e}")

    return "Caddy root CA certificate not found.", 404


def index():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    config = load_config()
    adguard_ip = config.get("ADGUARD_IP", "192.168.1.100")
    domains_list = configured_domains(config)

    if request.method == "POST":
        action = request.form.get("action")
        caddyfile_path = config.get("CADDYFILE_PATH", "/etc/caddy/Caddyfile")

        if action == "add":
            response = add_route(caddyfile_path, domains_list, config)
        elif action == "remove":
            response = remove_route(caddyfile_path)
        elif action in {"add_domain", "update_domain", "remove_domain"}:
            try:
                domain = change_domain(
                    action,
                    request.form.get("domain", ""),
                    request.form.get("tls_mode", "internal"),
                )
                verb = {
                    "add_domain": "Added",
                    "update_domain": "Updated",
                    "remove_domain": "Removed",
                }[action]
                session["flash_message"] = (
                    f"{verb} base domain {domain}. Existing routes are unchanged."
                )
                session["flash_error"] = False
                log_audit(action.upper(), f"{verb} base domain {domain}")
            except ValueError as error:
                session["flash_message"] = str(error)
                session["flash_error"] = True
            except OSError:
                session["flash_message"] = (
                    "Could not save base domains. Check configuration file permissions."
                )
                session["flash_error"] = True
            return redirect(url_for("index", page="domains"))
        else:
            response = None

        if response is not None:
            return response

        return redirect(url_for("index"))

    message = session.pop("flash_message", None)
    is_error = session.pop("flash_error", False)
    routes = get_routes()

    return render_template(
        "dashboard.html",
        routes=routes,
        message=message,
        is_error=is_error,
        adguard_ip=adguard_ip,
        domains=domains_list,
        domain_settings=[
            {"name": domain, "tls_mode": domain_tls_mode(config, domain)}
            for domain in domains_list
        ],
        tls_modes=TLS_MODES,
    )


def register_views(app):
    app.add_url_rule("/api/check-status", view_func=check_status, methods=["POST"])
    app.add_url_rule("/api/metrics", view_func=api_metrics)
    app.add_url_rule("/api/overview", view_func=api_overview)
    app.add_url_rule("/api/services/check", view_func=api_services, methods=["POST"])
    app.add_url_rule("/api/activity", view_func=api_activity)
    app.add_url_rule("/download-ca", view_func=download_ca)
    app.add_url_rule("/", view_func=index, methods=["GET", "POST"])
    app.register_error_handler(CSRFError, handle_csrf_error)
