import re
import unittest
from pathlib import Path

import app
from caddy_manager import config

ROOT = Path(__file__).resolve().parents[1]


class DistributionTests(unittest.TestCase):
    def test_app_paths_still_point_to_the_installation_root(self):
        self.assertEqual(Path(config.BASE_DIR), ROOT)
        self.assertEqual(Path(config.CRED_FILE), ROOT / ".credentials")
        self.assertEqual(Path(config.AUDIT_LOG_FILE), ROOT / "logs" / "audit.log")
        self.assertEqual(Path(app.app.template_folder), Path("templates"))
        self.assertEqual(Path(app.app.static_folder), ROOT / "static")

    def test_installer_and_updater_deliver_every_runtime_file(self):
        expected = {
            path.relative_to(ROOT).as_posix()
            for folder in ("caddy_manager", "templates")
            for path in (ROOT / folder).rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        }
        expected.add("requirements.txt")
        for name in ("install.sh", "update.sh"):
            with self.subTest(script=name):
                source = (ROOT / name).read_text(encoding="utf-8")
                array = re.search(r"APP_FILES=\((.*?)\)", source, re.DOTALL).group(1)
                listed = set(re.findall(r'"([^"]+)"', array))
                self.assertEqual(listed, expected)
                self.assertLess(
                    source.index('for app_file in "${APP_FILES[@]}"'),
                    source.index('cp -R "$DOWNLOAD_DIR/." "$INSTALL_DIR/"'),
                )
                self.assertIn("set -eo pipefail", source)
                self.assertIn("CADDY_MANAGER_SOURCE_DIR", source)
                self.assertIn(
                    'python3 -m pip install --break-system-packages -r "$DOWNLOAD_DIR/requirements.txt"',
                    source,
                )
                self.assertIn(
                    "/usr/bin/caddy validate --config /etc/caddy/Caddyfile", source
                )
                self.assertNotIn("config.yml", listed)
                self.assertNotIn(".credentials", listed)

    def test_startup_command_is_unchanged(self):
        installer = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn("ExecStart=/usr/bin/python3 app.py", installer)
        self.assertEqual(app.app.name, "app")
