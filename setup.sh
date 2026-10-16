#!/bin/bash
set -eo pipefail

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo bash setup.sh)."
    exit 1
fi

apt-get update >/dev/null
apt-get install -y ca-certificates git >/dev/null

CHECKOUT_DIR=$(mktemp -d /tmp/caddymanager-setup.XXXXXX)
trap 'rm -rf -- "$CHECKOUT_DIR"' EXIT
git clone --depth 1 --branch stable https://github.com/the0neand0nly001/caddymanager.git "$CHECKOUT_DIR"
cd "$CHECKOUT_DIR"
CADDY_MANAGER_SOURCE_DIR="$CHECKOUT_DIR" bash ./install.sh
