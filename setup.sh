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

# 1. Create necessary directories
echo "[+] Creating application directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/static"

# 2. Fix Caddy configuration folder permissions if they exist
if [ -f "$CADDY_CONFIG_DIR/Caddyfile" ]; then
    chown -R root:caddy "$CADDY_CONFIG_DIR"
    chmod 640 "$CADDY_CONFIG_DIR/Caddyfile"
fi

# 3. Set directory ownership for the install path
chown -R root:root "$INSTALL_DIR"
chmod 755 "$INSTALL_DIR"

# 4. Copy files from the current local repository directory into /opt/caddy-manager
echo "[+] Copying application files from local repository..."
if [ -f "app.py" ]; then
    cp app.py "$INSTALL_DIR/"
    echo "[+] Copied app.py"
fi

if [ -f "install.sh" ]; then
    cp install.sh "$INSTALL_DIR/"
    chmod +x "$INSTALL_DIR/install.sh"
    echo "[+] Copied install.sh"
fi

if [ -d "static" ]; then
    cp -r static "$INSTALL_DIR/"
    echo "[+] Copied static assets"
fi

# 5. Execute install.sh from the destination directory
if [ -f "$INSTALL_DIR/install.sh" ]; then
    echo "[+] Handing over to install.sh..."
    echo "=================================================="
    cd "$INSTALL_DIR"
    exec bash ./install.sh
else
    echo "[-] Error: install.sh could not be found to launch installation."
    exit 1
fi