from unittest.mock import patch

from caddy_manager import monitoring
from tests.support import AppTestCase


class MonitoringTests(AppTestCase):
    def test_metrics_keep_process_units_rounding_and_route_count(self):
        self.authenticate()
        self.content = "media.home.lab {\n    reverse_proxy 192.0.2.1:8096\n}\n"
        response = self.client.get("/api/metrics")
        self.assertEqual(response.json, {"cpu": 12.3, "ram_mb": 25.0, "routes": 1})
        self.process.cpu_percent.assert_called_with(interval=None)

    def test_process_is_reused_between_metrics_requests(self):
        self.authenticate()
        with patch.object(monitoring.psutil, "Process") as factory:
            self.client.get("/api/metrics")
            self.client.get("/api/metrics")
            factory.assert_not_called()

    def test_process_is_recreated_if_initial_sampling_failed(self):
        self.authenticate()
        with patch.object(monitoring, "caddy_proc", None), patch.object(
            monitoring.psutil, "Process", return_value=self.process
        ) as factory:
            self.assertEqual(self.client.get("/api/metrics").json["cpu"], 12.3)
            factory.assert_called_once()

    def test_metrics_failures_keep_zero_values(self):
        self.authenticate()
        self.process.cpu_percent.side_effect = OSError("simulated process failure")
        self.assertEqual(
            self.client.get("/api/metrics").json,
            {"cpu": 0.0, "ram_mb": 0.0, "routes": 0},
        )

    def test_tcp_health_check_keeps_timeout_and_protocol_handling(self):
        for target in (
            "192.0.2.1:8096",
            "http://192.0.2.1:8096",
            "https://192.0.2.1:8096/path",
        ):
            with self.subTest(target=target):
                response = self.client.post(
                    "/api/check-status", json={"target": target}
                )
                self.assertEqual(response.json, {"status": "Online"})
                self.connection.settimeout.assert_called_with(2.0)
                self.connection.connect_ex.assert_called_with(("192.0.2.1", 8096))

    def test_bad_health_targets_keep_down_response(self):
        for target in (
            "",
            "Unknown",
            "192.0.2.1",
            "192.0.2.1:not-a-port",
            "[::1]:8096",
        ):
            with self.subTest(target=target):
                self.assertEqual(
                    self.client.post("/api/check-status", json={"target": target}).json,
                    {"status": "Down"},
                )

    def test_closed_port_and_socket_failure_keep_down_response(self):
        self.connection.connect_ex.return_value = 1
        self.assertEqual(monitoring.check_service_status("192.0.2.1:8096"), "Down")
        self.connection.connect_ex.side_effect = OSError("simulated socket failure")
        self.assertEqual(monitoring.check_service_status("192.0.2.1:8096"), "Down")
