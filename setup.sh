#!/bin/bash

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run as root (sudo bash setup.sh)."
  exit 1
fi

INSTALL_DIR="/opt/caddy-manager"
CADDY_CONFIG_DIR="/etc/caddy"

echo "=================================================="
echo "🛠️ Caddy Manager Setup & Environment Preparation"
echo "=================================================="

# 1. Update package lists and install necessary system prerequisites
echo "[+] Installing system prerequisites (Python3, pip, curl, git)..."
apt-get update -y
apt-get install -y python3 python3-pip python3-yaml python3-werkzeug curl git caddy

# 2. Create directory structure with correct permissions
echo "[+] Creating application directories..."
mkdir -p "$INSTALL_DIR/static"

# 3. Handle Caddy configuration file permissions if they exist
if [ -f "$CADDY_CONFIG_DIR/Caddyfile" ]; then
    chown -R root:caddy "$CADDY_CONFIG_DIR"
    chmod 640 "$CADDY_CONFIG_DIR/Caddyfile"
fi

# 4. Set directory ownership
chown -R root:root "$INSTALL_DIR"
chmod 755 "$INSTALL_DIR"

# 5. Look for local application files in the current directory and stage them
if [ -f "app.py" ]; then
    echo "[+] Staging app.py into $INSTALL_DIR..."
    cp app.py "$INSTALL_DIR/"
fi

if [ -f "install.sh" ]; then
    echo "[+] Staging install.sh into $INSTALL_DIR..."
    cp install.sh "$INSTALL_DIR/"
    chmod +x "$INSTALL_DIR/install.sh"
fi

# 6. Chain execution into the main install script
if [ -f "$INSTALL_DIR/install.sh" ]; then
    echo "[+] Handing over to install.sh..."
    echo "=================================================="
    cd "$INSTALL_DIR"
    exec bash ./install.sh
else
    echo "[-] Error: install.sh could not be found. Please ensure it is in the same directory as setup.sh."
    exit 1
fi