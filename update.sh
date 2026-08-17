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

git pull origin stable > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "[-] Git pull failed. Please check your internet connection or repository status."
    exit 1
fi

echo "[CaddyManager] 📁 Backing up existing configuration..."
INSTALL_DIR="/opt/caddy-manager"
BACKUP_DIR="/tmp/caddy-manager-backup"
mkdir -p "$BACKUP_DIR"

if [ -f "$INSTALL_DIR/config.yml" ]; then
    cp "$INSTALL_DIR/config.yml" "$BACKUP_DIR/"
fi
if [ -f "$INSTALL_DIR/.credentials" ]; then
    cp "$INSTALL_DIR/.credentials" "$BACKUP_DIR/"
fi

echo "[CaddyManager] 📁 Updating application files..."
mkdir -p "$INSTALL_DIR"
# Copy everything except hidden git files to the installation directory
rsync -av --exclude='.git' ./ "$INSTALL_DIR/" > /dev/null 2>&1

echo "[CaddyManager] 📁 Restoring configuration..."
if [ -f "$BACKUP_DIR/config.yml" ]; then
    cp "$BACKUP_DIR/config.yml" "$INSTALL_DIR/"
fi
if [ -f "$BACKUP_DIR/.credentials" ]; then
    cp "$BACKUP_DIR/.credentials" "$INSTALL_DIR/"
fi
rm -rf "$BACKUP_DIR"

# Update python dependencies if a requirements file exists
if [ -f "$INSTALL_DIR/requirements.txt" ]; then
    echo "[CaddyManager] 🐍 Updating python dependencies..."
    if [ -f "$INSTALL_DIR/venv/bin/pip" ]; then
        /opt/caddy-manager/venv/bin/pip install -r /opt/caddy-manager/requirements.txt > /dev/null 2>&1
    else
        pip3 install -r /opt/caddy-manager/requirements.txt > /dev/null 2>&1
    fi
fi

echo "[CaddyManager] ⚙️ Restarting Caddy Manager service..."
systemctl daemon-reload > /dev/null 2>&1
systemctl restart caddy-manager > /dev/null 2>&1

echo "=================================================="
echo "✔ Caddy Manager successfully updated and restarted!"
echo "=================================================="