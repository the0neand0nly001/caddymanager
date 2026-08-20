#!/usr/bin/env bash

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run as root (sudo bash)"
  exit 1
fi

# Ensure whiptail is installed
if ! dpkg -s whiptail >/dev/null 2>&1; then
  apt-get update >/dev/null 2>&1 && apt-get install -y whiptail >/dev/null 2>&1
fi

# Whiptail Interactive Prompts
if (whiptail --title "Caddy Manager Setup" --yesno "Would you like to use default settings?" 10 60); then
    INPUT_DOMAINS="home.lab, testhome.lab"
    ADGUARD_IP="192.168.1.100"
    ADMIN_USER="admin"
    ADMIN_PASS="admin"
    DISCORD_WEBHOOK_URL=""
else
    INPUT_DOMAINS=$(whiptail --title "Base Domains" --inputbox "Enter base domains separated by commas:" 10 60 "home.lab, testhome.lab" 3>&1 1>&2 2>&3)
    [ -z "$INPUT_DOMAINS" ] && INPUT_DOMAINS="home.lab, testhome.lab"

    ADGUARD_IP=$(whiptail --title "AdGuard IP" --inputbox "Enter your AdGuard Home IP:" 10 60 "192.168.1.100" 3>&1 1>&2 2>&3)
    [ -z "$ADGUARD_IP" ] && ADGUARD_IP="192.168.1.100"

    ADMIN_USER=$(whiptail --title "Admin Username" --inputbox "Enter admin username:" 10 60 "admin" 3>&1 1>&2 2>&3)
    [ -z "$ADMIN_USER" ] && ADMIN_USER="admin"

    ADMIN_PASS=$(whiptail --title "Admin Password" --passwordbox "Enter admin password:" 10 60 3>&1 1>&2 2>&3)
    [ -z "$ADMIN_PASS" ] && ADMIN_PASS="admin"
fi

if !(whiptail --title "Ready to Install" --yesno "Proceed with installing Caddy Manager?" 10 60); then
    echo "Installation aborted."
    exit 0
fi

echo "[+] Downloading Caddy Manager repository..."
rm -rf /tmp/caddymanager
git clone https://github.com/the0neand0nly001/caddymanager.git /tmp/caddymanager >/dev/null 2>&1

cd /tmp/caddymanager
chmod +x install.sh update.sh uninstall.sh

# Export variables so install.sh can read them automatically without re-prompting
export INPUT_DOMAINS
export ADGUARD_IP
export ADMIN_USER
export ADMIN_PASS
export DISCORD_WEBHOOK_URL

echo "[+] Starting hardened installation..."
./install.sh