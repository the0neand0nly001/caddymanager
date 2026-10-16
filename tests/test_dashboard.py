import subprocess
from types import SimpleNamespace
from unittest.mock import patch

from caddy_manager import activity, dashboard
from tests.support import AppTestCase


class DashboardTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.stack.enter_context(
            patch.object(dashboard, "load_config", lambda: self.settings)
        )
        self.probe = self.stack.enter_context(
            patch.object(dashboard.socket, "create_connection")
        )
        self.content = (
            "online.home.lab {\n reverse_proxy 192.0.2.1:80\n}\n"
            "same.home.lab {\n reverse_proxy 192.0.2.1:80\n}\n"
            "offline.home.lab {\n reverse_proxy 192.0.2.2:8080\n}\n"
            "localhost {\n tls internal\n}\n"
        )

    def test_new_dashboard_apis_require_login(self):
        for endpoint in ("/api/overview", "/api/activity"):
            self.assertEqual(self.client.get(endpoint).status_code, 401)
        self.assertEqual(
            self.client.post("/api/services/check", json={}).status_code, 401
        )
        self.probe.assert_not_called()

    def test_overview_counts_actual_configuration_without_probing(self):
        self.authenticate()
        with patch.object(
            dashboard,
            "caddy_status",
            return_value={"state": "responding", "source": "Admin API"},
        ):
            response = self.client.get("/api/overview")
        self.assertEqual(response.json["totals"], {"routes": 4, "domains": 2})
        self.assertEqual(response.json["caddy"]["state"], "responding")
        self.assertFalse(response.json["services"][0]["checkable"])
        self.probe.assert_not_called()

    def test_health_checks_deduplicate_targets_and_keep_unknown_separate(self):
        def connect(address, timeout):
            if address[0] == "192.0.2.2":
                raise OSError("closed")
            return self.probe.return_value

        self.probe.side_effect = connect
        self.authenticate()
        response = self.client.post("/api/services/check", json={})
        results = {item["domain"]: item for item in response.json["services"]}
        self.assertEqual(results["online.home.lab"]["status"], "online")
        self.assertEqual(results["same.home.lab"]["status"], "online")
        self.assertEqual(results["offline.home.lab"]["status"], "down")
        self.assertEqual(results["localhost"]["status"], "unconfigured")
        self.assertIsNone(results["localhost"]["checked_at"])
        self.assertIsNotNone(results["online.home.lab"]["checked_at"])
        self.assertEqual(self.probe.call_count, 2)
        self.probe.assert_any_call(("192.0.2.1", 80), timeout=2)

    def test_individual_check_uses_only_the_saved_target(self):
        self.authenticate()
        response = self.client.post(
            "/api/services/check",
            json={"domain": "online.home.lab", "target": "203.0.113.8:22"},
        )
        self.assertEqual(len(response.json["services"]), 1)
        self.probe.assert_called_once_with(("192.0.2.1", 80), timeout=2)

    def test_missing_or_invalid_route_does_not_probe(self):
        self.authenticate()
        for data in ({"domain": "missing.lab"}, {"domain": 42}, ["bad"]):
            self.assertEqual(
                self.client.post("/api/services/check", json=data).status_code, 400
            )
        self.probe.assert_not_called()

    def test_batch_checks_require_csrf(self):
        self.authenticate()
        self.app.config["WTF_CSRF_ENABLED"] = True
        self.client.post("/api/services/check", json={})
        self.probe.assert_not_called()
        self.assertIn("CSRF_ERROR", self.audit_text())

    def test_ipv6_and_scheme_targets_are_parsed_without_changing_legacy_checks(self):
        self.assertEqual(dashboard.target_address("[::1]:8096"), ("::1", 8096))
        self.assertEqual(
            dashboard.target_address("https://192.0.2.1:443"), ("192.0.2.1", 443)
        )
        for invalid in (
            "Unknown",
            "",
            "host:99999",
            "http://user:pass@host:80",
            "ftp://host:21",
            "host:notaport",
        ):
            self.assertIsNone(dashboard.target_address(invalid))

    def test_caddy_api_status_is_read_only_and_rejects_invalid_responses(self):
        with patch.object(dashboard, "uses_admin_api", return_value=True), patch.object(
            dashboard, "request_admin_api"
        ) as api:
            for result, state in (
                (SimpleNamespace(returncode=0, stdout='{"apps":{}}'), "responding"),
                (SimpleNamespace(returncode=1, stdout=""), "unavailable"),
                (SimpleNamespace(returncode=0, stdout="not json"), "unavailable"),
            ):
                api.return_value = result
                self.assertEqual(dashboard.caddy_status()["state"], state)
            api.assert_called_with("/config/", timeout=3)

    def test_native_status_uses_systemd_without_sudo_or_reload(self):
        with patch.object(
            dashboard, "uses_admin_api", return_value=False
        ), patch.object(dashboard.subprocess, "run") as run:
            run.return_value = SimpleNamespace(returncode=0, stdout="active\n")
            self.assertEqual(dashboard.caddy_status()["state"], "active")
            run.assert_called_with(
                ["systemctl", "is-active", "caddy"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            run.return_value = SimpleNamespace(returncode=3, stdout="inactive\n")
            self.assertEqual(dashboard.caddy_status()["state"], "inactive")
            run.side_effect = subprocess.TimeoutExpired("systemctl", 3)
            self.assertEqual(dashboard.caddy_status()["state"], "unknown")


class ActivityTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.authenticate()
        self.log = self.directory / "logs" / "audit.log"
        self.log.parent.mkdir(exist_ok=True)

    def test_real_entries_are_newest_first_and_paginate_without_duplicates(self):
        lines = [
            f"[2026-10-16 12:00:00] IP: 192.0.2.1 | Action: ROUTE_ADDED | Details: event {index}\n"
            for index in range(125)
        ]
        self.log.write_text("".join(lines), encoding="utf-8")
        details = []
        cursor = None
        for _ in range(10):
            path = "/api/activity" + (f"?before={cursor}" if cursor is not None else "")
            result = self.client.get(path).json
            details.extend(entry["details"] for entry in result["entries"])
            cursor = result["next_cursor"]
            if cursor is None:
                break
        self.assertEqual(details, [f"event {index}" for index in reversed(range(125))])
        self.assertIsNone(cursor)

    def test_bounded_pages_handle_utf8_and_partial_lines(self):
        self.log.write_text(
            "".join(
                f"[time] IP: ip | Action: TEST | Details: café {index}\n"
                for index in range(30)
            )
            + "[unfinished",
            encoding="utf-8",
        )
        details = []
        cursor = None
        with patch.object(activity, "PAGE_BYTES", 200):
            for _ in range(50):
                result = activity.read_activity(before=cursor)
                details.extend(entry["details"] for entry in result["entries"])
                cursor = result["next_cursor"]
                if cursor is None:
                    break
        self.assertEqual(details, [f"café {index}" for index in reversed(range(30))])

    def test_missing_log_is_empty_and_bad_cursors_do_not_read_other_files(self):
        self.assertEqual(
            self.client.get("/api/activity").json, {"entries": [], "next_cursor": None}
        )
        self.log.write_text("event\n", encoding="utf-8")
        for cursor in ("-1", "99999", "abc", "../../config.yml"):
            self.assertEqual(
                self.client.get("/api/activity?before=" + cursor).status_code, 400
            )

    def test_unparsed_lines_are_retained_and_text_is_not_interpreted(self):
        self.log.write_text(
            "[time] IP: ip | Action: TEST | Details: <script>alert(1)</script>\nold format\n",
            encoding="utf-8",
        )
        result = self.client.get("/api/activity").json
        self.assertEqual(result["entries"][0]["action"], "UNPARSED")
        self.assertEqual(result["entries"][1]["details"], "<script>alert(1)</script>")

    def test_unreadable_log_reports_an_error_instead_of_empty_history(self):
        with patch.object(activity, "open", side_effect=PermissionError("denied")):
            response = self.client.get("/api/activity")
        self.assertEqual(response.status_code, 503)
        self.assertIn("permissions", response.json["error"])
