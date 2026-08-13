#!/bin/bash
# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run as root (sudo ./uninstall.sh)"
  exit 1
}
echo "[+] Starting Caddy Manager uninstallation..."
CADDYFILE_PATH="/etc/caddy/Caddyfile"
BACKUP_DIR="/root/caddy_backups"
if [ -f "$CADDYFILE_PATH" ]; then
  mkdir -p "$BACKUP_DIR"
  TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
  BACKUP_PATH="$BACKUP_DIR/Caddyfile.bak_$TIMESTAMP"
  cp "$CADDYFILE_PATH" "$BACKUP_PATH"
  echo "[+] Caddyfile successfully backed up to: $BACKUP_PATH"
else
  echo "[!] No Caddyfile found at $CADDYFILE_PATH, skipping backup."
fi
if systemctl list-units --type=service | grep -q "caddy-manager"; then
  echo "[+] Stopping and disabling caddy-manager service..."
  systemctl stop caddy-manager
  systemctl disable caddy-manager
fi
SERVICE_FILE="/etc/systemd/system/caddy-manager.service"
if [ -f "$SERVICE_FILE" ]; then
  echo "[+] Removing systemd service file..."
  rm -f "$SERVICE_FILE"
  systemctl daemon-reload
fi
INSTALL_DIR="/opt/caddy-manager"
if [ -d "$INSTALL_DIR" ]; then
  echo "[+] Removing application files from $INSTALL_DIR..."
  rm -rf "$INSTALL_DIR"
fi
echo "[+] Caddy Manager has been successfully uninstalled!"
if [ -f "$BACKUP_PATH" ]; then
  echo "[+] Remember: Your Caddyfile backup is safe at $BACKUP_PATH"
fi