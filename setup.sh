#!/bin/bash

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run as root (sudo bash setup.sh)."
  exit 1
fi

INSTALL_DIR="/opt/caddy-manager"
CADDY_CONFIG_DIR="/etc/caddy"

echo "[+] Setting up Caddy Manager environment and permissions..."

# 1. Create necessary directories if they don't exist
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/static"

# 2. Fix ownership and permissions for Caddy files and the install directory
# Caddy often runs under its own user, so ensure proper access to the Caddyfile
if [ -f "$CADDY_CONFIG_DIR/Caddyfile" ]; then
    chown -R root:caddy "$CADDY_CONFIG_DIR"
    chmod 640 "$CADDY_CONFIG_DIR/Caddyfile"
fi

# 3. Set proper permissions on the installation directory
chown -R root:root "$INSTALL_DIR"
chmod 755 "$INSTALL_DIR"

# Ensure runtime credential or config files have secure permissions if they exist
if [ -f "$INSTALL_DIR/.credentials" ]; then
    chmod 600 "$INSTALL_DIR/.credentials"
fi

if [ -f "$INSTALL_DIR/config.yml" ]; then
    chmod 644 "$INSTALL_DIR/config.yml"
fi

echo "[+] Permissions configured successfully."

# 4. Chain into the main install/launch sequence
if [ -f "$INSTALL_DIR/install.sh" ]; then
    echo "[+] Launching install.sh..."
    chmod +x "$INSTALL_DIR/install.sh"
    bash "$INSTALL_DIR/install.sh"
else
    echo "[!] install.sh not found in $INSTALL_DIR. Environment is prepped and ready."
fi