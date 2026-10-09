import contextlib
import os
import secrets
import sqlite3
from datetime import timedelta
from pathlib import Path

from flask import Flask, request, send_from_directory
from werkzeug.exceptions import BadRequest

import db
import security
from utils import api_error

ROOT = Path(__file__).resolve().parent


def _private(path, mode):
    """Owner-only permissions where the operating system supports them (no effect on Windows)."""
    with contextlib.suppress(OSError):
        os.chmod(path, mode)


def _load_secret_key(app):
    env = os.environ.get("FAMILY_SECRET_KEY")
    if env:
        return env
    path = Path(app.instance_path) / "secret_key"
    if not path.exists():
        try:  # exclusive create with owner-only permissions from the first byte
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as fh:
                fh.write(secrets.token_hex(32))
        except FileExistsError:
            pass
    return path.read_text().strip()


def load_env_file():
    """Load KEY=VALUE pairs from backend/.env (or project-root .env) without overriding real env vars."""
    for path in (ROOT / ".env", ROOT.parent / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip().removeprefix("export ").strip(), v.strip().strip('"').strip("'")
            if k and v:
                os.environ.setdefault(k, v)


def create_app(test_config=None):
    if not test_config:
        load_env_file()
    app = Flask(__name__, instance_path=str(ROOT / "instance"))
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    _private(app.instance_path, 0o700)
    app.config.update(
        DATABASE=str(Path(app.instance_path) / "family.db"),
        SECRET_KEY=None,
        SESSION_COOKIE_NAME="family_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_SECURE=os.environ.get("FAMILY_COOKIE_SECURE") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),
        MAX_CONTENT_LENGTH=12 * 1024 * 1024,
        UPLOAD_DIR=str(Path(app.instance_path) / "uploads"),
        FRONTEND_DIST=str(ROOT.parent / "frontend" / "dist"),
    )
    if test_config:
        app.config.update(test_config)
    if not app.config["SECRET_KEY"]:
        app.config["SECRET_KEY"] = _load_secret_key(app)

    db.init_app(app)
    _private(app.config["DATABASE"], 0o600)
    # a restart can interrupt background processing
    with contextlib.closing(sqlite3.connect(app.config["DATABASE"])) as conn, conn:
        conn.execute("""UPDATE documents SET processing_status = 'failed', processing_note = 'Processing was interrupted. Please try again.' WHERE processing_status = 'processing'""")

    from routes import (ai_routes, auth_routes, care_routes, family_routes, health_routes, personal_routes,
                        search_routes, sharing_routes, wellness_routes)
    security.reset_limiters()
    auth_routes.reset_limiters()
    for module in (auth_routes, family_routes, personal_routes, health_routes, care_routes, sharing_routes, ai_routes, search_routes, wellness_routes):
        app.register_blueprint(module.bp)

    @app.before_request
    def guard_requests():
        # Only this machine's own names are accepted as the site address (stops DNS-rebinding from other web sites).
        if not security.host_ok():
            return api_error(400, "bad_host", "That address isn't allowed.")
        if not (request.path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH", "DELETE"}):
            return None
        # Writes must come from this site itself: foreign Origins and cross-site fetches are refused.
        origin = request.headers.get("Origin")
        if (origin and not security.origin_ok(origin)) or not security.fetch_site_ok():
            return api_error(403, "forbidden_origin", "That request isn't allowed.")
        is_upload = request.method == "POST" and request.path == "/api/me/documents"
        allowed = "multipart/form-data" if is_upload else "application/json"
        # DELETE carries no body; it is covered by SameSite cookies, the Origin check and preflight.
        if request.method != "DELETE" and request.mimetype != allowed:
            return api_error(415, "unsupported_media_type", "That request type isn't supported.")
        if request.mimetype == "application/json" and not security.json_size_ok():
            return api_error(413, "too_large", "That request is too large.")
        return None

    @app.after_request
    def security_headers(resp):
        return security.apply_headers(resp)

    @app.errorhandler(400)
    def bad_request(_e):
        return api_error(400, "bad_request", "That request couldn't be understood.")

    @app.errorhandler(BadRequest)
    def bad_request_exc(_e):
        return api_error(400, "bad_request", "That request couldn't be understood.")

    @app.errorhandler(404)
    def not_found(_e):
        return api_error(404, "not_found", "We couldn't find that.")

    @app.errorhandler(405)
    def not_allowed(_e):
        return api_error(405, "method_not_allowed", "That action isn't supported.")

    @app.errorhandler(413)
    def too_large(_e):
        return api_error(413, "too_large", "That file is too large. The limit is 10 MB.", {"file": "That file is too large. The limit is 10 MB."})

    @app.errorhandler(500)
    def server_error(_e):
        return api_error(500, "server_error", "Something went wrong on our side. Please try again.")

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def spa(path):
        if path.startswith("api/"):
            return api_error(404, "not_found", "We couldn't find that.")
        dist = Path(app.config["FRONTEND_DIST"]).resolve()
        if not (dist / "index.html").exists():
            return ("The web app hasn't been built yet. Run `npm run build` in the frontend folder, "
                    "or use the dev server (see README)."), 503
        if path and (dist / path).resolve().is_relative_to(dist) and (dist / path).is_file():
            return send_from_directory(dist, path)
        return send_from_directory(dist, "index.html")

    return app


if __name__ == "__main__":
    # Local only, and never in debug mode: the Werkzeug debugger can run code on this machine.
    create_app().run(host="127.0.0.1", port=5000, debug=False)
