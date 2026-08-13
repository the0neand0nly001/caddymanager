import os
import re
import subprocess
import yaml
from flask import Flask, render_template_string, request, redirect, url_for, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))

CRED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".credentials")

def load_config():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yml")
    if not os.path.exists(config_path):
        config_path = "/opt/caddy-manager/config.yml"
        
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}

def get_stored_credentials():
    if os.path.exists(CRED_FILE):
        with open(CRED_FILE, "r") as f:
            lines = f.read().splitlines()
            if len(lines) >= 2:
                return lines[0], lines[1]
    return "admin", generate_password_hash("admin")

ADMIN_USER, ADMIN_PASSWORD_HASH = get_stored_credentials()

def get_routes():
    config = load_config()
    caddyfile_path = config.get("CADDYFILE_PATH", "/etc/caddy/Caddyfile")
    custom_domain = config.get("DOMAIN", "home.lab").strip()

    if not os.path.exists(caddyfile_path):
        return []
    try:
        with open(caddyfile_path, "r") as f:
            content = f.read()
        
        # Match domain block and extract reverse_proxy target if present
        pattern = r"([a-zA-Z0-9][-a-zA-Z0-9]*\." + re.escape(custom_domain) + r")\s*\{([^}]*)\}"
        matches = re.findall(pattern, content, re.DOTALL)
        
        routes = []
        for domain, block in matches:
            target = "Unknown"
            proxy_match = re.search(r"reverse_proxy\s+([^\s]+)", block)
            if proxy_match:
                target = proxy_match.group(1)
            routes.append({"domain": domain, "target": target})
            
        return sorted(routes, key=lambda x: x["domain"])
    except Exception:
        return []

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Login - Caddy Manager</title>
    <style>
        :root {
            --bg-color: #121214;
            --panel-bg: #1a1a1e;
            --border-color: #2a2a30;
            --text-color: #e1e1e6;
            --text-muted: #a1a1af;
            --accent-green: #00b37e;
            --accent-green-hover: #00875f;
            --accent-red: #f75a68;
            --input-bg: #121214;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-color);
            background-image: radial-gradient(circle at 50% 50%, #1f1f23 0%, #121214 100%);
            color: var(--text-color);
            margin: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }
        .login-card {
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
            width: 100%;
            max-width: 380px;
        }
        h2 {
            margin-top: 0;
            color: #ffffff;
            font-size: 1.25rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 10px;
            margin-bottom: 20px;
            text-align: center;
        }
        .form-group { margin-bottom: 15px; }
        label {
            display: block;
            margin-bottom: 6px;
            font-size: 0.85rem;
            color: var(--text-muted);
            font-weight: 600;
        }
        input[type="text"], input[type="password"] {
            width: 100%;
            padding: 10px 12px;
            box-sizing: border-box;
            background: var(--input-bg);
            border: 1px solid var(--border-color);
            color: var(--text-color);
            border-radius: 6px;
            font-size: 0.95rem;
        }
        input:focus { outline: none; border-color: var(--accent-green); }
        button {
            background: var(--accent-green);
            color: white;
            padding: 10px;
            width: 100%;
            border: none;
            border-radius: 6px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }
        button:hover { background: var(--accent-green-hover); }
        .alert-error {
            background: rgba(247, 90, 104, 0.15);
            border: 1px solid var(--accent-red);
            color: #ff8b94;
            padding: 10px;
            border-radius: 6px;
            margin-bottom: 15px;
            font-size: 0.85rem;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="login-card">
        <h2>Caddy Manager Login</h2>
        {% if error %}
            <div class="alert-error">{{ error }}</div>
        {% endif %}
        <form method="POST">
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" required autofocus>
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit">Sign In</button>
        </form>
    </div>
</body>
</html>
"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Caddy Reverse Proxy Manager</title>
    <style>
        :root {
            --bg-color: #121214;
            --panel-bg: #1a1a1e;
            --border-color: #2a2a30;
            --text-color: #e1e1e6;
            --text-muted: #a1a1af;
            --accent-green: #00b37e;
            --accent-green-hover: #00875f;
            --accent-red: #f75a68;
            --accent-red-hover: #de3f4f;
            --input-bg: #121214;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-color);
            background-image: radial-gradient(circle at 50% 50%, #1f1f23 0%, #121214 100%);
            color: var(--text-color);
            margin: 0;
            padding: 40px;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-height: 90vh;
        }
        .header-bar {
            width: 100%;
            max-width: 1000px;
            display: flex;
            justify-content: flex-end;
            margin-bottom: 15px;
        }
        .logout-btn {
            background: transparent;
            border: 1px solid var(--border-color);
            color: var(--text-muted);
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 0.85rem;
            cursor: pointer;
            text-decoration: none;
            transition: all 0.2s;
        }
        .logout-btn:hover {
            border-color: var(--accent-red);
            color: var(--accent-red);
        }
        .wrapper {
            display: flex;
            gap: 30px;
            max-width: 1000px;
            width: 100%;
            align-items: flex-start;
        }
        .sidebar {
            flex: 1;
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
            max-height: 80vh;
            overflow-y: auto;
        }
        .main-content {
            flex: 1.2;
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        .card {
            background: var(--panel-bg);
            border: 1px solid var(--border-color);
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
        }
        .sidebar-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        .sidebar-header h3 {
            margin: 0;
            border: none;
            padding: 0;
            color: #ffffff;
            font-size: 1.25rem;
        }
        .toggle-label {
            font-size: 0.75rem;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 5px;
            cursor: pointer;
            user-select: none;
        }
        .toggle-label input { cursor: pointer; accent-color: var(--accent-green); }
        h2, h3 {
            margin-top: 0;
            color: #ffffff;
            font-size: 1.25rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        .form-group { margin-bottom: 15px; }
        label {
            display: block;
            margin-bottom: 6px;
            font-size: 0.85rem;
            color: var(--text-muted);
            font-weight: 600;
        }
        input[type="text"], select {
            width: 100%;
            padding: 10px 12px;
            box-sizing: border-box;
            background: var(--input-bg);
            border: 1px solid var(--border-color);
            color: var(--text-color);
            border-radius: 6px;
            font-size: 0.95rem;
        }
        input[type="text"]:focus, select:focus { outline: none; border-color: var(--accent-green); }
        button {
            background: var(--accent-green);
            color: white;
            padding: 10px;
            width: 100%;
            border: none;
            border-radius: 6px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }
        button:hover { background: var(--accent-green-hover); }
        .delete-btn { background: var(--accent-red); }
        .delete-btn:hover { background: var(--accent-red-hover); }
        .domain-list { list-style: none; padding: 0; margin: 0; }
        .domain-item {
            padding: 10px 12px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border-color);
            margin-bottom: 8px;
            border-radius: 6px;
            font-size: 0.9rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .domain-info {
            display: flex;
            flex-direction: column;
            gap: 3px;
        }
        .domain-name {
            font-family: monospace;
            color: #ffffff;
        }
        .domain-target {
            font-size: 0.75rem;
            color: var(--text-muted);
            font-family: monospace;
        }
        .status-badge {
            width: 8px;
            height: 8px;
            background-color: var(--accent-green);
            border-radius: 50%;
            display: inline-block;
            flex-shrink: 0;
        }
        .alert {
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 20px;
            font-size: 0.9rem;
            font-weight: 500;
        }
        .alert-success {
            background: rgba(0, 179, 126, 0.15);
            border: 1px solid var(--accent-green);
            color: #00f0a8;
        }
        .alert-error {
            background: rgba(247, 90, 104, 0.15);
            border: 1px solid var(--accent-red);
            color: #ff8b94;
        }
        .empty-text { color: var(--text-muted); font-style: italic; font-size: 0.9rem; }
        footer {
            text-align: center;
            margin-top: 30px;
            font-size: 0.85rem;
            color: var(--text-muted);
            width: 100%;
            max-width: 1000px;
        }
    </style>
</head>
<body>
    <div class="header-bar">
        <a href="/logout" class="logout-btn">Sign Out</a>
    </div>
    <div class="wrapper">
        <div class="sidebar">
            <div class="sidebar-header">
                <h3>Active Domains</h3>
                <label class="toggle-label" title="Show or hide target IP/Port">
                    <input type="checkbox" id="toggleTargets" onchange="toggleTargetVisibility()"> Show Targets
                </label>
            </div>
            {% if routes %}
                <ul class="domain-list">
                    {% for route in routes %}
                        <li class="domain-item">
                            <div class="domain-info">
                                <span class="domain-name">{{ route.domain }}</span>
                                <span class="domain-target" data-target="{{ route.target }}">{{ route.target }}</span>
                            </div>
                            <span class="status-badge" title="Active"></span>
                        </li>
                    {% endfor %}
                </ul>
            {% else %}
                <p class="empty-text">No active routes found in Caddyfile.</p>
            {% endif %}
        </div>

        <div class="main-content">
            {% if message %}
                <div class="alert {% if is_error %}alert-error{% else %}alert-success{% endif %}">
                    {{ message }}
                </div>
            {% endif %}

            <div class="card">
                <h2>Add Caddy Route</h2>
                <form method="POST">
                    <input type="hidden" name="action" value="add">
                    <div class="form-group">
                        <label for="name">Subdomain Name</label>
                        <input type="text" id="name" name="name" placeholder="e.g. plex" required>
                    </div>
                    <div class="form-group">
                        <label for="ip">IP Address</label>
                        <input type="text" id="ip" name="ip" placeholder="e.g. 192.168.1.50" required>
                    </div>
                    <div class="form-group">
                        <label for="port">Port</label>
                        <input type="text" id="port" name="port" placeholder="e.g. 8080" required>
                    </div>
                    <div class="form-group">
                        <label for="protocol">Backend Protocol</label>
                        <select id="protocol" name="protocol">
                            <option value="http">HTTP</option>
                            <option value="https">HTTPS</option>
                        </select>
                    </div>
                    <button type="submit">Add to Caddyfile</button>
                </form>
            </div>

            <div class="card">
                <h2>Remove Caddy Route</h2>
                <form method="POST">
                    <input type="hidden" name="action" value="remove">
                    <div class="form-group">
                        <label for="route">Select Route to Remove</label>
                        <select id="route" name="route">
                            {% for route in routes %}
                                <option value="{{ route.domain }}">{{ route.domain }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <button type="submit" class="delete-btn">Remove from Caddyfile</button>
                </form>
            </div>

            <div class="card">
                <h2>SSL Certificate Authority</h2>
                <p class="empty-text" style="margin-bottom: 15px;">Download Caddy's local root CA certificate to install on Windows, mobile devices, or other servers (like Proxmox) to eliminate security warnings.</p>
                <a href="/download-ca" style="text-decoration: none;">
                    <button type="button" style="background: #2196F3;">Download Root CA (.crt)</button>
                </a>
            </div>
        </div>
    </div>
    <footer>
        Made with ❤️ by evansinnott & The0neAnd0nly |
        <a href="https://github.com/the0neand0nly001/caddymanager/blob/main/DOCUMENTATION.md" target="_blank" style="color: inherit; text-decoration: none;">Documentation</a> | 
        <span>V1.2.0</span>
        {% if adguard_ip %}
        | <span>DNS: {{ adguard_ip }}</span>
        {% endif %}
    </footer>

    <script>
        function toggleTargetVisibility() {
            const show = document.getElementById('toggleTargets').checked;
            localStorage.setItem('show_caddy_targets', show);
            document.querySelectorAll('.domain-target').forEach(el => {
                el.style.display = show ? 'block' : 'none';
            });
        }

        window.addEventListener('DOMContentLoaded', () => {
            const saved = localStorage.getItem('show_caddy_targets');
            const show = saved === 'true'; // defaults to false if not set
            document.getElementById('toggleTargets').checked = show;
            document.querySelectorAll('.domain-target').forEach(el => {
                el.style.display = show ? 'block' : 'none';
            });
        });
    </script>
</body>
</html>
"""

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    global ADMIN_USER, ADMIN_PASSWORD_HASH
    ADMIN_USER, ADMIN_PASSWORD_HASH = get_stored_credentials()
    
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == ADMIN_USER and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session["logged_in"] = True
            return redirect(url_for("index"))
        else:
            error = "Invalid username or password."
    return render_template_string(LOGIN_TEMPLATE, error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/download-ca")
def download_ca():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    ca_path = "/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt"
    
    if not os.path.exists(ca_path):
        ca_path = os.path.expanduser("~/.local/share/caddy/pki/authorities/local/root.crt")
        
    if os.path.exists(ca_path):
        return send_file(ca_path, as_attachment=True, download_name="caddy-root-ca.crt")
    else:
        return "Caddy root CA certificate not found. Ensure Caddy has generated it by visiting one of your local HTTPS sites first.", 404

@app.route("/", methods=["GET", "POST"])
def index():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    message = None
    is_error = False
    routes = get_routes()
    config = load_config()
    adguard_ip = config.get("ADGUARD_IP", "192.168.1.100")

    if request.method == "POST":
        action = request.form.get("action")
        caddyfile_path = config.get("CADDYFILE_PATH", "/etc/caddy/Caddyfile")
        custom_domain = config.get("DOMAIN", "home.lab").strip()
        
        if action == "add":
            name = request.form.get("name").strip().lower()
            ip = request.form.get("ip").strip()
            port = request.form.get("port").strip()
            protocol = request.form.get("protocol", "http")
            
            subdomain = f"{name}.{custom_domain}"
            
            # Conditionally add transport block to trust self-signed HTTPS backends
            if protocol == "https":
                block = f"\n{subdomain} {{\n    reverse_proxy {protocol}://{ip}:{port} {{\n        transport http {{\n            tls_insecure_skip_verify\n        }}\n    }}\n    tls internal\n}}\n"
            else:
                block = f"\n{subdomain} {{\n    reverse_proxy {protocol}://{ip}:{port}\n    tls internal\n}}\n"
            
            try:
                with open(caddyfile_path, "a") as f:
                    f.write(block)
                
                valid = subprocess.run(["caddy", "validate", "--config", caddyfile_path], capture_output=True, text=True)
                if valid.returncode != 0:
                    message = f"Added route, but Caddy validation failed: {valid.stderr}"
                    is_error = True
                else:
                    subprocess.run(["systemctl", "reload", "caddy"], check=True)
                    message = f"Successfully added and reloaded route for {subdomain}!"
            except Exception as e:
                message = f"Error updating Caddyfile: {str(e)}"
                is_error = True

        elif action == "remove":
            target_route = request.form.get("route")
            try:
                with open(caddyfile_path, "r") as f:
                    content = f.read()
                
                pattern = re.escape(target_route) + r"\s*\{[^}]*\}"
                new_content = re.sub(pattern, "", content, flags=re.DOTALL)
                new_content = re.sub(r'\n\s*\n\s*\n', '\n\n', new_content)
                
                with open(caddyfile_path, "w") as f:
                    f.write(new_content)
                
                subprocess.run(["systemctl", "reload", "caddy"], check=True)
                message = f"Successfully removed route: {target_route}"
            except Exception as e:
                message = f"Error removing route: {str(e)}"
                is_error = True

        routes = get_routes()

    return render_template_string(HTML_TEMPLATE, routes=routes, message=message, is_error=is_error, adguard_ip=adguard_ip)

if __name__ == "__main__":
    config = load_config()
    webserver_port = config.get("WEBSERVER_PORT", 5000)
    app.run(host="0.0.0.0", port=webserver_port)