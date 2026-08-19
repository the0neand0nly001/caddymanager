# Caddy Reverse Proxy Manager

A lightweight, secure, and user-friendly web interface for managing your local homelab services proxied through Caddy.

## ✨ Features
- Instant Configuration: Dynamic configuration loading — changes to config.yml take effect immediately without service restarts.
- Secure Management: Password-protected dashboard for adding and removing reverse proxy routes.
- Caddy Integration: Automatically validates new routes and reloads Caddy to apply changes.
- Local CA Certificate Support: Clear instructions on deploying Caddy's internal Root CA certificate for seamless, green-lock HTTPS.
- Simple Setup: Bash-based installer for Ubuntu/Debian systems.

## 🌐 Local DNS Requirements (AdGuard Home / Pi-hole)
Because this manager uses a custom local domain suffix (e.g., `homelab.test`), you **must** configure a local DNS server like **AdGuard Home** or **Pi-hole** on your network:
- **Wildcard / DNS Rewrites:** Set up a DNS rewrite or wildcard rule in AdGuard/Pi-hole pointing `*.yourdomain.com` (e.g., `*.homelab.test`) to the local IP address of your Caddy server. 
- Without this, your client devices won't know where to route traffic when you type in a subdomain like `plex.homelab.test`.

## 🔒 Trusting Caddy's Internal CA (For Valid HTTPS / Green Lock)
When using Caddy's `tls internal` feature, browsers will normally show a security warning because Caddy generates its own local certificate authority (CA). To fix this and get secure, trusted HTTPS across your Windows or Linux devices:
1. Locate Caddy's root CA certificate on your server (typically found at `/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt`).
2. Copy or download this `.crt` file to your client machines.
3. **On Windows:** Double-click the file, click **Install Certificate**, choose **Local Machine**, and place it into the **Trusted Root Certification Authorities** store.
4. **On Ubuntu/Linux:** Copy the `.crt` file to `/usr/local/share/ca-certificates/` and run `sudo update-ca-certificates`.
Once trusted, all your local subdomains will load with a secure HTTPS lock without browser warnings.

## ⚙️ Root Permissions Note
This application requires root (sudo) privileges because it performs the following system-level tasks:
1. It writes new configurations to the system-protected Caddyfile (usually located in `/etc/caddy/`).
2. It interacts with systemd to reload the Caddy service.
3. It installs Python dependencies to the system environment.
Because of these tasks, both the installer and the background service must run with elevated permissions.

## 📦 Installation

### Prerequisites
- An Ubuntu/Debian-based system.

### Steps
```
sudo bash -c "$(curl -sSL https://raw.githubusercontent.com/the0neand0nly001/caddymanager/stable/setup.sh)"
```
