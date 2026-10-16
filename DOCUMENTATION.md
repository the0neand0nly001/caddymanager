# Caddy Manager 2.0.0

## Install and update

Use [INSTALL.md](INSTALL.md) for a native Debian / LXC installation and [DOCKER.md](DOCKER.md) for Docker Compose, Portainer or Komodo. Native installations use systemd; Docker runs the manager and Caddy in separate services.

## System Dashboard

The dashboard reports all configured routes, base domains, reachable and unreachable backend ports, unchecked routes and routes without usable targets. Use Check all or the Check button beside a route. Checks run when the dashboard opens and every minute while visible. Results include their last-check time.

Green means reachable, red means unreachable, amber indicates a pending check and grey indicates a neutral or unchecked state. Text labels remain visible. A reachable TCP port is not proof that an application is healthy, and a configured route is not proof that its hostname resolves or that TLS is valid.

The combined status area separates manager connectivity, Caddy availability and backend reachability. Resource values measure the manager process, not the whole host or Caddy.

## Routes

To add a route, enter its subdomain name, select a base domain, supply a reachable backend IP and port, and choose the backend HTTP or HTTPS protocol. The frontend HTTPS/HTTP mode comes from the base domain's default.

The existing HTTPS backend behaviour retains `tls_insecure_skip_verify`; it does not validate the backend certificate. Read the retained route-add failure-handling and nested HTTPS-block-removal limitations in [CODEBASE.md](CODEBASE.md) before relying on automatic rollback or deleting complex blocks.

Route filters and Show Targets preferences are saved in the browser. Download Root CA retrieves only Caddy's public root certificate, which clients can install to trust internal HTTPS. Private CA keys stay in Caddy's data directory or Docker volume.

## Base domains

Add a domain name without a protocol, port, wildcard or path. Each base domain has a default for new routes:

- Internal HTTPS uses Caddy's local CA and preserves the previous default.
- Automatic HTTPS leaves certificate handling to Caddy; public certificates require eligible names and working DNS/validation access.
- HTTP only serves HTTP at Caddy, which can suit an HTTPS tunnel forwarding to an HTTP service.

Saving a default affects new routes only. Removing a base domain leaves its existing routes active and available for removal from Routes. An empty domain list is allowed, but new-route creation is disabled until a base domain is added.

These controls do not create DNS records or change public tunnel settings. For example, `service.example.com` uses `example.com` as its base domain and `service` as its route name.

## Activity

Activity reads the existing audit log, newest first, with Refresh and Load older entries controls. Timestamps use the server's clock. Login events, route changes, base-domain changes and CA downloads use the existing logger. Reading the log or checking backend health does not create audit events.

## Configuration and private files

`config.example.yml` is a generic reference. Actual configuration and credentials are installation-specific and are not shipped in the repository. Domain saves preserve unrelated YAML values but rewrite formatting and comments.

Keep `.env`, `config.yml`, `.credentials`, the session signing key, audit logs and Caddy certificate/private-key data private. Credentials contain the username and a password hash; reading that file does not reveal or reset the password.

For Docker, first-start environment values only seed missing files. For native installs, the setup dialog creates the files and the updater preserves them. See the deployment guides before moving saved state to another host.
