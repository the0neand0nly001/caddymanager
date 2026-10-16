from contextlib import ExitStack
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

import yaml

from caddy_manager import backend, caddy
from tests.support import AppTestCase

ROOT = Path(__file__).resolve().parents[1]
initialize = runpy.run_path(str(ROOT / "docker" / "entrypoint.py"))["initialize"]


class ApiBackendTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.stack.enter_context(
            patch.dict(os.environ, {"CADDY_ADMIN_URL": "http://caddy:2019"})
        )
        self.caddyfile = self.directory / "Caddyfile"
        self.settings["CADDYFILE_PATH"] = str(self.caddyfile)
        self.caddyfile.write_text(
            "localhost {\n    tls internal\n}\n", encoding="utf-8"
        )
        self.webhook.return_value.__enter__.return_value.read.return_value = b"{}"

    def test_api_file_access_uses_shared_file_without_sudo(self):
        self.assertTrue(caddy.write_caddyfile(str(self.caddyfile), "# first\n"))
        self.assertTrue(caddy.append_caddyfile(str(self.caddyfile), "# second\n"))
        self.assertEqual(
            caddy.read_caddyfile(str(self.caddyfile)), "# first\n# second\n"
        )
        self.assertEqual(self.commands, [])

    def test_adaptation_and_reload_send_exact_file_contents(self):
        expected = self.caddyfile.read_text(encoding="utf-8").encode("utf-8")
        backend.validate_caddyfile(str(self.caddyfile))
        backend.reload_caddy(str(self.caddyfile))
        self.assertEqual(
            [call.args[0].full_url for call in self.webhook.call_args_list],
            ["http://caddy:2019/adapt", "http://caddy:2019/load"],
        )
        for call in self.webhook.call_args_list:
            self.assertEqual(call.args[0].data, expected)
            self.assertEqual(call.args[0].get_header("Content-type"), "text/caddyfile")
            self.assertEqual(call.kwargs["timeout"], 10)

    def test_http_errors_are_reported_and_checked_reload_raises(self):
        def failure(*args, **kwargs):
            raise urllib.error.HTTPError(
                "http://caddy:2019/load",
                400,
                "bad config",
                {},
                io.BytesIO(b"invalid Caddyfile"),
            )

        self.webhook.side_effect = failure
        result = backend.validate_caddyfile(str(self.caddyfile))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "invalid Caddyfile")
        with self.assertRaises(subprocess.CalledProcessError):
            backend.reload_caddy(str(self.caddyfile), check=True)

    def test_unavailable_caddy_is_reported_as_a_failed_result(self):
        self.webhook.side_effect = urllib.error.URLError("connection refused")
        result = backend.reload_caddy(str(self.caddyfile))
        self.assertEqual(result.returncode, 1)
        self.assertIn("connection refused", result.stderr)

    def test_api_add_keeps_validation_and_reload_failure_rule(self):
        original = self.caddyfile.read_text(encoding="utf-8")
        self.webhook.side_effect = urllib.error.URLError("connection refused")
        self.add_route()
        self.assertEqual(self.caddyfile.read_text(encoding="utf-8"), original)
        self.assertTrue(self.flash()[1])
        self.assertIn("Changes were rolled back safely.", self.flash()[0])

    def test_certificate_download_only_requests_public_ca_certificate(self):
        certificate = "-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n"
        self.webhook.return_value.__enter__.return_value.read.return_value = json.dumps(
            {"root_certificate": certificate}
        ).encode()
        self.authenticate()
        response = self.client.get("/download-ca")
        self.addCleanup(response.close)
        self.assertEqual(response.data.decode(), certificate)
        self.assertIn("caddy-root-ca.crt", response.headers["Content-Disposition"])
        self.assertEqual(
            self.webhook.call_args.args[0].full_url, "http://caddy:2019/pki/ca/local"
        )
        self.assertEqual(self.commands, [])


class ContainerInitializationTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(
            patch.dict(
                os.environ,
                {
                    "ADMIN_USERNAME": "owner",
                    "ADMIN_PASSWORD": "password",
                    "CADDY_DOMAINS": "home.lab, testhome.lab",
                },
                clear=True,
            )
        )
        self.state = self.directory / "state"
        self.caddyfile = self.directory / "caddy" / "Caddyfile"

    def test_first_start_creates_configuration_credentials_and_caddyfile(self):
        initialize(self.state, self.caddyfile)
        settings = yaml.safe_load((self.state / "config.yml").read_text())
        self.assertEqual(settings["DOMAINS"], ["home.lab", "testhome.lab"])
        self.assertEqual(settings["CADDYFILE_PATH"], str(self.caddyfile))
        self.assertEqual(
            (self.state / ".credentials").read_text().splitlines()[0], "owner"
        )
        self.assertIn("admin 0.0.0.0:2019", self.caddyfile.read_text())
        self.assertEqual(
            os.environ["FLASK_SECRET_KEY"],
            (self.state / ".flask-secret-key").read_text(),
        )

    def test_restarts_preserve_files_and_session_secret(self):
        initialize(self.state, self.caddyfile)
        initial = {
            path: path.read_bytes()
            for path in self.directory.rglob("*")
            if path.is_file()
        }
        os.environ["ADMIN_PASSWORD"] = "different-password"
        os.environ["CADDY_DOMAINS"] = "different.lab"
        os.environ.pop("FLASK_SECRET_KEY")
        initialize(self.state, self.caddyfile)
        self.assertEqual(
            initial,
            {
                path: path.read_bytes()
                for path in self.directory.rglob("*")
                if path.is_file()
            },
        )
        self.assertEqual(
            os.environ["FLASK_SECRET_KEY"],
            (self.state / ".flask-secret-key").read_text(),
        )

    def test_empty_domain_list_is_rejected_on_first_start(self):
        os.environ["CADDY_DOMAINS"] = " , "
        with self.assertRaises(ValueError):
            initialize(self.state, self.caddyfile)
