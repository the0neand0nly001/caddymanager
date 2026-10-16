"""Audit logging and Discord notifications."""

import json
import os
import urllib.request
from datetime import datetime

from flask import request

from .config import AUDIT_LOG_FILE, load_config


def log_audit(action, details):
    client_ip = request.remote_addr or "Unknown"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = (
        f"[{timestamp}] IP: {client_ip} | Action: {action} | Details: {details}\n"
    )

    try:
        os.makedirs(os.path.dirname(AUDIT_LOG_FILE), exist_ok=True)
        with open(AUDIT_LOG_FILE, "a") as f:
            f.write(log_entry)
    except Exception:
        pass

    config = load_config()
    DISCORD_WEBHOOK_URL = config.get("DISCORD_WEBHOOK_URL", "")

    if DISCORD_WEBHOOK_URL:
        payload = {
            "content": f"🚨 **Caddy Manager Security Alert**\n• **Action:** `{action}`\n• **IP:** `{client_ip}`\n• **Details:** {details}"
        }

        try:
            req = urllib.request.Request(
                DISCORD_WEBHOOK_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "CaddyManager",
                },
            )
            urllib.request.urlopen(req)
        except Exception as e:
            print(f"Webhook error: {e}")
