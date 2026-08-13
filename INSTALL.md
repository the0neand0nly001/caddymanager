#!/bin/bash

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run this script with sudo or as root."
  exit 1
fi

echo "[+] Starting Caddy Manager Installation..."

# 1. Install system dependencies
apt-get update
apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl python3 python3-pip python3-flask python3-yaml

# 2. Automatically install official Caddy web server if not present
if ! command -v caddy &> /dev/null; then
  echo "[+] Installing official Caddy web server..."
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
  apt-get update
  apt-get install -y caddy
else
  echo "[+] Caddy is already installed."
fi

# 3. Interactive Prompts for AdGuard / DNS Options & Config
echo ""
echo "=== Caddy Manager Setup Configuration ==="
read -p "[?] Enter your base domain (default: home.lab): " USER_DOMAIN
USER_DOMAIN=${USER_DOMAIN:-home.lab}

read -p "[?] Enter your AdGuard Home / Upstream DNS IP (e.g., 192.168.1.100): " ADGUARD_IP
ADGUARD_IP=${ADGUARD_IP:-192.168.1.100}

# 4. Set up production directory
INSTALL_DIR="/opt/caddy-manager"
mkdir -p "$INSTALL_DIR"
cp -r . "$INSTALL_DIR/"

# 5. Write out the config.yml with user choices
cat << EOF > "$INSTALL_DIR/config.yml"
WEBSERVER_PORT: 5000
CADDYFILE_PATH: "/etc/caddy/Caddyfile"
DOMAIN: "$USER_DOMAIN"
ADGUARD_IP: "$ADGUARD_IP"
EOF

# 6. Set up Admin Credentials
echo ""
echo "=== Set up Admin Credentials ==="
python3 - "$INSTALL_DIR" << 'EOF'
import sys, os
from werkzeug.security import generate_password_hash
import getpass

install_dir = sys.argv[1]
username = input("Enter admin username: ")
password = getpass.getpass("Enter admin password: ")

hashed_pw = generate_password_hash(password)
with open(os.path.join(install_dir, ".credentials"), "w") as f:
    f.write(f"{username}:{hashed_pw}")
print("[+] Credentials saved securely.")
EOF

# 7. Create and register Systemd Service
echo "[+] Configuring systemd service..."
cat << EOF > /etc/systemd/system/caddy-manager.service
[Unit]
Description=Caddy Manager Web Interface
After=network.target caddy.service

[Service]
User=root
WorkingDirectory=/opt/caddy-manager
ExecStart=/usr/bin/python3 /opt/caddy-manager/app.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable caddy-manager
systemctl restart caddy-manager
systemctl restart caddy

echo ""
echo "[+] Installation complete! Caddy Manager is running on port 5000."
echo "[+] AdGuard/DNS Target set to: $ADGUARD_IP with domain: $USER_DOMAIN"