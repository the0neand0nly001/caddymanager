# Docker Compose

The stack runs Caddy Manager and Caddy as separate services. The dashboard, forms, authentication and API endpoints are shared with the Linux installation. Container deployments use Caddy's private admin API for configuration reloads and public CA downloads.

## Start from source

Copy `.env.example` to `.env`, choose your admin credentials, base domains and ports, then run from the repository root:

```sh
docker compose -f docker-compose.yml up -d --build
```

With the example defaults, the manager is at `http://localhost:5000`; Caddy uses ports 80 and 443. First-start credentials default to `admin` / `admin` if no alternatives are supplied.

For a preview restricted to the local computer, use these port settings in `.env`:

```dotenv
BIND_ADDRESS=127.0.0.1
MANAGER_PORT=5080
CADDY_HTTP_PORT=8080
CADDY_HTTPS_PORT=8443
```

Then open `http://127.0.0.1:5080`. HTTPS routes in this preview use port 8443. The default HTTP-to-HTTPS redirect assumes standard port 443, so open an HTTPS route directly on port 8443 when using these alternate preview ports. Normal deployments should use 80 and 443.

For a development preview, you can use the project name `caddymanager-preview`. Manage that instance with:

```sh
docker compose -p caddymanager-preview -f docker-compose.yml ps
docker compose -p caddymanager-preview -f docker-compose.yml logs --tail 50
docker compose -p caddymanager-preview -f docker-compose.yml up -d --build
docker compose -p caddymanager-preview -f docker-compose.yml stop
```

## Configuration and saved state

| Volume | Contents |
| --- | --- |
| `manager_data` | `config.yml`, `.credentials`, the session signing key, audit logs and downloaded public root certificate. |
| `caddy_files` | The shared Caddyfile, writable by the manager and read-only in the Caddy container. |
| `caddy_data` | Caddy certificates, private keys and local certificate authority. |
| `caddy_config` | Caddy's saved configuration. |

The manager creates configuration and credentials only if they are missing. Changing `.env` later does not overwrite saved configuration or credentials. Container recreation preserves these named volumes. Keep the same Compose project name to reuse them. `docker compose down -v` removes the volumes and their saved state.

First-start settings are `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `CADDY_DOMAINS` (comma separated), `ADGUARD_IP` and optional `DISCORD_WEBHOOK_URL`. Port and bind-address changes apply when containers are recreated.

Use **Base domains** in the sidebar to add or remove domain choices and save a TLS default for new routes. These settings are stored in `/data/config.yml` on the existing `manager_data` volume and survive container recreation. `CADDY_DOMAINS` seeds only the first start; it does not override saved domain choices.

- **Internal HTTPS** keeps the existing behaviour: Caddy issues certificates using its local CA.
- **Automatic HTTPS** omits `tls internal` and leaves certificate handling to Caddy. Public certificates require eligible names, suitable DNS and certificate validation access. See [Caddy's automatic HTTPS documentation](https://caddyserver.com/docs/automatic-https).
- **HTTP only** uses an explicit HTTP site address. This suits a tunnel that terminates public HTTPS and forwards HTTP to Caddy. It does not change your tunnel configuration.

For example, a forwarded hostname `service.example.com` uses `example.com` as the base domain and `service` as the route name, provided the tunnel forwards that hostname to Caddy. Select the frontend mode to match the tunnel's connection to Caddy; Backend Protocol separately controls Caddy's connection to Jellyfin. Leave a working tunnel and its existing routes unchanged until its forwarding protocol is confirmed.

Changing a domain's default affects new routes only. Removing a domain leaves its existing routes active and removable from Routes. Domain management does not create DNS records, issue certificates by itself or modify existing Caddyfile blocks. Configuration saves preserve other values but rewrite YAML formatting and comments.

To edit saved configuration without changing the UI:

```sh
docker compose -f docker-compose.yml cp manager:/data/config.yml ./docker-config.yml
# Edit docker-config.yml locally.
docker compose -f docker-compose.yml cp ./docker-config.yml manager:/data/config.yml
```

Keep `CADDYFILE_PATH: /etc/caddy/Caddyfile` and `WEBSERVER_PORT: 5000` inside the container. Change the published manager port through `MANAGER_PORT`. Configuration is read on demand. Back up credentials and the certificate authority before any migration to another host.

The existing route form accepts IP addresses. Use a backend IP reachable from the Caddy container, such as the server's LAN address. `127.0.0.1` points to the container itself, and Docker service names are not accepted by the existing IP-address validation. Keep your DNS rewrites pointing at the host running Caddy.

Download the root CA through the existing dashboard control and install it on client devices that need to trust internal HTTPS. The manager retrieves only the public certificate through the admin API; it does not mount Caddy's private-key volume.

## Portainer and Komodo

Use the same `docker-compose.yml` on a Docker Standalone host. Build the manager image on that host before deploying a local stack:

```sh
docker build -t caddymanager:2.0.0 .
```

- **Portainer:** create a Stack and supply `docker-compose.yml`. The local image must already exist on the selected Docker host; keep forced image pulling off for that local tag. Supply the desired environment settings in the Stack configuration.
- **Komodo:** create a Compose Stack on the target server, using the repository's `docker-compose.yml` and its build context, or preload the local image on that server first.

For distribution without building on each host, export and load the images:

```sh
docker save -o caddymanager-images.tar caddymanager:2.0.0 caddy:2.11.7
docker load -i caddymanager-images.tar
docker compose -f docker-compose.yml up -d --no-build --pull never
```

A registry image is another future option: publish a manager image and set `CADDY_MANAGER_IMAGE` to that tag. The Compose file builds the manager locally; it does not require a published manager image. A stack that uses the local image cannot be pulled from another computer until it is built, loaded or published there.

The stack does not mount the Docker socket and does not publish Caddy's admin port 2019. That endpoint is reachable only through the stack's Docker network.

## How the container differs

`CADDY_MANAGER_DATA_DIR=/data` redirects persistent manager files away from the application source. `CADDY_ADMIN_URL=http://caddy:2019` selects direct shared-file access and API reloads. Without these settings, the installation-root paths and existing sudo/systemd commands remain in use.

