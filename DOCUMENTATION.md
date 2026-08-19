# 🚀 Caddy Manager

Caddy Manager is a lightweight, web-based control panel built with Flask and Python for managing proxy routes inside a Caddyfile.

It provides a simple graphical interface for:

🌐 Viewing active proxy domains
➕ Adding new proxy routes
🗑️ Removing existing routes
⚙️ Managing the underlying Caddyfile
🔐 Securing access with administrator credentials
🖥️ Requirements

Caddy Manager is designed to run on a Linux system with:

-Python 3
-Caddy
-systemd
-pip
-Flask
-PyYAML

Note: The installation script handles the required dependencies automatically.

# ⚙️ Configuration

Caddy Manager uses a config.yml file to define its runtime configuration.

### 📄 Default Configuration
```
WEBSERVER_PORT: 5000
CADDYFILE_PATH: "/etc/caddy/Caddyfile"
DOMAIN: "home.lab"
```
### 🔧 Configuration Options
Setting	Description	Example

WEBSERVER_PORT	Port used by the Flask web server	5000
CADDYFILE_PATH	Absolute path to the Caddyfile	/etc/caddy/Caddyfile
DOMAIN	Default base domain	home.lab

Tip: After changing config.yml, restart the Caddy Manager service.
```
sudo systemctl restart caddy-manager
```
# 📦 Installation

```
sudo bash -c "$(curl -sSL https://raw.githubusercontent.com/the0neand0nly001/caddymanager/stable/setup.sh)"
```

2. Installation Process

The installation script:

-Checks whether Caddy is installed.
-Installs the required system dependencies.
-Copies the application to /opt/caddy-manager.
-Prompts for an administrator username.
-Prompts for an administrator password.
-Stores a securely hashed version of the credentials.
-Creates the systemd service.
-Registers the service with systemd.
### 3. Installation Location

The production installation is located at:

/opt/caddy-manager
# 🔄 Updating

Use update.sh to update an existing installation.

```
cd ~/caddymanager
sudo ./update.sh
```
The update script:

-Pulls the latest code from the repository.
-Synchronizes the production installation.
-Restarts the caddy-manager service.
# 🗑️ Uninstallation

To completely remove Caddy Manager:

```
cd ~/caddymanager
sudo ./uninstall.sh
```

The uninstallation script:

-Stops the caddy-manager service.
-Disables the service.
-Removes the systemd service file.
-Deletes /opt/caddy-manager.

>⚠️ Warning ⚠️ Uninstallation removes the application directory. Back up any configuration or credential files you need before running the script.

# 🖥️ Systemd Service

Caddy Manager runs as a persistent systemd service named:

```
caddy-manager
```
▶️ Start
```
sudo systemctl start caddy-manager
```
⏹️ Stop
```
sudo systemctl stop caddy-manager
```
🔄 Restart
```
sudo systemctl restart caddy-manager
```
📊 Check Status
```
sudo systemctl status caddy-manager
```
📜 View Logs

View recent logs:
```
sudo journalctl -u caddy-manager
```
Follow logs in real time:
```
sudo journalctl -u caddy-manager -f
```
# 📂 File & Directory Reference
Resource	Location
📁 Repository	~/caddymanager
📦 Production installation	/opt/caddy-manager
⚙️ Configuration	/opt/caddy-manager/config.yml
🔐 Administrator credentials	/opt/caddy-manager/.credentials
🌐 Caddyfile	/etc/caddy/Caddyfile
⚙️ systemd service	/etc/systemd/system/caddy-manager.service
# 🔐 Security

Administrator credentials are stored in:

/opt/caddy-manager/.credentials

The installation process stores a hashed version of the administrator password rather than the plaintext password.

Security Recommendation: Ensure that .credentials is readable only by trusted users on the host system.

# 🛠️ Troubleshooting
#### ❌ Service Won't Start

Check the service status:

```
sudo systemctl status caddy-manager
```
Then inspect the logs:

```
sudo journalctl -u caddy-manager -n 100
```

#### ⚙️ Configuration Changes Aren't Applied


Restart the service:
```
sudo systemctl restart caddy-manager
```
#### 📄 Check the Caddyfile

Verify that the configured Caddyfile exists:

```
sudo ls -l /etc/caddy/Caddyfile
```
Validate the Caddy configuration:
```
sudo caddy validate --config /etc/caddy/Caddyfile
```

# 🎯 Summary

Caddy Manager provides an easy-to-use web interface for managing Caddy reverse-proxy routes.

Instead of manually editing the Caddyfile for every change, administrators can use the control panel to manage proxy routes quickly and easily.

# 🚀 Caddy Manager
Simple Caddy reverse-proxy management through a web interface.
