#!/bin/bash

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run as root (sudo ./install.sh)"
  exit 1
fi

echo "=================================================="
echo "🚀 Caddy Reverse Proxy Manager Installer"
echo "=================================================="

# 1. Install Caddy if not already present
if ! command -v caddy &> /dev/null; then
    echo "[+] Caddy not found. Installing Caddy..."
    apt-get update
    apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
    apt-get update
    apt-get install -y caddy
else
    echo "[✔] Caddy is already installed."
fi

# 2. Interactive Prompts
read -p "[?] Enter your base domain (default home.lab): " DOMAIN
DOMAIN=${DOMAIN:-home.lab}

read -p "[?] Enter your AdGuard Home IP (default 192.168.1.100): " ADGUARD_IP
ADGUARD_IP=${ADGUARD_IP:-192.168.1.100}

read -p "[?] Enter admin username for Caddy Manager (default admin): " ADMIN_USER
ADMIN_USER=${ADMIN_USER:-admin}

read -s -p "[?] Enter admin password for Caddy Manager (default admin): " ADMIN_PASS
echo
ADMIN_PASS=${ADMIN_PASS:-admin}

# 3. Create installation directory
INSTALL_DIR="/opt/caddy-manager"
mkdir -p "$INSTALL_DIR"

# 4. Copy application files over
cp app.py "$INSTALL_DIR/"

# 5. Save Configuration to config.yml
CONFIG_FILE="$INSTALL_DIR/config.yml"
cat << EOF > "$CONFIG_FILE"
DOMAIN: "$DOMAIN"
CADDYFILE_PATH: "/etc/caddy/Caddyfile"
WEBSERVER_PORT: 5000
ADGUARD_IP: "$ADGUARD_IP"
EOF

echo "[✔] Configuration saved to $CONFIG_FILE"

# 6. Save Credentials securely using python to generate the correct hash format
python3 -c "
from werkzeug.security import generate_password_hash
pass_hash = generate_password_hash('$ADMIN_PASS')
with open('$INSTALL_DIR/.credentials', 'w') as f:
    f.write('$ADMIN_USER\n' + pass_hash)
"
echo "[✔] Admin credentials configured."

# 7. Set up Systemd Service for Caddy Manager
SERVICE_FILE="/etc/systemd/system/caddy-manager.service"
cat << EOF > "$SERVICE_FILE"
[Unit]
Description=Caddy Reverse Proxy Manager
After=network.target caddy.service

[Service]
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 app.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable caddy-manager
systemctl restart caddy-manager

echo "=================================================="
echo "✔ Installation Complete! Caddy Manager is running."
echo "✔ Access it at: http://<your-server-ip>:5000"
echo "=================================================="