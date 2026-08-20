#!/usr/bin/env bash

# Copyright (c) 2026 Your Name
# License: MIT
# Purpose: Create an LXC Container and install Caddy Manager

$SD && exit 0
bash -c "$(wget -qLO - https://github.com/community-scripts/ProxmoxVE/raw/main/misc/build.func)" || {
  echo "[-] Failed to load build functions."
  exit 1
}

# 1. Define App Defaults for the Container
APP="Caddy-Manager"
var_cpu="1"
var_ram="1024"
var_disk="4"
var_os="debian"
var_version="12"

# 2. Run standard variables setup
variables

# 3. Interactive Whiptail Settings (Prompts for CT ID, RAM, Storage, etc.)
start
settings

# 4. Create the LXC Container on Proxmox
payload

# 5. Run your Hardened Installer inside the newly created container
msg_info "Starting Caddy Manager installation inside container..."
lxc-attach -n "$VMID" -- bash -c "$(wget -qLO - https://raw.githubusercontent.com/theoneandonly001/caddymanager/main/install.sh)"

msg_ok "Caddy Manager container successfully created and configured!"
echo -e "Access your dashboard at: http://<container-ip>:5000"