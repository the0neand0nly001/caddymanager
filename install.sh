#!/bin/bash
set -eo pipefail

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run as root (sudo bash install.sh)"
  exit 1
fi

echo "=================================================="
echo "🚀 Caddy Reverse Proxy Manager Installer (Hardened)"
echo "=================================================="

echo "[CaddyManager] Installing system dependencies..."
apt-get update >/dev/null
apt-get install -y ca-certificates curl gnupg wget sudo whiptail python3 python3-pip >/dev/null
python3 -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11 or newer is required"'
DISCORD_WEBHOOK_URL=""

if (whiptail --title "Caddy Manager Setup" --yesno "Would you like to use default settings?" 10 60); then
    INPUT_DOMAINS="home.lab, testhome.lab"
    ADGUARD_IP="192.168.1.100"
    ADMIN_USER="admin"
    ADMIN_PASS="admin"
    DISCORD_WEBHOOK_URL=""
else
    INPUT_DOMAINS=$(whiptail --title "Base Domains" --inputbox "Enter base domains separated by commas:" 10 60 "home.lab, testhome.lab" 3>&1 1>&2 2>&3)
    [ -z "$INPUT_DOMAINS" ] && INPUT_DOMAINS="home.lab, testhome.lab"

    ADGUARD_IP=$(whiptail --title "AdGuard IP" --inputbox "Enter your AdGuard Home IP:" 10 60 "192.168.1.100" 3>&1 1>&2 2>&3)
    [ -z "$ADGUARD_IP" ] && ADGUARD_IP="192.168.1.100"

    ADMIN_USER=$(whiptail --title "Admin Username" --inputbox "Enter admin username:" 10 60 "admin" 3>&1 1>&2 2>&3)
    [ -z "$ADMIN_USER" ] && ADMIN_USER="admin"

    ADMIN_PASS=$(whiptail --title "Admin Password" --passwordbox "Enter admin password:" 10 60 3>&1 1>&2 2>&3)
    [ -z "$ADMIN_PASS" ] && ADMIN_PASS="admin"

    if (whiptail --title "Discord Webhook" --yesno "Would you like to link a Discord webhook for security alerts?" 10 60); then
        DISCORD_WEBHOOK_URL=$(whiptail --title "Discord Webhook" --inputbox "Enter your Discord Webhook URL:" 10 60 3>&1 1>&2 2>&3)
    fi
fi

if !(whiptail --title "Ready to Install" --yesno "Proceed with installing Caddy Manager?" 10 60); then
    echo "Installation aborted."
    exit 0
fi

clear

echo "[CaddyManager] 📦 Checking and installing Caddy..."
if ! command -v caddy &> /dev/null; then
    apt-get update > /dev/null 2>&1
    apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl > /dev/null 2>&1
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg > /dev/null 2>&1
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list > /dev/null 2>&1
    apt-get update > /dev/null 2>&1
    apt-get install -y caddy > /dev/null 2>&1
fi

echo "[CaddyManager] 👤 Creating dedicated system user and group memberships..."
id -u caddyman &>/dev/null || useradd -r -s /bin/false caddyman
usermod -aG caddy caddyman

echo "[CaddyManager] 📁 Setting up application and downloading files from GitHub..."
INSTALL_DIR="/opt/caddy-manager"
LOG_DIR="$INSTALL_DIR/logs"
STATIC_DIR="$INSTALL_DIR/static"

mkdir -p "$INSTALL_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$STATIC_DIR"

# Download the modules and templates before replacing the startup file.
APP_FILES=(
    "caddy_manager/__init__.py"
    "caddy_manager/config.py"
    "caddy_manager/domains.py"
    "caddy_manager/dashboard.py"
    "caddy_manager/activity.py"
    "caddy_manager/auth.py"
    "caddy_manager/audit.py"
    "caddy_manager/backend.py"
    "caddy_manager/caddy.py"
    "caddy_manager/monitoring.py"
    "caddy_manager/route_actions.py"
    "caddy_manager/views.py"
    "templates/login.html"
    "templates/icons.html"
    "templates/partials/system.html"
    "templates/partials/activity.html"
    "templates/dashboard.html"
    "templates/css/login.css"
    "templates/css/dashboard.css"
    "templates/js/dashboard.js"
    "templates/js/system.js"
    "templates/js/activity.js"
    "requirements.txt"
)
DOWNLOAD_DIR=$(mktemp -d /tmp/caddy-manager-files.XXXXXX)
trap 'rm -rf -- "$DOWNLOAD_DIR"' EXIT
for app_file in "${APP_FILES[@]}" app.py update.sh uninstall.sh static/icon.png; do
    mkdir -p "$DOWNLOAD_DIR/$(dirname "$app_file")"
    if [ -n "${CADDY_MANAGER_SOURCE_DIR:-}" ]; then
        cp -- "$CADDY_MANAGER_SOURCE_DIR/$app_file" "$DOWNLOAD_DIR/$app_file"
    else
        wget -q -O "$DOWNLOAD_DIR/$app_file" "https://raw.githubusercontent.com/the0neand0nly001/caddymanager/stable/$app_file"
    fi
