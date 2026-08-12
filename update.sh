#!/bin/bash
cd ~/caddymanager
git pull origin main
cp -r * /opt/caddy-manager/
systemctl restart caddy-manager
echo "Caddy Manager updated and restarted!"
