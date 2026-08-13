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

# 2. Prompt for AdGuard IP
read -p "[?] Enter your AdGuard Home IP (default 192.168.1.100): " ADGUARD_IP
ADGUARD_IP=${ADGUARD_IP:-192.168.1.100}

# 3. Create installation directory
INSTALL_DIR="/opt/caddy-manager"
mkdir -p "$INSTALL_DIR"

# 4. Copy application files over
cp app.py "$INSTALL_DIR/"
cp config.yml "$INSTALL_DIR/" 2>/dev/null || true

# 5. Save AdGuard IP to config.yml
CONFIG_FILE="$INSTALL_DIR/config.yml"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "DOMAIN: home.lab" > "$CONFIG_FILE"
    echo "CADDYFILE_PATH: /etc/caddy/Caddyfile" >> "$CONFIG_FILE"
    echo "WEBSERVER_PORT: 5000" >> "$CONFIG_FILE"
fi

# Update or add ADGUARD_IP in config.yml
if grep -q "ADGUARD_IP:" "$CONFIG_FILE"; then
    sed -i "s/ADGUARD_IP:.*/ADGUARD_IP: \"$ADGUARD_IP\"/" "$CONFIG_FILE"
else
    echo "ADGUARD_IP: \"$ADGUARD_IP\"" >> "$CONFIG_FILE"
fi

echo "[✔] Configuration saved with AdGuard IP: $ADGUARD_IP"

# 6. Set up Systemd Service for Caddy Manager
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