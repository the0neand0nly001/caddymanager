# 🛡️ Caddy Manager
<div align="center">

A lightweight, modern web-based control panel designed to effortlessly manage Caddyfile routes, monitor system performance, and check backend service health in real time.

![Version](https://img.shields.io/badge/version-1.5.0-00b37e?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)
![Python](https://img.shields.io/badge/python-3.8%2B-blueviolet?style=flat-square)
</div>

---

## ✨ Features
* **🎛️ Dual-Tab Interface:** Easily switch between a dedicated **System Dashboard** and the core **Caddy Manager** route controls.
* **📊 Real-Time System Metrics:** Live monitoring of CPU usage, memory consumption, and active route totals with smooth visual progress bars.
* **🔍 Service Health Monitor:** Instantly select any configured route from a dropdown menu to test if your backend targets are online or down.
* **🔒 Enterprise-Grade Security:** Built with Flask-WTF CSRF protection, rate limiting via Flask-Limiter, secure session management, and instant Discord webhook security alerts.
* **⚡ Automated Caddy Management:** Safely add or remove routes with built-in Caddyfile syntax validation and automatic rollbacks to prevent downtime.
* **📜 SSL CA Downloads:** Quick, one-click access to download Caddy’s local root CA certificate directly from the dashboard to eliminate browser security warnings.

---

## 🚀 Quick Installation
Deploy Caddy Manager instantly on your fresh Linux server using the automated installation script:
```
sudo bash -c "$(curl -sSL https://raw.githubusercontent.com/the0neand0nly001/caddymanager/stable/setup.sh)"
```
## 💡 Important Note on the SSL Certificate Authority
On a fresh installation, Caddy will not generate its local CA certificate (`root.crt`) until an active route or domain block requires internal TLS. 
* To make the **Download Root CA** button work, simply **add your first route** using the Caddy Manager dashboard.
* Once added, restart both services to initialize the certificate:
  ```bash
  sudo systemctl restart caddy
  sudo systemctl restart caddy-manager
* ** This is a one time thing and will not need to be done again.
---

## ⚙️ Configuration
Caddy Manager uses a simple config.yml configuration file located in your installation directory (/opt/caddy-manager/config.yml):

```
WEBSERVER_PORT: 5000
CADDYFILE_PATH: "/etc/caddy/Caddyfile"
DOMAINS:
  - "testhome.lab"
ADGUARD_IP: "192.168.1.59"
DISCORD_WEBHOOK_URL: ""
```

---

## 🤝 Credits & Built With
* Developed by evansinnott & The0neAnd0nly
* Powered by Flask, Python, and Caddy Web Server.

---

## 📚 Caddy Manager Documentation
Welcome to the official documentation for Caddy Manager (V1.5.0). This guide covers installation procedures, configuration guidelines, and management tools.

### 1. System Requirements & Architecture
Caddy Manager is designed for lightweight Linux environments running Caddy v2.
* Backend: Python 3 (Flask) managed via a dedicated systemd service.
* Permissions: Utilizes sudo helper functions to safely read, modify, and reload the system Caddyfile without exposing root privileges globally.

### 2. Installation Guide
* Automated Setup: The recommended way to install Caddy Manager is through the automated script, which handles dependencies, systemd services, users, and permissions automatically:
```
  sudo bash -c "$(curl -sSL https://raw.githubusercontent.com/the0neand0nly001/caddymanager/stable/setup.sh)"
  ```
* Default Credentials: Upon initial setup, an administrative credential file is generated at /opt/caddy-manager/.credentials. You can check or reset your admin login credentials using:
```
  sudo cat /opt/caddy-manager/.credentials
  ```

### 3. Configuration Reference (config.yml)
Parameters inside config.yml control core application behavior:
```
* WEBSERVER_PORT: Port on which the Flask dashboard runs locally. (Example: 5000)
* CADDYFILE_PATH: Absolute path to your system's Caddyfile. (Example: /etc/caddy/Caddyfile)
* DOMAINS: List of allowed base domains for route creation. (Example: ["testhome.lab", "home.lab"])
* ADGUARD_IP: Optional DNS server IP displayed in the footer. (Example: 192.168.1.59)
* DISCORD_WEBHOOK_URL: Webhook URL for security alerts e.g. login failures. (Example: "")
```

### 4. Dashboard Features
* System Dashboard:
  - Metrics Grid: View live CPU utilization and RAM usage tracked directly from the application process.
  - Service Health Monitor: Pick any active subdomain from the dropdown to run a direct TCP socket health check against the target backend IP and port.
* Caddy Manager:
  - Add Route: Specify a subdomain name, select an authorized base domain, input your target backend IP/port, and pick your protocol (HTTP or HTTPS with automatic tls_insecure_skip_verify handling).
  - Safe Validation: Every route addition automatically runs caddy validate before reloading the server. If syntax errors are detected, changes automatically roll back.
  - SSL Root CA Download: Easily grab your local root certificate to install onto client operating systems or hypervisors like Proxmox.

### 5. Managing the Service
You can control the Caddy Manager service using standard systemd commands:
* Check Status:
  ```
  sudo systemctl status caddy-manager
  ``` 
Restart Service:
```
  sudo systemctl restart caddy-manager
  ```
* View Audit Logs:
```
  sudo tail -f /opt/caddy-manager/logs/audit.log
  ```
