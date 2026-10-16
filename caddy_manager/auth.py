"""Credential loading and login/logout request handlers."""

import os

from flask import redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .audit import log_audit
from .config import CRED_FILE


def get_stored_credentials():
    if os.path.exists(CRED_FILE):
        with open(CRED_FILE, "r") as f:
            lines = f.read().splitlines()
            if len(lines) >= 2:
                return lines[0], lines[1]
    return "admin", generate_password_hash("admin")


ADMIN_USER, ADMIN_PASSWORD_HASH = get_stored_credentials()


def login():
    error = None
    global ADMIN_USER, ADMIN_PASSWORD_HASH
    ADMIN_USER, ADMIN_PASSWORD_HASH = get_stored_credentials()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == ADMIN_USER and check_password_hash(
            ADMIN_PASSWORD_HASH, password
        ):
            session["logged_in"] = True
            log_audit("LOGIN_SUCCESS", f"User '{username}' logged in successfully.")
            return redirect(url_for("index"))
        else:
            log_audit(
                "LOGIN_FAILED", f"Failed login attempt for username '{username}'."
            )
            error = "Invalid username or password."
    return render_template("login.html", error=error)


def logout():
    log_audit("LOGOUT", "User signed out.")
    session.clear()
    return redirect(url_for("login"))


def register_auth_routes(app, limiter):
    app.add_url_rule(
        "/login",
        view_func=limiter.limit("10 per minute")(login),
        methods=["GET", "POST"],
    )
    app.add_url_rule("/logout", view_func=logout)
