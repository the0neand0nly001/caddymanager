"""An isolated app with simulated Caddy commands and network calls."""

import subprocess
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from werkzeug.security import generate_password_hash

from caddy_manager import audit, auth, caddy, config, create_app, monitoring, views


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.settings = {
            "DOMAINS": ["home.lab", "testhome.lab"],
            "ADGUARD_IP": "192.168.1.59",
            "CADDYFILE_PATH": "/etc/caddy/Caddyfile",
        }
        (self.directory / "config.yml").write_text(
            "DOMAINS: [home.lab, testhome.lab]\nADGUARD_IP: 192.168.1.59\n",
            encoding="utf-8",
        )
        self.credentials = self.directory / ".credentials"
        self.credentials.write_text(
            "owner\n"
            + generate_password_hash("test-password", method="pbkdf2:sha256:1000"),
            encoding="utf-8",
        )
        self.stack.enter_context(patch.object(config, "BASE_DIR", str(self.directory)))
        self.stack.enter_context(patch.object(auth, "CRED_FILE", str(self.credentials)))
        self.stack.enter_context(
            patch.object(
                audit, "AUDIT_LOG_FILE", str(self.directory / "logs" / "audit.log")
            )
        )
        for module in (audit, caddy, views):
            self.stack.enter_context(
                patch.object(module, "load_config", lambda: self.settings)
            )

        self.content = ""
        self.validate_code = 0
        self.reload_code = 0
        self.write_code = 0
        self.commands = []
        self.stack.enter_context(patch("subprocess.run", side_effect=self.run_command))
        self.stack.enter_context(
            patch("subprocess.Popen", side_effect=self.open_command)
        )
        self.webhook = self.stack.enter_context(patch("urllib.request.urlopen"))
        self.socket = self.stack.enter_context(patch("socket.socket"))
        self.connection = self.socket.return_value.__enter__.return_value
        self.connection.connect_ex.return_value = 0
        self.process = Mock()
        self.process.cpu_percent.return_value = 12.34
        self.process.memory_info.return_value = SimpleNamespace(rss=25 * 1024 * 1024)
        self.stack.enter_context(patch.object(monitoring, "caddy_proc", self.process))

        self.app = create_app()
        self.app.config.update(
            TESTING=True, SECRET_KEY="test-secret", WTF_CSRF_ENABLED=False
        )
        self.limiter = next(iter(self.app.extensions["limiter"]))
        self.limiter.enabled = False
        self.client = self.app.test_client()

    def run_command(self, command, **options):
        self.commands.append((list(command), dict(options), None))
        result = SimpleNamespace(returncode=0, stdout="", stderr="")
        if command[:2] == ["sudo", "cat"]:
            result.stdout = self.content
        elif command[:3] == ["sudo", "caddy", "validate"]:
            result.returncode = self.validate_code
        elif command[:3] == ["sudo", "systemctl", "reload"]:
            result.returncode = self.reload_code
        elif command[:2] == ["sudo", "/usr/bin/cp"]:
            destination = Path(command[3])
            if destination.parent != self.directory:
                raise AssertionError(
                    "Certificate writes must stay in the test directory"
                )
            destination.write_bytes(b"test root certificate\n")
        if result.returncode and options.get("check"):
            raise subprocess.CalledProcessError(result.returncode, command)
        return result

    def open_command(self, command, **options):
        process = Mock(returncode=self.write_code)

        def communicate(input):
            self.commands.append((list(command), dict(options), input))
            if not self.write_code:
                if "-a" in command:
                    self.content += input
                else:
                    self.content = input
            return "", ""

        process.communicate.side_effect = communicate
        return process

    def authenticate(self):
        with self.client.session_transaction() as state:
            state["logged_in"] = True

    def add_route(self, **fields):
        self.authenticate()
        data = {
            "action": "add",
            "name": "media",
            "ip": "192.0.2.1",
            "port": "8096",
            "protocol": "http",
            "base_domain": "home.lab",
        }
        data.update(fields)
        return self.client.post("/", data=data)

    def flash(self):
        with self.client.session_transaction() as state:
            return state.get("flash_message"), state.get("flash_error")

    def audit_text(self):
        path = self.directory / "logs" / "audit.log"
        return path.read_text(encoding="utf-8") if path.exists() else ""
