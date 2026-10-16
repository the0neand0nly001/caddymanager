#!/bin/bash
set -eo pipefail

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
    echo "[-] Please run as root (sudo ./update.sh)"
    exit 1
fi

echo "=================================================="
echo "🔄 Caddy Manager Updater"
echo "=================================================="

echo "[CaddyManager] Checking system dependencies..."
apt-get update >/dev/null
apt-get install -y ca-certificates wget sudo python3 python3-pip >/dev/null
python3 -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11 or newer is required"'

INSTALL_DIR="/opt/caddy-manager"
STATIC_DIR="$INSTALL_DIR/static"
LOG_DIR="$INSTALL_DIR/logs"

mkdir -p "$INSTALL_DIR" "$STATIC_DIR" "$LOG_DIR"

echo "[CaddyManager] 📥 Downloading latest updates from GitHub..."
# Download the modules and templates before replacing the startup file.
APP_FILES=(
    "caddy_manager/__init__.py"
    "caddy_manager/config.py"
    "caddy_manager/domains.py"
    "caddy_manager/dashboard.py"
    "caddy_manager/activity.py"
    "caddy_manager/auth.py"
    "caddy_manager/audit.py"
    "caddy_manager/backend.py"
    "caddy_manager/caddy.py"
    "caddy_manager/monitoring.py"
    "caddy_manager/route_actions.py"
    "caddy_manager/views.py"
    "templates/login.html"
    "templates/icons.html"
    "templates/partials/system.html"
    "templates/partials/activity.html"
    "templates/dashboard.html"
    "templates/css/login.css"
    "templates/css/dashboard.css"
    "templates/js/dashboard.js"
    "templates/js/system.js"
    "templates/js/activity.js"
    "requirements.txt"
)
DOWNLOAD_DIR=$(mktemp -d /tmp/caddy-manager-files.XXXXXX)
trap 'rm -rf -- "$DOWNLOAD_DIR"' EXIT
for app_file in "${APP_FILES[@]}" app.py update.sh uninstall.sh static/icon.png; do
    mkdir -p "$DOWNLOAD_DIR/$(dirname "$app_file")"
    if [ -n "${CADDY_MANAGER_SOURCE_DIR:-}" ]; then
        cp -- "$CADDY_MANAGER_SOURCE_DIR/$app_file" "$DOWNLOAD_DIR/$app_file"
    else
        wget -q -O "$DOWNLOAD_DIR/$app_file" "https://raw.githubusercontent.com/the0neand0nly001/caddymanager/stable/$app_file"
    fi
done

# Install dependencies before replacing the application; failed downloads leave it intact.
python3 -m pip install --break-system-packages -r "$DOWNLOAD_DIR/requirements.txt" >/dev/null
python3 -m compileall -q "$DOWNLOAD_DIR"
cp -R "$DOWNLOAD_DIR/." "$INSTALL_DIR/"

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
caddyman ALL=(ALL) NOPASSWD: /usr/bin/systemctl reload caddy, /usr/bin/systemctl restart caddy, /usr/bin/caddy validate --config /etc/caddy/Caddyfile, /usr/bin/cat /etc/caddy/Caddyfile, /usr/bin/tee /etc/caddy/Caddyfile, /usr/bin/tee -a /etc/caddy/Caddyfile, /usr/bin/cp /var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt *, /usr/bin/chown caddyman\:caddyman *
EOF
chmod 440 "$SUDOERS_FILE"

touch /etc/caddy/Caddyfile
chown -R root:caddy /etc/caddy
chmod 775 /etc/caddy
chmod 664 /etc/caddy/Caddyfile

echo "[CaddyManager] ⚙️ Restarting Caddy Manager service..."
systemctl daemon-reload > /dev/null 2>&1
systemctl restart caddy-manager > /dev/null 2>&1

# Ensure Caddyfile has a default block so Caddy initializes internal TLS
if [ ! -s /etc/caddy/Caddyfile ]; then
    echo "localhost {
        tls internal
    }" > /etc/caddy/Caddyfile
fi

# Restart Caddy to force generation of the local CA certificate
systemctl restart caddy
sleep 2

echo "=================================================="
echo "✔ Caddy Manager successfully updated and restarted!"
echo "=================================================="
