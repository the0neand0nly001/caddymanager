#!/bin/bash

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
    echo "[-] Please run as root (sudo ./update.sh)"
    exit 1
fi

echo "=================================================="
echo "🔄 Caddy Manager Updater"
echo "=================================================="

# Navigate to script directory or fallback to typical path
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || { echo "[-] Failed to change directory."; exit 1; }

echo "[CaddyManager] 📥 Pulling latest changes from stable..."
if ! git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
    echo "[-] Error: This directory is not a Git repository."
    exit 1
fi

# Discard local modifications so updates never block or fail
git reset --hard HEAD > /dev/null 2>&1
git pull origin stable > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "[-] Git pull failed. Please check your internet connection or repository status."
    exit 1
fi

echo "[CaddyManager] 🔑 Restoring script permissions..."
chmod +x update.sh install.sh uninstall.sh > /dev/null 2>&1

INSTALL_DIR="/opt/caddy-manager"
mkdir -p "$INSTALL_DIR"

echo "[CaddyManager] 📁 Updating application files..."
if [ -f "app.py" ]; then
    cp app.py "$INSTALL_DIR/"
    echo "[CaddyManager] ✔ Updated app.py"
fi

if [ -d "static" ]; then
    cp -r static "$INSTALL_DIR/"
    echo "[CaddyManager] ✔ Updated static assets"
fi

# Ensure user/group exist and group memberships are intact
id -u caddyman &>/dev/null || useradd -r -s /bin/false caddyman
usermod -aG caddy caddyman

# Re-enforce permissions, ownership, and group mapping on installation and Caddy directories
echo "[CaddyManager] 🔐 Re-enforcing correct file ownership and permissions..."
chown -R caddyman:caddyman "$INSTALL_DIR"
chmod 600 "$INSTALL_DIR/.credentials" 2>/dev/null
chmod 644 "$INSTALL_DIR/config.yml" 2>/dev/null

touch /etc/caddy/Caddyfile
chown -R root:caddy /etc/caddy
chmod 775 /etc/caddy
chmod 664 /etc/caddy/Caddyfile

echo "[CaddyManager] ⚙️ Restarting Caddy Manager service..."
systemctl daemon-reload > /dev/null 2>&1
systemctl restart caddy-manager > /dev/null 2>&1

echo "=================================================="
echo "✔ Caddy Manager successfully updated and restarted!"
echo "=================================================="