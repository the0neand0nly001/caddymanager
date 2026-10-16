# Linux / LXC installation

Use a Debian 12 or Debian 13 container with systemd, Python 3.11 or newer, and network access to the package repositories and GitHub. Run the installer as root. Docker is not required inside the LXC.

## Fresh installation

```sh
apt-get update
apt-get install -y curl
bash -c "$(curl -fsSL https://raw.githubusercontent.com/the0neand0nly001/caddymanager/stable/setup.sh)"
```

Setup clones the `stable` branch and installs its matching application files. The dialogs let you set base domains, DNS server, admin username/password and an optional Discord webhook. Default credentials are `admin` / `admin`; choose your own credentials through the custom setup before allowing access to the dashboard.

The installer installs Caddy when missing, creates the `caddyman` service user, installs Python dependencies from `requirements.txt`, writes configuration and hashed credentials, and registers `caddy-manager.service`. It installs `sudo` and the restricted Caddy command rules needed by the application. Downloads and dependencies must succeed before application files are replaced.

Open `http://<LXC-IP>:5000`. Set your DNS rewrites to the LXC's IP for local routes. Internal HTTPS clients must trust the Caddy root CA, available from the Routes page. Public tunnels retain their own forwarding configuration.

## Update an existing installation

For the first upgrade from the older single-file application, fetch the current updater first:

```sh
wget -O /tmp/caddy-manager-update.sh https://raw.githubusercontent.com/the0neand0nly001/caddymanager/stable/update.sh
bash /tmp/caddy-manager-update.sh
```

After that, the installed updater can be used directly:

```sh
bash /opt/caddy-manager/update.sh
```

Updates install the complete package and templates, refresh dependencies and restart the services. They preserve `config.yml`, `.credentials`, the audit log and existing Caddyfile contents. Keep a backup of those files and Caddy's data directory before migrating to another host.

The systemd startup remains `/usr/bin/python3 app.py`, with `/opt/caddy-manager` as the working directory. Python dependencies use the system interpreter and pip's `--break-system-packages` option, matching the existing native deployment model.

## Paths and service controls

| Path | Contents |
| --- | --- |
| `/opt/caddy-manager/config.yml` | Saved settings and base-domain defaults. |
| `/opt/caddy-manager/.credentials` | Admin username and password hash. Keep private. |
| `/opt/caddy-manager/logs/audit.log` | Recorded actions. |
| `/etc/caddy/Caddyfile` | Proxy routes. |
| `/var/lib/caddy/.local/share/caddy` | Caddy's native data, certificates and private keys. |

```sh
systemctl status caddy-manager caddy
journalctl -u caddy-manager -n 50
systemctl restart caddy-manager
```

Use `config.example.yml` as a reference; the local `config.yml`, credentials, logs and certificates are excluded from Git. For Docker Compose, Portainer or Komodo, use [DOCKER.md](DOCKER.md).

## Testing the native installer

The native smoke harness runs only in a disposable Docker container. It installs real Debian packages, runs the application as `caddyman`, exercises actual sudo rules and Caddy validation/reload, checks HTTPS proxying and certificate download, then verifies that an update preserves saved state:

```sh
docker run --rm -e CADDY_MANAGER_NATIVE_TEST=1 --mount type=bind,source="$(pwd)",target=/source,readonly debian:12-slim bash /source/tests/native/run.sh
```

The harness supplies deterministic setup answers and a small init adapter because a regular Docker container does not boot systemd. It does not replace an end-to-end test on a Proxmox LXC host.
