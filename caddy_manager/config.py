"""Configuration and paths anchored to the installation directory."""

import os
import stat
import tempfile
from threading import RLock

import yaml

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_data_dir():
    return os.environ.get("CADDY_MANAGER_DATA_DIR") or BASE_DIR


CRED_FILE = os.path.join(get_data_dir(), ".credentials")
AUDIT_LOG_FILE = os.path.join(get_data_dir(), "logs", "audit.log")
CONFIG_LOCK = RLock()


def get_config_path():
    config_path = os.path.join(get_data_dir(), "config.yml")
    if not os.path.exists(config_path):
        config_path = "/opt/caddy-manager/config.yml"

    return config_path


def load_config():
    config_path = get_config_path()
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def save_config(settings):
    """Replace configuration atomically in the same directory and keep permissions."""
    path = get_config_path()
    directory = os.path.dirname(path)
    mode = stat.S_IMODE(os.stat(path).st_mode) if os.path.exists(path) else 0o644
    descriptor, temporary = tempfile.mkstemp(prefix=".config-", dir=directory)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            yaml.safe_dump(settings, file, sort_keys=False, allow_unicode=True)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
