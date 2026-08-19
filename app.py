import os
import re
import ipaddress
import subprocess
import yaml
import urllib.request
import json
import psutil
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, session, send_file, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["60 per minute", "10 per second"],
    storage_uri="memory://"
)

app.config.update(
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)

csrf = CSRFProtect(app)

CRED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".credentials")
AUDIT_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "audit.log")

try:
    caddy_proc = psutil.Process(os.getpid())
    caddy_proc.cpu_percent(interval=None)
except Exception:
    caddy_proc = None

def log_audit(action, details):
    client_ip = request.remote_addr or "Unknown"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] IP: {client_ip} | Action: {action} | Details: {details}\n"
    
    try:
        os.makedirs(os.path.dirname(AUDIT_LOG_FILE), exist_ok=True)
        with open(AUDIT_LOG_FILE, "a") as f:
            f.write(log_entry)
    except Exception:
        pass

    config = load_config()
    DISCORD_WEBHOOK_URL = config.get("DISCORD_WEBHOOK_URL", "")
    
    if DISCORD_WEBHOOK_URL:
        payload = {
            "content": f"🚨 **Caddy Manager Security Alert**\n• **Action:** `{action}`\n• **IP:** `{client_ip}`\n• **Details:** {details}"
        }
        try:
            req = urllib.request.Request(
                DISCORD_WEBHOOK_URL,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json', 'User-Agent': 'CaddyManager'}
            )
            urllib.request.urlopen(req)
        except Exception as e:
            print(f"Webhook error: {e}")

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
    
    default_domain = config.get("DOMAIN", "home.lab")
    domains_list = config.get("DOMAINS", [default_domain])

    if not os.path.exists(caddyfile_path):
        return []
    try:
        with open(caddyfile_path, "r") as f:
            content = f.read()
        
        routes = []
        for d in domains_list:
            pattern = r"([a-zA-Z0-9][-a-zA-Z0-9]*\." + re.escape(d.strip()) + r")\s*\{([^}]*)\}"
            matches = re.findall(pattern, content, re.DOTALL)
            
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
    <link rel="icon" type="image/png" sizes="32x32" href="{{ url_for('static', filename='icon.png') }}">
    <style>
        :root {
            --bg-color: #121214; --panel-bg: #1a1a1e; --border-color: #2a2a30;
            --text-color: #e1e1e6; --text-muted: #a1a1af; --accent-green: #00b37e;
            --accent-green-hover: #00875f; --accent-red: #f75a68; --input-bg: #121214;
        }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: var(--bg-color); color: var(--text-color); display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .login-card { background: var(--panel-bg); border: 1px solid var(--border-color); padding: 30px; border-radius: 12px; width: 100%; max-width: 380px; box-shadow: 0 8px 24px rgba(0,0,0,0.4); }
        h2 { margin-top: 0; color: #fff; font-size: 1.25rem; border-bottom: 1px solid var(--border-color); padding-bottom: 10px; margin-bottom: 20px; text-align: center; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 6px; font-size: 0.85rem; color: var(--text-muted); font-weight: 600; }
        input[type="text"], input[type="password"] { width: 100%; padding: 10px 12px; box-sizing: border-box; background: var(--input-bg); border: 1px solid var(--border-color); color: var(--text-color); border-radius: 6px; font-size: 0.95rem; }
        input:focus { outline: none; border-color: var(--accent-green); }
        button { background: var(--accent-green); color: white; padding: 10px; width: 100%; border: none; border-radius: 6px; font-size: 0.95rem; font-weight: 600; cursor: pointer; }
        button:hover { background: var(--accent-green-hover); }
        .alert-error { background: rgba(247, 90, 104, 0.15); border: 1px solid var(--accent-red); color: #ff8b94; padding: 10px; border-radius: 6px; margin-bottom: 15px; font-size: 0.85rem; text-align: center; }
    </style>
</head>
<body>
    <div class="login-card">
        <h2>Caddy Manager Login</h2>
        {% if error %}<div class="alert-error">{{ error }}</div>{% endif %}
        <form method="POST">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <div class="form-group"><label>Username</label><input type="text" name="username" required autofocus></div>
            <div class="form-group"><label>Password</label><input type="password" name="password" required></div>
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
    <title>Caddy Manager</title>
    <link rel="icon" type="image/png" sizes="32x32" href="{{ url_for('static', filename='icon.png') }}">
    <style>
        :root {
            --bg-color: #121214; --panel-bg: #1a1a1e; --border-color: #2a2a30;
            --text-color: #e1e1e6; --text-muted: #a1a1af; --accent-green: #00b37e;
            --accent-green-hover: #00875f; --accent-red: #f75a68; --accent-red-hover: #de3f4f; --input-bg: #121214;
        }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: var(--bg-color); color: var(--text-color); margin: 0; padding: 40px; display: flex; flex-direction: column; align-items: center; min-height: 90vh; }
        .header-bar { width: 100%; max-width: 1000px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .status-badge-top { width: 12px; height: 12px; background-color: var(--accent-green); border-radius: 50%; display: inline-block; box-shadow: 0 0 8px rgba(0, 179, 126, 0.6); }
        .logout-btn { background: transparent; border: 1px solid var(--border-color); color: var(--text-muted); padding: 6px 14px; border-radius: 6px; font-size: 0.85rem; text-decoration: none; }
        .logout-btn:hover { border-color: var(--accent-red); color: var(--accent-red); }
        .tab-nav { display: flex; gap: 10px; margin-bottom: 20px; width: 100%; max-width: 1000px; }
        .tab-btn { background: var(--panel-bg); border: 1px solid var(--border-color); color: var(--text-muted); padding: 10px 20px; border-radius: 8px; font-weight: 600; cursor: pointer; }
        .tab-btn.active { background: var(--accent-green); color: white; border-color: var(--accent-green); }
        .tab-content { display: none; width: 100%; max-width: 1000px; }
        .tab-content.active { display: flex; flex-direction: column; gap: 30px; }
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; width: 100%; }
        .metric-card, .card, .sidebar { background: var(--panel-bg); border: 1px solid var(--border-color); padding: 25px; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.4); }
        .metric-title, .empty-text, footer { color: var(--text-muted); }
        .metric-value { font-size: 2.2rem; font-weight: bold; color: var(--accent-green); font-family: monospace; margin: 0 0 15px 0; }
        .metric-graph-container { width: 100%; background: rgba(255,255,255,0.05); border-radius: 4px; height: 8px; border: 1px solid var(--border-color); overflow: hidden; }
        .metric-graph-bar { height: 100%; width: 0%; background: var(--accent-green); border-radius: 4px; transition: width 0.4s ease; }
        .wrapper { display: flex; gap: 30px; max-width: 1000px; width: 100%; align-items: flex-start; }
        .sidebar { flex: 1; max-height: 80vh; overflow-y: auto; }
        .main-content { flex: 1.2; display: flex; flex-direction: column; gap: 20px; }
        .sidebar-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 10px; margin-bottom: 15px; }
        .sidebar-header h3 { margin: 0; color: #fff; font-size: 1.25rem; border: none; }
        .sidebar-controls { display: flex; gap: 10px; margin-bottom: 15px; align-items: center; }
        .sidebar-controls select { padding: 6px 10px; font-size: 0.85rem; background: var(--input-bg); border: 1px solid var(--border-color); color: var(--text-color); border-radius: 6px; flex: 1; }
        .toggle-label { font-size: 0.75rem; color: var(--text-muted); display: flex; align-items: center; gap: 5px; cursor: pointer; }
        h2, h3 { margin-top: 0; color: #fff; font-size: 1.25rem; border-bottom: 1px solid var(--border-color); padding-bottom: 10px; margin-bottom: 20px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 6px; font-size: 0.85rem; color: var(--text-muted); font-weight: 600; }
        input[type="text"], select { width: 100%; padding: 10px 12px; box-sizing: border-box; background: var(--input-bg); border: 1px solid var(--border-color); color: var(--text-color); border-radius: 6px; font-size: 0.95rem; }
        input:focus, select:focus { outline: none; border-color: var(--accent-green); }
        button { background: var(--accent-green); color: white; padding: 10px; width: 100%; border: none; border-radius: 6px; font-size: 0.95rem; font-weight: 600; cursor: pointer; }
        button:hover { background: var(--accent-green-hover); }
        .delete-btn { background: var(--accent-red); }
        .delete-btn:hover { background: var(--accent-red-hover); }
        .domain-list { list-style: none; padding: 0; margin: 0; }
        .domain-item { padding: 10px 12px; background: rgba(255,255,255,0.03); border: 1px solid var(--border-color); margin-bottom: 8px; border-radius: 6px; display: flex; align-items: center; justify-content: space-between; }
        .domain-info { display: flex; flex-direction: column; gap: 3px; }
        .domain-name { font-family: monospace; color: #fff; }
        .domain-target { font-size: 0.75rem; color: var(--text-muted); font-family: monospace; display: none; }
        .status-badge { width: 8px; height: 8px; background-color: var(--accent-green); border-radius: 50%; display: inline-block; }
        .alert { padding: 12px; border-radius: 6px; margin-bottom: 20px; font-size: 0.9rem; font-weight: 500; }
        .alert-success { background: rgba(0, 179, 126, 0.15); border: 1px solid var(--accent-green); color: #00f0a8; }
        .alert-error { background: rgba(247, 90, 104, 0.15); border: 1px solid var(--accent-red); color: #ff8b94; }
        footer { text-align: center; margin-top: 30px; font-size: 0.85rem; width: 100%; max-width: 1000px; }
    </style>
</head>
<body>
    <div class="header-bar">
        <div class="status-badge-container"><span id="topStatusDot" class="status-badge-top"></span></div>
        <a href="/logout" class="logout-btn">Sign Out</a>
    </div>

    <div class="tab-nav">
        <button class="tab-btn active" onclick="switchTab('dashboard', event)">System Dashboard</button>
        <button class="tab-btn" onclick="switchTab('routes', event)">Caddy Manager</button>
    </div>

    <div id="tab-dashboard" class="tab-content active">
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-title">CPU Usage</div>
                <p id="metric-cpu" class="metric-value">Loading...</p>
                <div class="metric-graph-container"><div id="graph-cpu" class="metric-graph-bar"></div></div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Memory Usage</div>
                <p id="metric-ram" class="metric-value">Loading...</p>
                <div class="metric-graph-container"><div id="graph-ram" class="metric-graph-bar"></div></div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Active Routes Count</div>
                <p id="metric-routes" class="metric-value" style="margin-bottom:0;">{{ routes | length }}</p>
            </div>
        </div>
    </div>

    <div id="tab-routes" class="tab-content">
        {% if message %}
            <div class="alert {% if is_error %}alert-error{% else %}alert-success{% endif %}">{{ message }}</div>
        {% endif %}

        <div class="wrapper">
            <div class="sidebar">
                <div class="sidebar-header"><h3>Active Domains</h3></div>
                <div class="sidebar-controls">
                    <select id="domainFilter" onchange="filterDomains()">
                        <option value="all">All Domains</option>
                        {% for d in domains %}<option value="{{ d }}">{{ d }}</option>{% endfor %}
                    </select>
                    <label class="toggle-label"><input type="checkbox" id="toggleTargets" onchange="toggleTargetVisibility()"> Show Targets</label>
                </div>
                {% if routes %}
                    <ul class="domain-list" id="domainList">
                        {% for route in routes %}
                            <li class="domain-item" data-domain="{{ route.domain }}">
                                <div class="domain-info">
                                    <span class="domain-name">{{ route.domain }}</span>
                                    <span class="domain-target" data-target="{{ route.target }}">{{ route.target }}</span>
                                </div>
                                <span class="status-badge"></span>
                            </li>
                        {% endfor %}
                    </ul>
                {% else %}
                    <p class="empty-text">No active routes found in Caddyfile.</p>
                {% endif %}
            </div>

            <div class="main-content">
                <div class="card">
                    <h2>Add Caddy Route</h2>
                    <form method="POST">
                        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                        <input type="hidden" name="action" value="add">
                        <div class="form-group"><label>Subdomain Name</label><input type="text" name="name" placeholder="e.g. plex" required></div>
                        <div class="form-group"><label>Base Domain</label><select name="base_domain">{% for d in domains %}<option value="{{ d }}">{{ d }}</option>{% endfor %}</select></div>
                        <div class="form-group"><label>IP Address</label><input type="text" name="ip" placeholder="e.g. 192.168.1.50" required></div>
                        <div class="form-group"><label>Port</label><input type="text" name="port" placeholder="e.g. 8080" required></div>
                        <div class="form-group"><label>Backend Protocol</label><select name="protocol"><option value="http">HTTP</option><option value="https">HTTPS</option></select></div>
                        <button type="submit">Add to Caddyfile</button>
                    </form>
                </div>

                <div class="card">
                    <h2>Remove Caddy Route</h2>
                    <form method="POST">
                        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                        <input type="hidden" name="action" value="remove">
                        <div class="form-group"><label>Select Route to Remove</label><select name="route">{% for route in routes %}<option value="{{ route.domain }}">{{ route.domain }}</option>{% endfor %}</select></div>
                        <button type="submit" class="delete-btn">Remove from Caddyfile</button>
                    </form>
                </div>
            </div>
        </div>
    </div>

    <footer>Caddy Manager v1.4.2</footer>
    <script>
        function switchTab(tabId, event) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById('tab-' + tabId).classList.add('active');
            event.currentTarget.classList.add('active');
            localStorage.setItem('active_tab', tabId);
        }
        function fetchMetrics() {
            fetch('/api/metrics').then(res => res.json()).then(data => {
                document.getElementById('metric-cpu').innerText = data.cpu + '%';
                document.getElementById('graph-cpu').style.width = Math.min(data.cpu, 100) + '%';
                document.getElementById('metric-ram').innerText = data.ram_mb + ' MB';
                document.getElementById('graph-ram').style.width = Math.min((data.ram_mb / 500) * 100, 100) + '%';
                document.getElementById('metric-routes').innerText = data.routes;
            }).catch(err => console.error(err));
        }
        setInterval(fetchMetrics, 3000);
        fetchMetrics();
        function toggleTargetVisibility() {
            const show = document.getElementById('toggleTargets').checked;
            document.querySelectorAll('.domain-target').forEach(el => el.style.display = show ? 'block' : 'none');
        }
        function filterDomains() {
            const sel = document.getElementById('domainFilter').value;
            document.querySelectorAll('.domain-item').forEach(item => {
                const d = item.getAttribute('data-domain');
                item.style.display = (sel === 'all' || d.endsWith('.' + sel)) ? 'flex' : 'none';
            });
        }
    </script>
</body>
</html>
"""

@app.route("/api/metrics")
def api_metrics():
    if not session.get("logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    cpu_usage, ram_mb = 0.0, 0.0
    global caddy_proc
    try:
        if not caddy_proc:
            caddy_proc = psutil.Process(os.getpid())
        cpu_usage = round(caddy_proc.cpu_percent(interval=None), 1)
        ram_mb = round(caddy_proc.memory_info().rss / (1024 * 1024), 1)
    except Exception:
        pass
    return jsonify({"cpu": cpu_usage, "ram_mb": ram_mb, "routes": len(get_routes())})

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    return render_template_string(HTML_TEMPLATE, message="CSRF token missing or invalid.", is_error=True, routes=get_routes(), domains=[])

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    error = None
    global ADMIN_USER, ADMIN_PASSWORD_HASH
    ADMIN_USER, ADMIN_PASSWORD_HASH = get_stored_credentials()
    if request.method == "POST":
        if request.form.get("username") == ADMIN_USER and check_password_hash(ADMIN_PASSWORD_HASH, request.form.get("password")):
            session["logged_in"] = True
            return redirect(url_for("index"))
        error = "Invalid username or password."
    return render_template_string(LOGIN_TEMPLATE, error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/", methods=["GET", "POST"])
def index():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    config = load_config()
    domains_list = config.get("DOMAINS", [config.get("DOMAIN", "home.lab")])
    caddyfile_path = config.get("CADDYFILE_PATH", "/etc/caddy/Caddyfile")

    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "add":
                name = request.form.get("name", "").strip().lower()
                ip_str = request.form.get("ip", "").strip()
                port_str = request.form.get("port", "").strip()
                protocol = request.form.get("protocol", "http")
                selected_domain = request.form.get("base_domain", domains_list[0]).strip()

                subdomain = f"{name}.{selected_domain}"
                if protocol == "https":
                    block = f"\n{subdomain} {{\n    reverse_proxy {protocol}://{ip_str}:{port_str} {{\n        transport http {{\n            tls_insecure_skip_verify\n        }}\n    }}\n    tls internal\n}}\n"
                else:
                    block = f"\n{subdomain} {{\n    reverse_proxy {protocol}://{ip_str}:{port_str}\n    tls internal\n}}\n"

                with open(caddyfile_path, "a") as f:
                    f.write(block)
                
                subprocess.run(["systemctl", "reload", "caddy"], check=True)
                session['flash_message'] = f"Successfully added route for {subdomain}!"
                session['flash_error'] = False
            elif action == "remove":
                target_route = request.form.get("route", "").strip()
                with open(caddyfile_path, "r") as f:
                    content = f.read()
                
                pattern = re.escape(target_route) + r"\s*\{[^}]*\}"
                new_content = re.sub(pattern, "", content, flags=re.DOTALL)
                
                with open(caddyfile_path, "w") as f:
                    f.write(new_content)
                
                subprocess.run(["systemctl", "reload", "caddy"], check=True)
                session['flash_message'] = f"Successfully removed route: {target_route}"
                session['flash_error'] = False
        except Exception as e:
            session['flash_message'] = f"Permission or file error modifying Caddyfile: {e}"
            session['flash_error'] = True

        return redirect(url_for("index"))

    message = session.pop('flash_message', None)
    is_error = session.pop('flash_error', False)
    return render_template_string(HTML_TEMPLATE, routes=get_routes(), message=message, is_error=is_error, domains=domains_list)

if __name__ == "__main__":
    config = load_config()
    app.run(host="0.0.0.0", port=config.get("WEBSERVER_PORT", 5000))