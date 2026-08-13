#!/bin/bash
cd ~/caddymanager
git pull origin stable
cp -r * /opt/caddy-manager/
systemctl restart caddy-manager
echo "Caddy Manager updated and restarted!"
