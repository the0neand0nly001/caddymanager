# 📚 Caddy Manager Official Documentation

Welcome to the official documentation for **Caddy Manager (V1.5.0)**. This comprehensive guide details system requirements, automated installation, configuration parameters, and daily management procedures.

---

## 1. System Requirements & Architecture

Caddy Manager is designed for lightweight Linux environments running **Caddy v2**. 

* **Backend Engine:** Built on Python 3 using the Flask framework, running as a dedicated systemd service.
* **Privilege Management:** Employs safe `sudo` helper functions to read, validate, modify, and reload the system Caddyfile without requiring full root user exposure.

---

## 2. Installation Guide

### Automated Setup
The recommended installation method uses the automated setup script, which handles dependencies, system users, directories, and systemd configurations automatically:
```
sudo bash -c "$(curl -sSL https://raw.githubusercontent.com/the0neand0nly001/caddymanager/stable/setup.sh)"
```
### Default Credentials
Upon initial installation, an administrative credential file is generated at `/opt/caddy-manager/.credentials`. You can check or reset your admin login credentials using:
```
sudo cat /opt/caddy-manager/.credentials
```
---

## 3. Configuration Reference (`config.yml`)

Core application behavior is controlled via the `config.yml` file located in the installation directory:
```
* **WEBSERVER_PORT**: Port on which the Flask dashboard runs locally. (Example: `5000`)
* **CADDYFILE_PATH**: Absolute path to your system's Caddy file. (Example: `/etc/caddy/Caddyfile`)
* **DOMAINS**: List of allowed base domains permitted for route creation. (Example: `["testhome.lab", "home.lab"]`)
* **ADGUARD_IP**: Optional DNS server IP displayed at the page footer. (Example: `192.168.1.59`)
* **DISCORD_WEBHOOK_URL**: Optional webhook URL for immediate security event alerts like login failures. (Example: `""`)
```
---

## 4. Dashboard Features

### System Dashboard
* **Metrics Grid:** View live CPU utilization and RAM consumption tracked directly from the running application process.
* **Service Health Monitor:** Select any active subdomain from the dropdown to run an immediate TCP socket health check against the target backend IP and port.

### Caddy Manager
* **Add Route:** Specify a subdomain name, select an authorized base domain, input your target backend IP and port, and pick your protocol (`HTTP` or `HTTPS` with built-in `tls_insecure_skip_verify` handling).
* **Safe Validation:** Every route addition automatically runs `caddy validate` before reloading the server daemon. If configuration syntax errors are found, modifications are rolled back automatically.
* **SSL Root CA Download:** Quick, one-click access to download Caddy’s local root CA certificate directly from the dashboard to eliminate browser security warnings.

---

## 5. Managing the Service

You can monitor and control the Caddy Manager service using standard systemd commands:

* **Check Service Status:**
  ```
  sudo systemctl status caddy-manager
  ```
* **Restart Service:**
  ```
  sudo systemctl restart caddy-manager
  ```

* **View Real-Time Audit Logs:**
  ```
  sudo tail -f /opt/caddy-manager/logs/audit.log
  ```