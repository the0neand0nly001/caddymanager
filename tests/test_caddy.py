from unittest.mock import patch

from caddy_manager import caddy
from tests.support import AppTestCase


class CaddyTests(AppTestCase):
    def test_parser_handles_nested_blocks_sorts_and_deduplicates(self):
        content = (
            "z.home.lab {\n    reverse_proxy https://192.0.2.2:443 {\n"
            "        transport http {\n            tls_insecure_skip_verify\n        }\n    }\n}\n"
            "https://a.home.lab {\n    reverse_proxy http://192.0.2.1:80\n}\n"
            "z.home.lab {\n    reverse_proxy 192.0.2.3:8080\n}\n"
            "empty.home.lab {\n    tls internal\n}\n"
        )
        self.assertEqual(
            caddy.parse_routes(content),
            [
                {"domain": "a.home.lab", "target": "192.0.2.1:80"},
                {"domain": "empty.home.lab", "target": "Unknown"},
                {"domain": "z.home.lab", "target": "192.0.2.2:443"},
            ],
        )

    def test_failed_caddyfile_read_returns_no_routes(self):
        with patch("subprocess.run", side_effect=OSError("simulated read failure")):
            self.assertEqual(caddy.get_routes(), [])

    def test_failed_caddyfile_write_returns_false(self):
        with patch("subprocess.Popen", side_effect=OSError("simulated write failure")):
            self.assertFalse(caddy.write_caddyfile("/etc/caddy/Caddyfile", "test"))
            self.assertFalse(caddy.append_caddyfile("/etc/caddy/Caddyfile", "test"))

    def test_http_route_keeps_block_text_and_command_order(self):
        response = self.add_route(name="  MEDIA  ", ip=" 192.0.2.1 ", port=" 8096 ")
        self.assertEqual(response.location, "/")
        self.assertEqual(
            self.content,
            "\nmedia.home.lab {\n    reverse_proxy http://192.0.2.1:8096\n    tls internal\n}\n",
        )
        self.assertEqual(
            [entry[0] for entry in self.commands],
            [
                ["sudo", "cat", "/etc/caddy/Caddyfile"],
                ["sudo", "cat", "/etc/caddy/Caddyfile"],
                ["sudo", "tee", "-a", "/etc/caddy/Caddyfile"],
                ["sudo", "caddy", "validate", "--config", "/etc/caddy/Caddyfile"],
                ["sudo", "systemctl", "reload", "caddy"],
            ],
        )
        self.assertEqual(
            self.flash(),
            ("Successfully added and reloaded route for media.home.lab!", False),
        )
        self.assertIn("ROUTE_ADDED", self.audit_text())

    def test_https_route_keeps_transport_and_internal_tls(self):
        self.add_route(protocol="https")
        self.assertEqual(
            self.content,
            "\nmedia.home.lab {\n    reverse_proxy https://192.0.2.1:8096 {\n"
            "        transport http {\n            tls_insecure_skip_verify\n        }\n"
            "    }\n    tls internal\n}\n",
        )

    def test_validation_messages_and_no_writes(self):
        cases = [
            (
                {"name": "bad.name"},
                "Invalid subdomain name. Only lowercase letters, numbers, and hyphens are allowed.",
            ),
            ({"ip": "not-an-ip"}, "Invalid IP address format."),
            ({"port": "0"}, "Invalid port number. Must be between 1 and 65535."),
            ({"port": "65536"}, "Invalid port number. Must be between 1 and 65535."),
            ({"port": "abc"}, "Invalid port number. Must be between 1 and 65535."),
            ({"protocol": "ftp"}, "Invalid protocol selected."),
            ({"base_domain": "other.lab"}, "Unauthorized base domain selection."),
        ]
        for fields, message in cases:
            with self.subTest(fields=fields):
                self.commands.clear()
                response = self.add_route(**fields)
                self.assertEqual(response.location, "/")
                self.assertEqual(self.flash(), (message, True))
                self.assertEqual(self.commands, [])

    def test_duplicate_route_does_not_write(self):
        self.content = "media.home.lab {\n    reverse_proxy 192.0.2.1:8096\n}\n"
        before = self.content
        self.add_route()
        self.assertEqual(
            self.flash(), ("Route for media.home.lab already exists!", True)
        )
        self.assertEqual(self.content, before)
        self.assertEqual(len(self.commands), 1)

    def test_append_failure_does_not_validate_or_reload(self):
        self.write_code = 1
        self.add_route()
        self.assertEqual(
            self.flash(),
            ("Failed to write to Caddyfile. Check sudo permissions.", True),
        )
        self.assertEqual(self.content, "")
        self.assertFalse(
            any(
                "systemctl" in entry[0] or "validate" in entry[0]
                for entry in self.commands
            )
        )

    def test_add_rolls_back_only_when_both_commands_fail(self):
        for validation, reload in ((0, 0), (1, 0), (0, 1), (1, 1)):
            with self.subTest(validation=validation, reload=reload):
                self.content = "# existing configuration\n"
                self.commands.clear()
                self.validate_code = validation
                self.reload_code = reload
                self.add_route()
                if validation and reload:
                    self.assertEqual(self.content, "# existing configuration\n")
                    self.assertEqual(
                        self.flash(),
                        (
                            "Caddy configuration validation/reload failed. Changes were rolled back safely.",
                            True,
                        ),
                    )
                    self.assertEqual(
                        self.commands[-1][0], ["sudo", "tee", "/etc/caddy/Caddyfile"]
                    )
                else:
                    self.assertIn("media.home.lab", self.content)
                    self.assertFalse(self.flash()[1])

    def test_add_exception_keeps_error_message(self):
        with patch("subprocess.run", side_effect=OSError("simulated command failure")):
            self.add_route()
        self.assertEqual(
            self.flash(),
            ("An unexpected error occurred while modifying the Caddyfile.", True),
        )
        self.assertIn("ROUTE_ADD_ERROR", self.audit_text())

    def test_simple_removal_preserves_other_routes(self):
        self.content = (
            "media.home.lab {\n    reverse_proxy 192.0.2.1:8096\n}\n\n"
            "other.home.lab {\n    reverse_proxy 192.0.2.2:8080\n}\n"
        )
        self.authenticate()
        response = self.client.post(
            "/", data={"action": "remove", "route": " media.home.lab "}
        )
        self.assertEqual(response.location, "/")
        self.assertNotIn("media.home.lab", self.content)
        self.assertIn("other.home.lab", self.content)
        self.assertEqual(
            self.flash(), ("Successfully removed route: media.home.lab", False)
        )
        self.assertEqual(
            self.commands[-1],
            (["sudo", "systemctl", "reload", "caddy"], {"check": True}, None),
        )

    def test_nested_removal_keeps_known_limitation(self):
        self.content = caddy.build_route_block(
            "media.home.lab", "192.0.2.1", "8096", "https"
        )
        self.authenticate()
        self.client.post("/", data={"action": "remove", "route": "media.home.lab"})
        self.assertEqual(self.content, "\n\n    }\n    tls internal\n}\n")

    def test_invalid_removal_does_not_write(self):
        self.authenticate()
        self.client.post("/", data={"action": "remove", "route": "missing.home.lab"})
        self.assertEqual(self.flash(), ("Invalid route selection for removal.", True))
        self.assertEqual(len(self.commands), 1)

    def test_remove_write_failure_keeps_message_and_does_not_reload(self):
        self.content = caddy.build_route_block(
            "media.home.lab", "192.0.2.1", "8096", "http"
        )
        self.write_code = 1
        self.authenticate()
        self.client.post("/", data={"action": "remove", "route": "media.home.lab"})
        self.assertEqual(
            self.flash(), ("Failed to update Caddyfile. Check sudo permissions.", True)
        )
        self.assertNotIn("systemctl", self.commands[-1][0])

    def test_remove_reload_failure_keeps_error_without_rollback(self):
        self.content = caddy.build_route_block(
            "media.home.lab", "192.0.2.1", "8096", "http"
        )
        self.reload_code = 1
        self.authenticate()
        self.client.post("/", data={"action": "remove", "route": "media.home.lab"})
        self.assertEqual(
            self.flash(), ("An error occurred while removing the route.", True)
        )
        self.assertNotIn("media.home.lab", self.content)
        self.assertIn("ROUTE_REMOVE_ERROR", self.audit_text())
