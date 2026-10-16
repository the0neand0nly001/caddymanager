import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from flask import render_template
from markupsafe import escape

from caddy_manager import __version__, auth
from tests.support import AppTestCase


class WebTests(AppTestCase):
    def test_existing_routes_and_new_dashboard_api_methods(self):
        routes = {
            rule.rule: (rule.endpoint, rule.methods)
            for rule in self.app.url_map.iter_rules()
        }
        self.assertEqual(
            {path: value[0] for path, value in routes.items()},
            {
                "/static/<path:filename>": "static",
                "/login": "login",
                "/logout": "logout",
                "/": "index",
                "/api/metrics": "api_metrics",
                "/api/overview": "api_overview",
                "/api/services/check": "api_services",
                "/api/activity": "api_activity",
                "/api/check-status": "check_status",
                "/download-ca": "download_ca",
            },
        )
        self.assertEqual(routes["/"][1], {"GET", "HEAD", "POST", "OPTIONS"})
        self.assertEqual(routes["/api/check-status"][1], {"POST", "OPTIONS"})

    def test_anonymous_requests_keep_redirects_and_metrics_response(self):
        for path in ("/", "/download-ca"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.location, "/login")
        response = self.client.get("/api/metrics")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json, {"error": "Unauthorized"})

    def test_login_reads_credentials_and_logout_clears_session(self):
        response = self.client.post(
            "/login", data={"username": "owner", "password": "test-password"}
        )
        self.assertEqual(response.location, "/")
        self.assertIn("LOGIN_SUCCESS", self.audit_text())
        with self.client.session_transaction() as state:
            self.assertTrue(state["logged_in"])
            state["flash_message"] = "old message"
        response = self.client.get("/logout")
        self.assertEqual(response.location, "/login")
        self.assertIn("LOGOUT", self.audit_text())
        with self.client.session_transaction() as state:
            self.assertEqual(dict(state), {})

    def test_failed_login_keeps_the_same_error(self):
        response = self.client.post(
            "/login", data={"username": "owner", "password": "wrong"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid username or password.", response.data)
        self.assertIn("LOGIN_FAILED", self.audit_text())
        with self.client.session_transaction() as state:
            self.assertFalse(state.get("logged_in", False))

    def test_credentials_are_reloaded_after_the_file_changes(self):
        self.client.get("/login")
        self.credentials.write_text(
            "new-owner\n" + auth.generate_password_hash("new-password"),
            encoding="utf-8",
        )
        response = self.client.post(
            "/login", data={"username": "new-owner", "password": "new-password"}
        )
        self.assertEqual(response.location, "/")

    def test_missing_credentials_keep_default_login(self):
        self.credentials.unlink()
        response = self.client.post(
            "/login", data={"username": "admin", "password": "admin"}
        )
        self.assertEqual(response.location, "/")

    def test_csrf_rejection_keeps_dashboard_response_and_status(self):
        self.app.config["WTF_CSRF_ENABLED"] = True
        response = self.client.post(
            "/login", data={"username": "owner", "password": "test-password"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"Cross-Site Request Forgery (CSRF) token missing or invalid.",
            response.data,
        )
        self.assertIn("CSRF_ERROR", self.audit_text())

    def test_csrf_token_works_for_login_and_json_health_check(self):
        self.app.config["WTF_CSRF_ENABLED"] = True
        page = self.client.get("/login")
        token = (
            re.search(rb'name="csrf_token" value="([^"]+)"', page.data)
            .group(1)
            .decode()
        )
        response = self.client.post(
            "/login",
            data={
                "username": "owner",
                "password": "test-password",
                "csrf_token": token,
            },
        )
        self.assertEqual(response.location, "/")
        response = self.client.post(
            "/api/check-status",
            json={"target": "192.0.2.1:8096"},
            headers={"X-CSRFToken": token},
        )
        self.assertEqual(response.json, {"status": "Online"})
        self.connection.connect_ex.assert_called_with(("192.0.2.1", 8096))

    def test_login_rate_limit_is_still_ten_per_minute(self):
        self.limiter.enabled = True
        for _ in range(10):
            self.assertEqual(self.client.get("/login").status_code, 200)
        self.assertEqual(self.client.get("/login").status_code, 429)

    def test_session_cookie_settings_are_unchanged(self):
        self.assertFalse(self.app.config["SESSION_COOKIE_SECURE"])
        self.assertTrue(self.app.config["SESSION_COOKIE_HTTPONLY"])
        self.assertEqual(self.app.config["SESSION_COOKIE_SAMESITE"], "Lax")

    def test_flash_message_is_consumed_after_one_page(self):
        self.add_route()
        first = self.client.get("/")
        second = self.client.get("/")
        self.assertIn(
            b"Successfully added and reloaded route for media.home.lab!", first.data
        )
        self.assertNotIn(
            b"Successfully added and reloaded route for media.home.lab!", second.data
        )

    def test_certificate_download_keeps_filename_and_command_paths(self):
        self.authenticate()
        response = self.client.get("/download-ca")
        self.addCleanup(response.close)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"test root certificate\n")
        self.assertIn("caddy-root-ca.crt", response.headers["Content-Disposition"])
        self.assertEqual(
            self.commands[0][0],
            [
                "sudo",
                "/usr/bin/cp",
                "/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt",
                str(self.directory / "root.crt"),
            ],
        )
        self.assertIn("DOWNLOAD_CA", self.audit_text())

    def test_failed_certificate_copy_keeps_404(self):
        self.authenticate()
        with patch("subprocess.run", side_effect=OSError("simulated copy failure")):
            response = self.client.get("/download-ca")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, b"Caddy root CA certificate not found.")

    def test_rendered_login_matches_original(self):
        fixture = Path(__file__).parent / "fixtures" / "original_ui.json"
        cases = json.loads(fixture.read_text(encoding="utf-8"))
        with patch.dict(
            self.app.jinja_env.globals, csrf_token=lambda: "baseline-csrf-token"
        ), patch("flask_wtf.csrf.generate_csrf", return_value="baseline-csrf-token"):
            for case in cases:
                if case["template"] != "login.html":
                    continue
                with self.subTest(page=case["name"]), self.app.test_request_context(
                    "/"
                ):
                    rendered = render_template(case["template"], **case["context"])
                    self.assertEqual(
                        hashlib.sha256(rendered.encode()).hexdigest(), case["sha256"]
                    )

    def test_dashboard_preserves_controls_data_and_escaping(self):
        class Elements(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids = []
                self.names = []

            def handle_starttag(self, tag, attributes):
                attributes = dict(attributes)
                if "id" in attributes:
                    self.ids.append(attributes["id"])
                if "name" in attributes:
                    self.names.append(attributes["name"])

        fixture = Path(__file__).parent / "fixtures" / "original_ui.json"
        cases = json.loads(fixture.read_text(encoding="utf-8"))
        for case in cases:
            if case["template"] != "dashboard.html":
                continue
            with self.subTest(page=case["name"]), self.app.test_request_context("/"):
                rendered = render_template("dashboard.html", **case["context"])
                elements = Elements()
                elements.feed(rendered)
                self.assertEqual(len(elements.ids), len(set(elements.ids)))
                self.assertTrue(
                    {
                        "appSidebar",
                        "settingsButton",
                        "sidebarCollapse",
                        "mobileMenu",
                        "serviceRows",
                        "checkAllServices",
                        "activityRows",
                        "systemWarnings",
                        "metric-cpu",
                        "metric-ram",
                        "metric-routes",
                        "domainFilter",
                        "toggleTargets",
                    }.issubset(elements.ids)
                )
                self.assertTrue(
                    {
                        "action",
                        "csrf_token",
                        "name",
                        "base_domain",
                        "ip",
                        "port",
                        "protocol",
                        "route",
                    }.issubset(elements.names)
                )
                for route in case["context"]["routes"]:
                    self.assertIn(str(escape(route["domain"])), rendered)
                    self.assertIn(str(escape(route["target"])), rendered)
                message = case["context"].get("message")
                if message:
                    self.assertIn(str(escape(message)), rendered)
                self.assertNotIn('<script>alert("x")</script>', rendered)
                self.assertIn('href="/download-ca"', rendered)
                self.assertIn('href="/logout"', rendered)

    def test_version_is_two_and_appears_in_the_dashboard(self):
        self.authenticate()
        self.assertEqual(__version__, "2.0.0")
        self.assertIn(
            b'class="sidebar-version">V2.0.0</span>', self.client.get("/").data
        )

    def test_legacy_domain_configuration_still_works(self):
        self.settings = {"DOMAIN": "legacy.lab"}
        self.authenticate()
        self.assertIn(
            b'<option value="legacy.lab">legacy.lab</option>', self.client.get("/").data
        )

    def test_unknown_action_redirects_without_writing(self):
        self.authenticate()
        response = self.client.post("/", data={"action": "unknown"})
        self.assertEqual(response.location, "/")
        self.assertEqual(self.commands, [])
