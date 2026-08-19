#!/bin/bash

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run as root (sudo ./install.sh)"
  exit 1
fi

echo "=================================================="
echo "🚀 Caddy Reverse Proxy Manager Installer (Hardened)"
echo "=================================================="

# Interactive configuration prompts
read -p "[?] Enter your base domains separated by commas (default home.lab, testhome.lab): " INPUT_DOMAINS
INPUT_DOMAINS=${INPUT_DOMAINS:-home.lab, testhome.lab}

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

echo "[CaddyManager] 👤 Creating dedicated system user..."
id -u caddyman &>/dev/null || useradd -r -s /bin/false caddyman

echo "[CaddyManager] 🐍 Installing required Python dependencies..."
apt-get update > /dev/null 2>&1
apt-get install -y python3-pip python3-yaml python3-flask python3-limits > /dev/null 2>&1
pip3 install flask-wtf flask-limiter > /dev/null 2>&1

echo "[CaddyManager] 📁 Setting up application and log directories..."
INSTALL_DIR="/opt/caddy-manager"
LOG_DIR="$INSTALL_DIR/logs"

mkdir -p "$INSTALL_DIR"
mkdir -p "$LOG_DIR"

cp app.py "$INSTALL_DIR/" > /dev/null 2>&1
if [ -d "static" ]; then
    cp -r static "$INSTALL_DIR/" > /dev/null 2>&1
fi

echo "[CaddyManager] ⚙️ Writing configuration files..."
CONFIG_FILE="$INSTALL_DIR/config.yml"

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

# Give caddyman ownership of its installation and log files
chown -R caddyman:caddyman "$INSTALL_DIR"

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
# Hardening parameters
NoNewPrivileges=true
ProtectSystem=full
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload > /dev/null 2>&1
systemctl enable caddy-manager > /dev/null 2>&1
systemctl restart caddy-manager > /dev/null 2>&1

echo "=================================================="
echo "✔ Installation Complete! Hardened Caddy Manager is running."
echo "✔ Access it at: http://<your-server-ip>:5000"
echo "--------------------------------------------------"
echo "⚠️  REMINDER: Remember to set up a DNS rewrite in AdGuard!"
echo "    - Set the Domain/Rewrite to your wildcard domain."
echo "=================================================="