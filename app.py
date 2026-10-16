"""Run the Caddy Manager web server."""

from caddy_manager import create_app
from caddy_manager.config import load_config

app = create_app()

if __name__ == "__main__":
    config = load_config()
    webserver_port = config.get("WEBSERVER_PORT", 5000)
    app.run(host="0.0.0.0", port=webserver_port)
