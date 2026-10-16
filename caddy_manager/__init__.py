"""Flask application setup."""

import os

from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect

from .config import BASE_DIR

__version__ = "2.0.0"


def create_app():
    app = Flask("app", root_path=BASE_DIR)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))

    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["60 per minute", "10 per second"],
        storage_uri="memory://",
    )
    app.config.update(
        SESSION_COOKIE_SECURE=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    CSRFProtect(app)
    app.jinja_env.globals["version"] = __version__

    from .auth import register_auth_routes
    from .views import register_views

    register_auth_routes(app, limiter)
    register_views(app)
    return app
