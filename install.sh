#!/bin/bash

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run as root (sudo ./install.sh)"
  exit 1
fi

echo "=================================================="
echo "🚀 Caddy Reverse Proxy Manager Installer"
echo "=================================================="

# Interactive configuration prompts (must remain visible)
read -p "[?] Enter your base domains separated by commas (default home.lab, k3shome.lab): " INPUT_DOMAINS
INPUT_DOMAINS=${INPUT_DOMAINS:-home.lab, k3shome.lab}

read -p "[?] Enter your AdGuard Home IP (default 192.168.1.100): " ADGUARD_IP
ADGUARD_IP=${ADGUARD_IP:-192.168.1.100}

read -p "[?] Enter admin username for Caddy Manager (default admin): " ADMIN_USER
ADMIN_USER=${ADMIN_USER:-admin}

read -s -p "[?] Enter admin password for Caddy Manager (default admin): " ADMIN_PASS
echo
ADMIN_PASS=${ADMIN_PASS:-admin}

echo "[CaddyManager] 📦 Checking and installing Caddy..."
if ! command -v caddy &> /dev/null; then
    apt-get update > /dev/null 2>&1
    apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl > /dev/null 2>&1
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg > /dev/null 2>&1
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list > /dev/null 2>&1
    apt-get update > /dev/null 2>&1
    apt-get install -y caddy > /dev/null 2>&1
fi

echo "[CaddyManager] 📁 Setting up application directory..."
INSTALL_DIR="/opt/caddy-manager"
mkdir -p "$INSTALL_DIR"
cp app.py "$INSTALL_DIR/" > /dev/null 2>&1

echo "[CaddyManager] ⚙️ Writing configuration files..."
CONFIG_FILE="$INSTALL_DIR/config.yml"

# Parse comma-separated domains into a YAML list format
YAML_DOMAINS=""
IFS=',' read -ra ADDR <<< "$INPUT_DOMAINS"
for i in "${ADDR[@]}"; do
    clean_domain=$(echo "$i" | xargs)
    YAML_DOMAINS+="  - \"$clean_domain\""$'\n'
done

cat << EOF > "$CONFIG_FILE"
WEBSERVER_PORT: 5000
CADDYFILE_PATH: "/etc/caddy/Caddyfile"
DOMAINS:
$YAML_DOMAINS
ADGUARD_IP: "$ADGUARD_IP"
EOF

python3 -c "
from werkzeug.security import generate_password_hash
pass_hash = generate_password_hash('$ADMIN_PASS')
with open('$INSTALL_DIR/.credentials', 'w') as f:
    f.write('$ADMIN_USER\n' + pass_hash)
" > /dev/null 2>&1

echo "[CaddyManager] 🔌 Configuring systemd service..."
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

systemctl daemon-reload > /dev/null 2>&1
systemctl enable caddy-manager > /dev/null 2>&1
systemctl restart caddy-manager > /dev/null 2>&1

echo "=================================================="
echo "✔ Installation Complete! Caddy Manager is running."
echo "✔ Access it at: http://<your-server-ip>:5000"
echo "=================================================="