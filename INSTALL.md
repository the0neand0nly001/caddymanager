

# Installation Guide

Follow these steps to install and set up the Caddy Reverse Proxy Manager on your Ubuntu/Debian server.

## Prerequisites
- An Ubuntu or Debian-based Linux server.
- Caddy installed (`sudo apt install caddy`).
- Sudo (root) privileges.

## Step 1: Clone the Repository
Open your terminal and clone your project repository, then navigate into the project directory:
```bash
git clone https://github.com/the0neand0nly001/caddymanager.git
cd caddy-manager
````

## Step 2: Make the Installer Executable

Ensure the installation script has execution permissions by running:

Bash

```
chmod +x install.sh

```

## Step 3: Run the Installer

Execute the installation script with `sudo` privileges[cite: 1, 2, 3]:

Bash

```
sudo ./install.sh

```

### What the installer does automatically

:

1. Installs the required Python packages (`flask`, `pyyaml`).
2. Sets up the application directory structure at `/opt/caddy-manager/`.
3. Prompts you to create an administrator username and password (saved securely to `.credentials`).
4. Generates and enables a `systemd` service (`caddy-manager.service`) so the app runs automatically in the background on system startup.

## Step 4: Verify the Service

You can check if the service is running properly by running:

Bash

```
sudo systemctl status caddy-manager

```

## Step 5: Access the Dashboard

1. Open your web browser.
2. Navigate to `http://<your-server-ip>:5000`.
3. Log in using the admin credentials you created during the installation steps.