Docker mode submits the Caddyfile to `/adapt` for syntax adaptation, then `/load` for runtime validation and reload. The add/remove form logic, including the previously identified failure-handling and nested-block-removal limitations, is retained. The UI redesign changes navigation and presentation, not the Caddyfile parser or those decisions.

The manager uses a shell-free Minimus Python 3.13 runtime and one Gunicorn worker with four threads. Dependencies are installed in a separate build stage. The runtime runs as UID 1000. Registry login is optional and can raise pull limits for an existing Minimus account; credentials do not belong in the Dockerfile.

## Verification

The System Dashboard reports Caddy admin-API availability separately from manager connectivity and backend TCP reachability. A backend may be reachable while its application is unhealthy; a route without a proxy target is excluded from checks and listed under No target. The resource section measures the manager process only. Activity reads the existing audit log on its own tab, with refresh and older-entry controls. These monitoring actions do not change Caddy routes or tunnel settings.

Run the unit tests with the application dependencies installed:

```sh
python -m unittest discover -s tests -v
```

The Docker integration check uses temporary HTTP and self-signed HTTPS backends. It needs Docker, Python and OpenSSL (Git for Windows' bundled OpenSSL is detected automatically):

```sh
python tests/docker_smoke.py --project caddymanager-preview --manager-url http://127.0.0.1:5080 --proxy-port 8443 --recreate
```

It checks base-domain add/update/remove, duplicate rejection, real HTTP-only proxying, automatic-HTTPS adaptation without requesting public certificates, login, real metrics, CA download, backend health, HTTP/HTTPS upstreams, HTTP route removal, rejected reloads and state after recreation. Temporary domains, routes and the test backend are removed afterwards; the original configuration and Caddyfile are restored. Run this exclusively on a test stack with no concurrent edits: `--recreate` restarts that named stack. The default HTTP proxy port is 8080; override it with `--http-proxy-port` if needed.

References: [Caddy API](https://caddyserver.com/docs/api), [Caddy Compose deployment](https://caddyserver.com/docs/running#docker-compose), [Portainer Stacks](https://docs.portainer.io/user/docker/stacks/add), [Komodo Stacks](https://komo.do/docs/resources#stack), [Minimus Python versions](https://images.minimus.io/images/python/lines/3.13).
