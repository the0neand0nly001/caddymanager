#!/bin/bash

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run as root (sudo ./install.sh)"
  exit 1
fi

echo "=================================================="
echo "🚀 Caddy Reverse Proxy Manager Installer (Hardened)"
echo "=================================================="

# Use exported variables from frontend wizard if available, otherwise fall back to interactive reads
INPUT_DOMAINS=${INPUT_DOMAINS:-$(read -p "[?] Enter your base domains: " d && echo $d)}
INPUT_DOMAINS=${INPUT_DOMAINS:-home.lab, testhome.lab}

ADGUARD_IP=${ADGUARD_IP:-$(read -p "[?] Enter AdGuard IP: " ip && echo $ip)}
ADGUARD_IP=${ADGUARD_IP:-192.168.1.100}

ADMIN_USER=${ADMIN_USER:-$(read -p "[?] Enter admin username: " u && echo $u)}
ADMIN_USER=${ADMIN_USER:-admin}

if [ -z "${ADMIN_PASS:-}" ]; then
  read -s -p "[?] Enter admin password: " ADMIN_PASS
  echo
fi
ADMIN_PASS=${ADMIN_PASS:-admin}

DISCORD_WEBHOOK_URL=${DISCORD_WEBHOOK_URL:-""}

# ---> (Keep the rest of your hardened installation logic down here as you wrote it!)