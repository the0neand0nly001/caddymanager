"""Prepare persistent container state, then start the web server."""

import os
from pathlib import Path
import secrets

import yaml
from werkzeug.security import generate_password_hash


def initialize(data_dir, caddyfile):
    data_dir = Path(data_dir)
    caddyfile = Path(caddyfile)
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "logs").mkdir(exist_ok=True)
    caddyfile.parent.mkdir(parents=True, exist_ok=True)

    config_file = data_dir / "config.yml"
    if not config_file.exists():
        domains = [
            domain.strip()
            for domain in os.environ.get(
                "CADDY_DOMAINS", "home.lab,testhome.lab"
            ).split(",")
            if domain.strip()
        ]
        if not domains:
            raise ValueError("CADDY_DOMAINS must contain at least one base domain")
        settings = {
            "WEBSERVER_PORT": 5000,
            "CADDYFILE_PATH": str(caddyfile),
            "DOMAINS": domains,
            "ADGUARD_IP": os.environ.get("ADGUARD_IP", "192.168.1.100"),
            "DISCORD_WEBHOOK_URL": os.environ.get("DISCORD_WEBHOOK_URL", ""),
        }
        config_file.write_text(
            yaml.safe_dump(settings, sort_keys=False), encoding="utf-8"
        )

    credentials = data_dir / ".credentials"
    if not credentials.exists():
        username = os.environ.get("ADMIN_USERNAME", "admin")
        password = os.environ.get("ADMIN_PASSWORD", "admin")
        if not username or not password or "\n" in username or "\r" in username:
            raise ValueError(
                "Admin credentials must be nonempty and the username one line"
            )
        credentials.write_text(
            username + "\n" + generate_password_hash(password), encoding="utf-8"
        )
        credentials.chmod(0o600)

    secret_file = data_dir / ".flask-secret-key"
    if not secret_file.exists():
        secret_file.write_text(secrets.token_hex(32), encoding="ascii")
        secret_file.chmod(0o600)
    os.environ.setdefault("FLASK_SECRET_KEY", secret_file.read_text(encoding="ascii"))

    if not caddyfile.exists():
        caddyfile.write_text(
            "{\n    admin 0.0.0.0:2019\n}\n\nlocalhost {\n    tls internal\n}\n",
            encoding="utf-8",
        )


def main():
    initialize(
        os.environ.get("CADDY_MANAGER_DATA_DIR", "/data"),
        os.environ.get("CADDYFILE_PATH", "/etc/caddy/Caddyfile"),
    )
    executable = "/opt/venv/bin/gunicorn"
    os.execv(
        executable,
        [
            executable,
            "--bind",
            "0.0.0.0:5000",
            "--workers",
            "1",
            "--threads",
            "4",
            "--access-logfile",
            "-",
            "--error-logfile",
            "-",
            "app:app",
        ],
    )


if __name__ == "__main__":
    main()
