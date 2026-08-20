#!/bin/bash

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
    echo "[-] Please run as root (sudo ./update.sh)"
    exit 1
fi

echo "=================================================="
echo "🔄 Caddy Manager Updater"
echo "=================================================="

INSTALL_DIR="/opt/caddy-manager"
STATIC_DIR="$INSTALL_DIR/static"
LOG_DIR="$INSTALL_DIR/logs"

mkdir -p "$INSTALL_DIR" "$STATIC_DIR" "$LOG_DIR"

echo "[CaddyManager] 📥 Downloading latest updates from GitHub..."
wget -q -O "$INSTALL_DIR/app.py" https://raw.githubusercontent.com/the0neand0nly001/caddymanager/stable/app.py
wget -q -O "$INSTALL_DIR/update.sh" https://raw.githubusercontent.com/the0neand0nly001/caddymanager/stable/update.sh
wget -q -O "$INSTALL_DIR/uninstall.sh" https://raw.githubusercontent.com/the0neand0nly001/caddymanager/stable/uninstall.sh
wget -q -O "$STATIC_DIR/icon.png" https://raw.githubusercontent.com/the0neand0nly001/caddymanager/stable/static/icon.png 2>/dev/null || true

echo "[CaddyManager] 🔑 Restoring script permissions..."
chmod +x "$INSTALL_DIR/update.sh" "$INSTALL_DIR/uninstall.sh"

# Ensure user/group exist and group memberships are intact
id -u caddyman &>/dev/null || useradd -r -s /bin/false caddyman
usermod -aG caddy caddyman

# Re-enforce permissions, ownership, and group mapping on installation and Caddy directories
echo "[CaddyManager] 🔐 Re-enforcing correct file ownership and permissions..."
chown -R caddyman:caddyman "$INSTALL_DIR"
chmod 600 "$INSTALL_DIR/.credentials" 2>/dev/null || true
chmod 644 "$INSTALL_DIR/config.yml" 2>/dev/null || true

# Ensure proper sudoers file for caddyman is enforced during updates
echo "[CaddyManager] 🔑 Updating restricted sudoers privileges..."
SUDOERS_FILE="/etc/sudoers.d/caddyman"
cat << EOF > "$SUDOERS_FILE"
caddyman ALL=(ALL) NOPASSWD: /usr/bin/systemctl reload caddy, /usr/bin/systemctl restart caddy, /usr/bin/caddy validate, /usr/bin/cat /etc/caddy/Caddyfile, /usr/bin/tee /etc/caddy/Caddyfile, /usr/bin/tee -a /etc/caddy/Caddyfile, /usr/bin/cp /var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt *, /usr/bin/chown caddyman\:caddyman *
EOF
chmod 440 "$SUDOERS_FILE"

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

# Ensure Caddyfile has a default block so Caddy initializes internal TLS
if [ ! -s /etc/caddy/Caddyfile ]; then
    echo "localhost {
        tls internal
    }" > /etc/caddy/Caddyfile
fi

# Restart Caddy to force generation of the local CA certificate
systemctl restart caddy
sleep 2