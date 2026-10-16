# Caddy Manager 2.0.0

The Linux application still starts with `python3 app.py`. Routes, form fields and JSON responses are unchanged. Version 2.0.0 now also includes Docker Compose support and a dashboard redesign requested after the initial refactor. See [DOCKER.md](DOCKER.md) for container deployment.

## File layout

| File | Responsibility |
| --- | --- |
| `app.py` | Create the application and start the server on the configured port. |
| `caddy_manager/__init__.py` | Set up Flask, sessions, CSRF protection and rate limits; register request handlers. |
| `caddy_manager/config.py` | Resolve installation paths and load YAML configuration. |
| `caddy_manager/domains.py` | Validate base domains and persist defaults for new routes. |
| `caddy_manager/auth.py` | Read credentials and handle login/logout. |
| `caddy_manager/audit.py` | Write audit entries and send configured Discord alerts. |
| `caddy_manager/caddy.py` | Read/write the Caddyfile, parse routes and format route blocks. |
| `caddy_manager/backend.py` | Validate/reload Caddy and retrieve public certificates through the native commands or container API. |
| `caddy_manager/route_actions.py` | Validate add/remove forms, run Caddy commands and set response messages. |
| `caddy_manager/monitoring.py` | Sample process metrics and check backend TCP connections. |
| `caddy_manager/dashboard.py` | Read Caddy status and configuration totals; check only configured backend targets with bounded concurrency. |
| `caddy_manager/activity.py` | Read bounded pages of the existing audit log, newest first. |
| `caddy_manager/views.py` | Handle the dashboard, JSON endpoints, certificate downloads and CSRF errors. |
| `templates/` | Login and dashboard HTML, with separate CSS and JavaScript source files. |
| `static/icon.png` | The existing favicon. |
| `tests/` | Behaviour checks and rendered-page fingerprints from version 1.5.0. |

CSS and JavaScript are included through Jinja inside the pages' `<style>` and `<script>` elements. The dashboard uses a persistent desktop sidebar, a mobile drawer and a shared SVG icon macro. View settings reuse the domain-filter and target-visibility preferences. Existing local-storage keys, CSRF handling and polling intervals are retained.

`config.yml`, `.credentials`, `logs/audit.log` and the downloaded `root.crt` remain relative to the installation root unless `CADDY_MANAGER_DATA_DIR` selects a persistent container directory. Configuration is still read on demand, and credentials are re-read by the login handler. Metrics still measure the manager process.

Base domains are managed on the **Base domains** page. `DOMAINS` remains a list of names; the optional `DOMAIN_TLS` mapping stores `internal`, `auto` or `http` for each domain. Existing configurations, including the legacy `DOMAIN` key, default to internal HTTPS. An empty `DOMAINS` list is supported and disables new-route creation until a domain is added. Domain updates read the latest configuration under a process lock, preserve other settings and atomically replace the YAML file with its permissions retained. Saving rewrites YAML formatting and comments. Domain changes do not write or reload the Caddyfile; each new route copies its domain's current TLS default. Existing routes remain unchanged, including when their base domain is removed.

The frontend TLS mode and backend protocol are independent. HTTP-only frontend routes use an explicit `http://` site address; their removal consumes that prefix too. The existing limitation with nested HTTPS upstream blocks remains unchanged.

The System Dashboard has a route health table, six totals, a compact manager-resource section and one combined status area. `/api/overview` reports configuration and Caddy status (a read-only admin API request in Docker, or `systemctl is-active` natively). `/api/services/check` checks all configured targets or one configured domain; it never accepts a caller-supplied target. Duplicate targets are checked once, with at most eight concurrent TCP connections and a two-second connection timeout. Reachability does not imply application health or validate TLS. Results live in the open browser; there is no invented uptime or historical monitoring. Checks run on dashboard entry and every minute while that page is visible. Overview and manager metrics update every ten and three seconds while the document is visible.

Activity has its own tab and authenticated `/api/activity` endpoint. It reads up to 50 entries per page using a byte-offset cursor, with a 1 MiB read bound. Details beyond 8 KiB are explicitly marked as truncated. The original file is not changed. Invalid legacy lines are shown as unparsed entries, incomplete lines still being appended are deferred, and permission errors are reported instead of presented as an empty log. Timestamps retain the server clock used by the existing logger. Missing proxy targets are informational; unreachable backends or unavailable monitoring generate warnings in the combined status area.

## Development

From the repository root, install the application dependencies into a virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

On Windows, activate the environment with `.venv\Scripts\Activate.ps1`.

The unit tests simulate Caddy commands, socket connections and webhook requests. Their configuration, credentials and logs live in temporary directories. They do not operate on the host's Caddy service. Login fingerprints retain the original page; dashboard checks cover the existing controls, data and escaping after the redesign. The optional Docker smoke test exercises a real named test stack.

`requirements.txt` lists the dependencies already used by the application. It does not introduce version pins. The native installer and updater both install this manifest using the system Python interpreter.

## Installation and upgrades

The installer and updater stage the complete package and templates and install dependencies before replacing application files. The setup script installs from its matching checkout; direct updater downloads use the stable branch. Minimal-container dependencies and the exact sudo Caddy validation command are installed explicitly. The systemd startup command, service user and configuration format remain unchanged.

For the first upgrade from 1.x, use the **2.0.0 updater** from the `stable` branch. A copy of the old updater cannot download the new folders. Fetch the current script before running it:

```sh
sudo wget -O /tmp/caddy-manager-update.sh https://raw.githubusercontent.com/the0neand0nly001/caddymanager/stable/update.sh
sudo bash /tmp/caddy-manager-update.sh
```

Later upgrades can use the installed `/opt/caddy-manager/update.sh` as before. The updater does not download replacements for `config.yml` or `.credentials`.

## Behaviour retained for this release

This release reorganises the source. It leaves the following existing behaviour in place for a separate review:

- Route addition restores the previous Caddyfile only when both validation and reload return a failure.
- Route removal uses the same regular expression, with the same limitation for nested HTTPS blocks.
- Missing or single-line credentials still fall back to the default login.
- The CSRF error handler still renders the dashboard with HTTP status 200.

Changes to these behaviours should have their own tests and review, rather than being bundled into a file move.
