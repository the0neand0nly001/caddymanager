#!/bin/bash

if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run this installer with sudo or as root."
  exit 1
fi

CLEAR_SCREEN="\033[H\033[2J"
echo -e "$CLEAR_SCREEN"
echo "===================================================="
echo "    🚀 Caddy Reverse Proxy Manager Installer        "
echo "===================================================="

# Check if Caddy is installed on the system
if ! command -v caddy &> /dev/null; then
  echo ""
  echo "[!] ERROR: Caddy is not found on this system!"
  echo "[!] Please install Caddy first before running this manager."
  echo "[!] (Visit https://caddyserver.com/docs/install for installation instructions)"
  echo ""
  exit 1
fi

echo "[✓] Caddy detected on system."

# 1. Install dependencies including python3-yaml
echo "[+] Installing Python3, Flask, and PyYAML..."
apt-get update -y && apt-get install -y python3 python3-pip python3-flask python3-yaml > /dev/null 2>&1

# 2. Setup directory path
INSTALL_DIR="/opt/caddy-manager"
echo "[+] Copying files to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
cp app.py "$INSTALL_DIR/"

# Copy config.yml if it exists locally, otherwise create a default one
if [ -f "config.yml" ]; then
    cp config.yml "$INSTALL_DIR/"
else
    echo -e "WEBSERVER_PORT: 5000\nCADDYFILE_PATH: \"/etc/caddy/Caddyfile\"\nDOMAIN: \"home.lab\"" > "$INSTALL_DIR/config.yml"
fi

# 3. Interactive Admin Setup
echo ""
echo "----------------------------------------------------"
echo " 🔐 Administrator Account Setup"
echo "----------------------------------------------------"
read -p "Enter desired admin username [default: admin]: " ADMIN_USER
ADMIN_USER=${ADMIN_USER:-admin}

read -s -p "Enter desired admin password: " ADMIN_PASS
echo ""

PYTHON_HASH=$(python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('$ADMIN_PASS'))")

echo "$ADMIN_USER" > "$INSTALL_DIR/.credentials"
echo "$PYTHON_HASH" >> "$INSTALL_DIR/.credentials"
chmod 600 "$INSTALL_DIR/.credentials"
echo "[+] Credentials configured securely!"

# 4. Create Systemd Service
SERVICE_FILE="/etc/systemd/system/caddy-manager.service"
echo "[+] Creating systemd service file..."

cat << EOF > "$SERVICE_FILE"
[Unit]
Description=Caddy Reverse Proxy Manager Flask App
After=network.target caddy.service

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/app.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# 5. Enable and Start Service
systemctl daemon-reload
systemctl enable caddy-manager
systemctl restart caddy-manager

echo -e "$CLEAR_SCREEN"
echo "===================================================="
echo " ✨ Installation Complete Successfully!             "
echo "===================================================="
echo " Your app is running with options pulled from config.yml"
echo "===================================================="