done

# Install dependencies before replacing the application; failed downloads leave it intact.
python3 -m pip install --break-system-packages -r "$DOWNLOAD_DIR/requirements.txt" >/dev/null
python3 -m compileall -q "$DOWNLOAD_DIR"
cp -R "$DOWNLOAD_DIR/." "$INSTALL_DIR/"

chmod +x "$INSTALL_DIR/update.sh" "$INSTALL_DIR/uninstall.sh"

echo "[CaddyManager] ⚙️ Writing configuration files..."
CONFIG_FILE="$INSTALL_DIR/config.yml"

INPUT_DOMAINS="$INPUT_DOMAINS" ADGUARD_IP="$ADGUARD_IP" \
ADMIN_USER="$ADMIN_USER" ADMIN_PASS="$ADMIN_PASS" \
DISCORD_WEBHOOK_URL="$DISCORD_WEBHOOK_URL" python3 - "$INSTALL_DIR" <<'PY'
import os
from pathlib import Path
import sys

import yaml
from werkzeug.security import generate_password_hash

install_dir = Path(sys.argv[1])
username = os.environ["ADMIN_USER"]
if "\n" in username or "\r" in username:
    raise ValueError("Admin username must be one line")
settings = {
    "WEBSERVER_PORT": 5000,
    "CADDYFILE_PATH": "/etc/caddy/Caddyfile",
    "DOMAINS": [name.strip() for name in os.environ["INPUT_DOMAINS"].split(",") if name.strip()],
    "ADGUARD_IP": os.environ["ADGUARD_IP"],
    "DISCORD_WEBHOOK_URL": os.environ["DISCORD_WEBHOOK_URL"],
}
(install_dir / "config.yml").write_text(yaml.safe_dump(settings, sort_keys=False), encoding="utf-8")
(install_dir / ".credentials").write_text(
    username + "\n" + generate_password_hash(os.environ["ADMIN_PASS"]), encoding="utf-8"
)
PY

chown -R caddyman:caddyman "$INSTALL_DIR"

echo "[CaddyManager] 📁 Setting up Caddyfile and permissions..."
touch /etc/caddy/Caddyfile
chown -R root:caddy /etc/caddy
chmod 775 /etc/caddy
chmod 664 /etc/caddy/Caddyfile

chmod 600 "$INSTALL_DIR/.credentials"
chmod 644 "$INSTALL_DIR/config.yml"

echo "[CaddyManager] 🔑 Configuring restricted sudoers privileges for Caddy operations..."
SUDOERS_FILE="/etc/sudoers.d/caddyman"
cat << EOF > "$SUDOERS_FILE"
caddyman ALL=(ALL) NOPASSWD: /usr/bin/systemctl reload caddy, /usr/bin/systemctl restart caddy, /usr/bin/caddy validate --config /etc/caddy/Caddyfile, /usr/bin/cat /etc/caddy/Caddyfile, /usr/bin/tee /etc/caddy/Caddyfile, /usr/bin/tee -a /etc/caddy/Caddyfile, /usr/bin/cp /var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt *, /usr/bin/chown caddyman\:caddyman *
EOF
chmod 440 "$SUDOERS_FILE"

# Ensure Caddy is restarted so it generates the internal CA certificate on a fresh setup
systemctl restart caddy
sleep 2

echo "[CaddyManager] 🔌 Configuring systemd service..."
SERVICE_FILE="/etc/systemd/system/caddy-manager.service"
cat << EOF > "$SERVICE_FILE"
[Unit]
Description=Caddy Reverse Proxy Manager
After=network.target caddy.service

[Service]
User=caddyman
Group=caddyman
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 app.py
Restart=always
NoNewPrivileges=false
ProtectSystem=false
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF

# Ensure Caddyfile has a default block so Caddy initializes internal TLS
if [ ! -s /etc/caddy/Caddyfile ]; then
    echo "localhost {
        tls internal
    }" > /etc/caddy/Caddyfile
fi

# Restart Caddy to force generation of the local CA certificate
systemctl restart caddy
sleep 2

systemctl daemon-reload > /dev/null 2>&1
systemctl enable caddy-manager > /dev/null 2>&1
systemctl restart caddy-manager > /dev/null 2>&1

IP_ADDR=$(hostname -I | awk '{print $1}')
echo "=================================================="
echo "✔ Installation Complete! Hardened Caddy Manager is running."
echo "✔ Access it at: http://${IP_ADDR}:5000"
echo "--------------------------------------------------"
echo "⚠️  REMINDER: Remember to set up a DNS rewrite in AdGuard!"
echo "     - Set the Domain/Rewrite to your wildcard domain."
echo "=================================================="
