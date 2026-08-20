#!/bin/bash

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run as root (sudo bash setup.sh)"
  exit 1
fi

echo "[+] Checking for git..."
if ! command -v git &> /dev/null; then
    echo "[+] Git not found. Installing git..."
    apt-get update > /dev/null 2>&1
    apt-get install -y git > /dev/null 2>&1
fi

echo "[+] Downloading Caddy Manager..."
rm -rf /tmp/caddymanager
git clone https://github.com/the0neand0nly001/caddymanager.git /tmp/caddymanager

cd /tmp/caddymanager
chmod +x install.sh update.sh uninstall.sh

echo "[+] Starting installer..."
./install.sh
# 1