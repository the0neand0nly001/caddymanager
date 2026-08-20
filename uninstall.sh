#!/bin/bash

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run as root (sudo bash uninstall.sh)"
  exit 1
fi

echo "=================================================="
echo "🗑️ Caddy Reverse Proxy Manager Uninstaller"
echo "=================================================="

read -p "Are you sure you want to completely remove Caddy Manager and its files? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstall aborted."
    exit 0
fi

echo "[+] Stopping and disabling services..."
sudo systemctl stop caddy-manager >/dev/null 2>&1 || true
sudo systemctl disable caddy-manager >/dev/null 2>&1 || true

echo "[+] Removing systemd service and daemon reload..."
sudo rm -f /etc/systemd/system/caddy-manager.service
sudo systemctl daemon-reload

echo "[+] Removing sudoers configurations..."
sudo rm -f /etc/sudoers.d/caddyman
sudo rm -f /etc/sudoers.d/caddy-manager

echo "[+] Removing application directory..."
sudo rm -rf /opt/caddy-manager
sudo rm -rf /tmp/caddymanager

echo "[+] Removing dedicated system user (caddyman)..."
userdel caddyman >/dev/null 2>&1 || true

echo "=================================================="
echo "✔ Caddy Manager has been completely uninstalled."
echo "Note: Caddy itself and /etc/caddy/Caddyfile were left intact."
echo "=================================================="