#!/bin/bash

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run as root (sudo bash install.sh)"
  exit 1
fi

echo "=================================================="
echo "🚀 Caddy Reverse Proxy Manager Installer (Hardened)"
echo "=================================================="

if ! dpkg -s whiptail >/dev/null 2>&1; then
  apt-get update >/dev/null 2>&1 && apt-get install -y whiptail >/dev/null 2>&1
fi

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

    if (whiptail --title "Discord Webhook" --yesno "Would you like to link a Discord webhook for security alerts?" 10 60); then
        DISCORD_WEBHOOK_URL=$(whiptail --title "Discord Webhook" --inputbox "Enter your Discord Webhook URL:" 10 60 3>&1 1>&2 2>&3)
    fi
fi

if !(whiptail --title "Ready to Install" --yesno "Proceed with installing Caddy Manager?" 10 60); then
    echo "Installation aborted."
    exit 0
fi

clear

echo "[CaddyManager] 📦 Checking and installing Caddy..."
if ! command -v caddy &> /dev/null; then
    apt-get update > /dev/null 2>&1
    apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl > /dev/null 2>&1
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg > /dev/null 2>&1
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list > /dev/null 2>&1
    apt-get update > /dev/null 2>&1
    apt-get install -y caddy > /dev/null 2>&1
fi

echo "[CaddyManager] 👤 Creating dedicated system user and group memberships..."
id -u caddyman &>/dev/null || useradd -r -s /bin/false caddyman
usermod -aG caddy caddyman

echo "[CaddyManager] 🐍 Installing required Python dependencies..."
apt-get update > /dev/null 2>&1
apt-get install -y python3-pip python3-yaml python3-flask python3-limits python3-flask-limiter python3-psutil > /dev/null 2>&1
pip3 install flask-wtf flask-limiter psutil --break-system-packages > /dev/null 2>&1

echo "[CaddyManager] 📁 Setting up application and downloading files from GitHub..."
INSTALL_DIR="/opt/caddy-manager"
LOG_DIR="$INSTALL_DIR/logs"
STATIC_DIR="$INSTALL_DIR/static"

mkdir -p "$INSTALL_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$STATIC_DIR"

wget -q -O "$INSTALL_DIR/app.py" https://raw.githubusercontent.com/the0neand0nly001/caddymanager/stable/app.py
wget -q -O "$INSTALL_DIR/update.sh" https://raw.githubusercontent.com/the0neand0nly001/caddymanager/stable/update.sh 2>/dev/null || true
wget -q -O "$INSTALL_DIR/uninstall.sh" https://raw.githubusercontent.com/the0neand0nly001/caddymanager/stable/uninstall.sh 2>/dev/null || true
wget -q -O "$STATIC_DIR/icon.png" https://raw.githubusercontent.com/the0neand0nly001/caddymanager/stable/static/icon.png 2>/dev/null || true

chmod +x "$INSTALL_DIR/update.sh" "$INSTALL_DIR/uninstall.sh"

echo "[CaddyManager] ⚙️ Writing configuration files..."
CONFIG_FILE="$INSTALL_DIR/config.yml"

YAML_DOMAINS=""
IFS=',' read -ra ADDR <<< "$INPUT_DOMAINS"
for i in "${ADDR[@]}"; do
    clean_domain=$(echo "$i" | xargs)
    YAML_DOMAINS+="  - \"$clean_domain\""$'\n'
done

cat << EOF > "$CONFIG_FILE"
WEBSERVER_PORT: 5000
CADDYFILE_PATH: "/etc/caddy/Caddyfile"
DOMAINS:
$YAML_DOMAINS
ADGUARD_IP: "$ADGUARD_IP"
DISCORD_WEBHOOK_URL: "$DISCORD_WEBHOOK_URL"
EOF

python3 -c "
from werkzeug.security import generate_password_hash
pass_hash = generate_password_hash('$ADMIN_PASS')
with open('$INSTALL_DIR/.credentials', 'w') as f:
    f.write('$ADMIN_USER\n' + pass_hash)
" > /dev/null 2>&1

chown -R caddyman:caddyman "$INSTALL_DIR"

echo "[CaddyManager] 📁 Setting up Caddyfile and permissions..."
touch /etc/caddy/Caddyfile
chown -R root:caddy /etc/caddy
chmod 775 /etc/caddy
chmod 664 /etc/caddy/Caddyfile

chmod 600 "$INSTALL_DIR/.credentials"
chmod 644 "$INSTALL_DIR/config.yml"

echo "[CaddyManager] 🔑 Configuring restricted sudoers privileges for Caddy operations..."
SUDOERS_FILE="/etc/sudoers.d/caddyman"
cat << EOF > "$SUDOERS_FILE"
caddyman ALL=(ALL) NOPASSWD: /usr/bin/systemctl reload caddy, /usr/bin/systemctl restart caddy, /usr/bin/caddy validate, /usr/bin/cat /etc/caddy/Caddyfile, /usr/bin/tee /etc/caddy/Caddyfile, /usr/bin/tee -a /etc/caddy/Caddyfile
EOF
chmod 440 "$SUDOERS_FILE"

# Fix Caddy CA certificate permissions for download
if [ -d "/var/lib/caddy/.local/share/caddy/pki/authorities/local" ]; then
    sudo chmod -R +rx /var/lib/caddy/.local/share/caddy/pki/authorities/local/
fi

echo "[CaddyManager] 🔌 Configuring systemd service..."
SERVICE_FILE="/etc/systemd/system/caddy-manager.service"
cat << EOF > "$SERVICE_FILE"
[Unit]
Description=Caddy Reverse Proxy Manager
After=network.target caddy.service

[Service]
User=caddyman
Group=caddyman
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 app.py
Restart=always
NoNewPrivileges=false
ProtectSystem=false
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/sudoers.d/caddy-manager > /dev/null << 'EOF'
%sudo ALL=(ALL) NOPASSWD: /usr/bin/systemctl reload caddy, /usr/bin/caddy validate
EOF

sudo chmod 0440 /etc/sudoers.d/caddy-manager

systemctl daemon-reload > /dev/null 2>&1
systemctl enable caddy-manager > /dev/null 2>&1
systemctl restart caddy-manager > /dev/null 2>&1

IP_ADDR=$(hostname -I | awk '{print $1}')
echo "=================================================="
echo "✔ Installation Complete! Hardened Caddy Manager is running."
echo "✔ Access it at: http://${IP_ADDR}:5000"
echo "--------------------------------------------------"
echo "⚠️  REMINDER: Remember to set up a DNS rewrite in AdGuard!"
echo "     - Set the Domain/Rewrite to your wildcard domain."
echo "=================================================="