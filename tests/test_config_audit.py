import json
from unittest.mock import mock_open, patch

from caddy_manager import audit, auth, config
from tests.support import AppTestCase


class ConfigurationAndAuditTests(AppTestCase):
    def test_configuration_reads_installation_root_and_is_not_cached(self):
        self.assertEqual(config.load_config()["DOMAINS"], ["home.lab", "testhome.lab"])
        (self.directory / "config.yml").write_text(
            "DOMAIN: legacy.lab\n", encoding="utf-8"
        )
        self.assertEqual(config.load_config(), {"DOMAIN": "legacy.lab"})

    def test_configuration_keeps_opt_fallback(self):
        with patch("os.path.exists", side_effect=[False, True]), patch(
            "builtins.open", mock_open(read_data="WEBSERVER_PORT: 5123\n")
        ) as file:
            self.assertEqual(config.load_config(), {"WEBSERVER_PORT": 5123})
            file.assert_called_once_with(
                "/opt/caddy-manager/config.yml", "r", encoding="utf-8"
            )

    def test_missing_or_empty_configuration_returns_empty_dict(self):
        (self.directory / "config.yml").write_text("", encoding="utf-8")
        self.assertEqual(config.load_config(), {})
        with patch("os.path.exists", return_value=False):
            self.assertEqual(config.load_config(), {})

    def test_legacy_colon_credentials_keep_default_fallback(self):
        self.credentials.write_text("legacy:password-hash", encoding="utf-8")
        username, password_hash = auth.get_stored_credentials()
        self.assertEqual(username, "admin")
        self.assertTrue(auth.check_password_hash(password_hash, "admin"))

    def test_audit_keeps_ip_action_details_and_webhook_payload(self):
        self.settings["DISCORD_WEBHOOK_URL"] = "https://example.invalid/webhook"
        with self.app.test_request_context(
            "/", environ_base={"REMOTE_ADDR": "192.0.2.9"}
        ):
            audit.log_audit("LOGIN_SUCCESS", "User 'owner' logged in successfully.")
        self.assertIn(
            "IP: 192.0.2.9 | Action: LOGIN_SUCCESS | Details: User 'owner' logged in successfully.\n",
            self.audit_text(),
        )
        request = self.webhook.call_args.args[0]
        self.assertEqual(request.full_url, "https://example.invalid/webhook")
        self.assertEqual(
            json.loads(request.data),
            {
                "content": "🚨 **Caddy Manager Security Alert**\n• **Action:** `LOGIN_SUCCESS`\n• **IP:** `192.0.2.9`\n• **Details:** User 'owner' logged in successfully."
            },
        )

    def test_failed_audit_file_does_not_prevent_webhook(self):
        self.settings["DISCORD_WEBHOOK_URL"] = "https://example.invalid/webhook"
        with self.app.test_request_context("/"), patch(
            "builtins.open", side_effect=OSError("simulated log failure")
        ):
            audit.log_audit("LOGOUT", "User signed out.")
        self.webhook.assert_called_once()

    def test_failed_webhook_does_not_fail_login(self):
        self.settings["DISCORD_WEBHOOK_URL"] = "https://example.invalid/webhook"
        self.webhook.side_effect = OSError("simulated webhook failure")
        response = self.client.post(
            "/login", data={"username": "owner", "password": "test-password"}
        )
        self.assertEqual(response.location, "/")
        self.assertIn("LOGIN_SUCCESS", self.audit_text())
