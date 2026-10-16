# Caddy Manager

A web interface for Caddy reverse-proxy routes, base domains, backend reachability and audit history.

![Version](https://img.shields.io/badge/version-2.0.0-318c70)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)

## Features

- Add and remove routes using a hostname, backend IP, port and protocol.
- Manage base domains and choose internal HTTPS, automatic HTTPS or HTTP-only defaults for new routes.
- Check individual backend ports or all configured targets, with route/domain/health totals and labelled status dots.
- View manager-process CPU and memory usage, Caddy status and combined monitoring warnings.
- Read recent audit entries or load older history from the Activity tab.
- Download Caddy's public root CA certificate for internal HTTPS.
- Use a collapsible desktop sidebar and mobile navigation drawer.

Changing or removing a base domain leaves existing routes unchanged. Backend checks confirm TCP reachability; they do not measure application health or uptime. Existing route validation/reload and nested-block-removal limitations are documented in [CODEBASE.md](CODEBASE.md).

## Linux / Proxmox LXC

Run on a Debian 12 or Debian 13 container with systemd. As root:

```sh
apt-get update
apt-get install -y curl
bash -c "$(curl -fsSL https://raw.githubusercontent.com/the0neand0nly001/caddymanager/stable/setup.sh)"
```

The setup dialogs configure domains, DNS display settings and admin credentials. The dashboard runs at `http://<LXC-IP>:5000`. See [INSTALL.md](INSTALL.md) for installation, updates, paths and service controls.

## Docker Compose

```sh
git clone --branch stable https://github.com/the0neand0nly001/caddymanager.git
cd caddymanager
cp .env.example .env
# Edit .env for your credentials, domains and host ports.
docker compose -f docker-compose.yml up -d --build
```

The default manager port is 5000; Caddy uses 80 and 443. Saved configuration, credentials and certificates live in named volumes. First-start credentials default to `admin` / `admin` if you do not set alternatives. Changing `.env` does not overwrite already saved credentials or configuration.

See [DOCKER.md](DOCKER.md) for persistent data, local-only previews, Portainer and Komodo. Compose builds the manager from source; there is no published manager registry image required by this setup.

## Configuration

The native installer creates `/opt/caddy-manager/config.yml`; Docker creates `/data/config.yml` in the manager volume. The generic [config.example.yml](config.example.yml) describes the available settings. Real configuration, `.env`, credentials, logs and private keys are excluded from Git.

Internal HTTPS requires clients to trust Caddy's local CA. Automatic public HTTPS requires suitable domain names, DNS and certificate validation access. A tunnel that terminates HTTPS may forward HTTP to Caddy; select the frontend mode to match that forwarding connection. Backend Protocol separately controls Caddy's connection to the service.

## Development

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

[CODEBASE.md](CODEBASE.md) describes the source layout, behaviour retained from the previous version and deployment checks. [DOCUMENTATION.md](DOCUMENTATION.md) covers everyday use.

Developed by evansinnott & The0neAnd0nly. Built with Flask, Python and Caddy.
