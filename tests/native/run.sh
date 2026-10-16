#!/bin/bash
set -eo pipefail

# This harness replaces init commands and must only run in a disposable container.
if [ ! -f /.dockerenv ] || [ "${CADDY_MANAGER_NATIVE_TEST:-}" != "1" ]; then
    echo "Run this harness in a disposable Docker container with CADDY_MANAGER_NATIVE_TEST=1."
    exit 1
fi

export DEBIAN_FRONTEND=noninteractive TERM=xterm
apt-get update -qq
apt-get install -y -qq python3 sudo >/tmp/native-dependencies.log 2>&1
install -m 755 /source/tests/native/systemctl.py /usr/bin/systemctl
install -m 755 /source/tests/native/whiptail.sh /usr/local/bin/whiptail

CADDY_MANAGER_SOURCE_DIR=/source bash /source/install.sh >/tmp/native-install.log 2>&1
visudo -cf /etc/sudoers.d/caddyman
python3 /source/tests/native/verify.py install

CADDY_MANAGER_SOURCE_DIR=/source bash /source/update.sh >/tmp/native-update.log 2>&1
visudo -cf /etc/sudoers.d/caddyman
python3 /source/tests/native/verify.py update

cd /source
python3 -m unittest discover -s tests -q
