import os
from unittest.mock import patch

import yaml

from caddy_manager import caddy, config, domains, views
from tests.support import AppTestCase


class BaseDomainTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.stack.enter_context(patch.object(views, "load_config", config.load_config))
        self.stack.enter_context(patch.object(caddy, "load_config", config.load_config))
        self.config_path = self.directory / "config.yml"
        self.settings["CUSTOM_SETTING"] = {"keep": True}
        self.config_path.write_text(yaml.safe_dump(self.settings), encoding="utf-8")
        self.authenticate()

    def change(self, action="add_domain", domain="extra.lab", tls_mode="internal"):
        return self.client.post(
            "/", data={"action": action, "domain": domain, "tls_mode": tls_mode}
        )

    def test_add_domain_persists_and_preserves_other_configuration(self):
        response = self.change(domain=" Extra.LAB. ", tls_mode="auto")
        saved = config.load_config()
        self.assertEqual(response.location, "/?page=domains")
        self.assertEqual(saved["DOMAINS"], ["home.lab", "testhome.lab", "extra.lab"])
        self.assertEqual(saved["DOMAIN_TLS"], {"extra.lab": "auto"})
        self.assertEqual(saved["CUSTOM_SETTING"], {"keep": True})
        self.assertEqual(saved["ADGUARD_IP"], self.settings["ADGUARD_IP"])
        self.assertIn(b'<option value="extra.lab">', self.client.get("/").data)
        self.assertEqual(
            self.commands,
            [
                (
                    ["sudo", "cat", "/etc/caddy/Caddyfile"],
                    {"capture_output": True, "text": True, "check": True},
                    None,
                )
            ],
        )
        self.assertIn("ADD_DOMAIN", self.audit_text())

    def test_invalid_and_duplicate_domains_do_not_write(self):
        before = self.config_path.read_bytes()
        for value in (
            "home.lab",
            "HOME.LAB.",
            "http://extra.lab",
            "x.lab/path",
            "x.lab:80",
            "*.lab",
            "bad..lab",
            "bad.lab..",
            "-bad.lab",
            "bad-.lab",
            "a" * 64 + ".lab",
            "localhost",
            "192.0.2.1",
            "x.lab\n{tls internal}",
            "",
        ):
            with self.subTest(domain=value):
                self.change(domain=value)
                self.assertTrue(self.flash()[1])
                self.assertEqual(self.config_path.read_bytes(), before)
        self.assertEqual(self.commands, [])

    def test_international_domain_is_saved_as_ascii(self):
        self.change(domain="bücher.example")
        self.assertIn("xn--bcher-kva.example", config.load_config()["DOMAINS"])

    def test_invalid_tls_mode_does_not_write(self):
        before = self.config_path.read_bytes()
        self.change(tls_mode="injected\n}")
        self.assertTrue(self.flash()[1])
        self.assertEqual(self.config_path.read_bytes(), before)

    def test_updates_and_removals_leave_existing_routes_unchanged(self):
        self.content = caddy.build_route_block(
            "old.home.lab", "192.0.2.5", "443", "https"
        )
        before = self.content
        self.change("update_domain", "home.lab", "http")
        self.assertEqual(
            domains.domain_tls_mode(config.load_config(), "home.lab"), "http"
        )
        self.change("remove_domain", "home.lab")
        self.assertNotIn("home.lab", config.load_config()["DOMAINS"])
        self.assertNotIn("home.lab", config.load_config()["DOMAIN_TLS"])
        self.assertEqual(self.content, before)
        self.assertEqual(self.commands, [])
        self.assertIn(b"old.home.lab", self.client.get("/").data)

    def test_removing_all_domains_disables_add_and_can_be_recovered(self):
        for name in self.settings["DOMAINS"]:
            self.change("remove_domain", name)
        self.assertEqual(config.load_config()["DOMAINS"], [])
        page = self.client.get("/").data
        self.assertIn(b"No base domains configured", page)
        self.commands.clear()
        self.add_route()
        self.assertTrue(self.flash()[1])
        self.assertEqual(self.commands, [])
        self.change(domain="restored.lab")
        self.add_route(base_domain="restored.lab")
        self.assertIn("media.restored.lab", self.content)

    def test_stale_domain_action_does_not_write(self):
        before = self.config_path.read_bytes()
        for action in ("update_domain", "remove_domain"):
            self.change(action, "missing.lab")
            self.assertTrue(self.flash()[1])
            self.assertEqual(self.config_path.read_bytes(), before)

    def test_legacy_single_domain_migrates_without_losing_settings(self):
        self.config_path.write_text(
            "DOMAIN: legacy.lab\nWEBSERVER_PORT: 5123\n", encoding="utf-8"
        )
        self.change()
        saved = config.load_config()
        self.assertEqual(saved["DOMAINS"], ["legacy.lab", "extra.lab"])
        self.assertEqual(saved["WEBSERVER_PORT"], 5123)
        self.assertEqual(domains.domain_tls_mode(saved, "legacy.lab"), "internal")

    def test_domain_settings_control_frontend_tls_not_backend_protocol(self):
        for mode in ("internal", "auto", "http"):
            for protocol in ("http", "https"):
                with self.subTest(mode=mode, backend=protocol):
                    self.content = ""
                    self.change("update_domain", "home.lab", mode)
                    self.add_route(protocol=protocol, tls_mode="injected")
                    self.assertEqual(
                        self.content,
                        caddy.build_route_block(
                            "media.home.lab", "192.0.2.1", "8096", protocol, mode
                        ),
                    )
                    self.assertEqual("tls internal" in self.content, mode == "internal")
                    self.assertEqual(
                        self.content.startswith("\nhttp://"), mode == "http"
                    )
                    self.assertIn(f"reverse_proxy {protocol}://", self.content)

    def test_http_only_route_can_be_removed_without_a_dangling_prefix(self):
        self.change("update_domain", "home.lab", "http")
        self.add_route()
        self.client.post("/", data={"action": "remove", "route": "media.home.lab"})
        self.assertNotIn("http://", self.content)
        self.assertFalse(self.flash()[1])

    def test_atomic_write_failure_preserves_configuration(self):
        before = self.config_path.read_bytes()
        with patch.object(os, "replace", side_effect=OSError("simulated save failure")):
            self.change()
        self.assertTrue(self.flash()[1])
        self.assertEqual(self.config_path.read_bytes(), before)
        self.assertEqual(list(self.directory.glob(".config-*")), [])
        self.assertEqual(self.commands, [])

    def test_domain_change_requires_login_and_csrf(self):
        with self.client.session_transaction() as state:
            state.clear()
        self.assertEqual(self.change().location, "/login")
        self.authenticate()
        self.app.config["WTF_CSRF_ENABLED"] = True
        self.change()
        self.assertNotIn("extra.lab", config.load_config()["DOMAINS"])
        self.assertIn("CSRF_ERROR", self.audit_text())

    def test_container_data_directory_is_used_for_saving(self):
        data = self.directory / "container-data"
        data.mkdir()
        (data / "config.yml").write_text(
            "DOMAINS: []\nWEBSERVER_PORT: 5000\n", encoding="utf-8"
        )
        before = self.config_path.read_bytes()
        with patch.dict(os.environ, {"CADDY_MANAGER_DATA_DIR": str(data)}):
            self.change(tls_mode="http")
            self.assertEqual(config.load_config()["DOMAINS"], ["extra.lab"])
        self.assertEqual(self.config_path.read_bytes(), before)
        self.assertEqual(
            yaml.safe_load((data / "config.yml").read_text())["DOMAIN_TLS"],
            {"extra.lab": "http"},
        )
