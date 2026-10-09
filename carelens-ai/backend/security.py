"""Cross-cutting security helpers: request checks, response headers, rate limiting, audit events, safe file replies.

Everything here is additive: it wraps the existing routes and never changes what they store.
"""
import functools
import io
import os
import time
from urllib.parse import urlparse

from flask import current_app, g, request, send_file

from utils import RateLimiter, api_error, now_iso

LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]"}
MAX_JSON_BYTES = 256 * 1024  # every JSON request in this app is small; uploads use multipart

# The web app is served by this server, so scripts, styles, images and connections may only come from itself.
CSP_APP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
           "font-src 'self' data:; connect-src 'self'; media-src 'self' blob:; object-src 'none'; base-uri 'self'; "
           "form-action 'self'; frame-ancestors 'none'")
CSP_API = "default-src 'none'; frame-ancestors 'none'"
CSP_IMAGE_FILE = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
# The voice assistant needs the microphone on this site only; nothing else sensitive is ever needed.
PERMISSIONS = "camera=(), geolocation=(), payment=(), usb=(), bluetooth=(), serial=(), microphone=(self)"


# ---------------------------------------------------------------- host & origin checks
def _hostname(host):
    host = (host or "").strip().lower()
    if host.startswith("["):  # [::1]:5000
        return host.split("]")[0] + "]"
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


def allowed_hosts():
    extra = {_hostname(x) for x in os.environ.get("CARELENS_ALLOWED_HOSTS", "").split(",") if x.strip()}
    render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
    if render_host:
        extra.add(_hostname(render_host))
    return LOOPBACK_HOSTS | extra


def host_ok():
    """Refuse requests whose Host header isn't this machine (defeats DNS-rebinding attacks from other web sites)."""
    return _hostname(request.environ.get("HTTP_HOST") or request.host) in allowed_hosts()


def origin_ok(origin):
    """A browser's Origin must be this very site (same scheme-less host:port), or one listed by the owner.

    Other local web pages (a different port on localhost) are NOT trusted: they share cookies with this site, so
    trusting 'any localhost' would let them act as the signed-in user."""
    try:
        o = urlparse(origin)
    except ValueError:
        return False
    if o.scheme not in ("http", "https") or not o.netloc:
        return False  # includes the literal "null" origin
    hosts = {request.host}
    if request.remote_addr in ("127.0.0.1", "::1"):  # the Vite dev proxy forwards the browser's own host
        hosts.add(request.headers.get("X-Forwarded-Host", ""))
    if o.netloc in hosts:
        return True
    extra = {x.strip() for x in os.environ.get("CARELENS_ALLOWED_ORIGINS", "").split(",") if x.strip()}
    return origin in extra or o.netloc in extra


def fetch_site_ok():
    """Sec-Fetch-Site is set by the browser and can't be forged by a web page."""
    site = request.headers.get("Sec-Fetch-Site")
    return site in (None, "", "same-origin", "none")


def json_size_ok():
    n = request.content_length
    return n is None or n <= MAX_JSON_BYTES


# ---------------------------------------------------------------- response headers
def apply_headers(resp):
    h = resp.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Referrer-Policy", "no-referrer")
    h.setdefault("Permissions-Policy", PERMISSIONS)
    h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    h.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    h.setdefault("X-Permitted-Cross-Domain-Policies", "none")
    h.setdefault("Content-Security-Policy", CSP_API if request.path.startswith("/api/") else CSP_APP)
    if request.path.startswith("/api/"):
        h["Cache-Control"] = "no-store"
        h["Pragma"] = "no-cache"
    elif request.path in ("/", "/index.html") or "." not in request.path.rsplit("/", 1)[-1]:
        h.setdefault("Cache-Control", "no-cache")
    if request.is_secure or request.headers.get("X-Forwarded-Proto") == "https":
        h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return resp


def send_document(data, mimetype, filename):
    """Serve a stored document from memory. Images get a sandboxing policy; PDFs rely on nosniff + validated type."""
    resp = send_file(io.BytesIO(data), mimetype=mimetype, as_attachment=False, download_name=filename)
    if mimetype.startswith("image/"):
        resp.headers["Content-Security-Policy"] = CSP_IMAGE_FILE
    return resp


# ---------------------------------------------------------------- rate limiting
_limiters = {}


def _limiter(name, limit, window):
    lim = _limiters.get(name)
    if lim is None:
        lim = _limiters[name] = RateLimiter(limit, window)
    return lim


def reset_limiters():
    """Fresh counters (called by create_app so each app instance, e.g. each test, starts clean)."""
    for lim in _limiters.values():
        lim.clear()


def throttle(name, limit, window_seconds, per="user"):
    """Allow at most `limit` calls per window, per signed-in user (or per IP address with per='ip')."""

    def deco(view):
        @functools.wraps(view)
        def wrapped(*args, **kwargs):
            if current_app.config.get("RATELIMIT_ENABLED", True):
                who = (g.user["id"] if per == "user" and getattr(g, "user", None) is not None else request.remote_addr)
                lim = _limiter(name, limit, window_seconds)
                key = f"{name}|{who}"
                lim.hit(key)
                if lim.count(key) > limit:
                    return api_error(429, "too_many_requests", "You're doing that very quickly. Please wait a few minutes and try again.")
            return view(*args, **kwargs)

        return wrapped

    return deco


# ---------------------------------------------------------------- audit trail (no message text, no data)
EVENT_LABELS = {
    "login": "Signed in",
    "login_failed": "Wrong password entered",
    "login_blocked": "Sign-in paused after too many attempts",
    "password_changed": "Password changed",
    "signed_out_everywhere": "Signed out of all devices",
    "assistant_declined": "Assistant request declined for safety",
    "session_expired": "Session ended after inactivity",
}


def record_event(db, user_id, kind, detail=None):
    """Append a security event. Never raises into the caller: auditing must not break a request."""
    try:
        with db:
            db.execute("INSERT INTO security_events (user_id, kind, detail, ip, created_at) VALUES (?,?,?,?,?)",
                       (user_id, kind, detail, request.remote_addr, now_iso()))
            if user_id is not None:  # keep the newest 300 per person
                db.execute("""DELETE FROM security_events WHERE user_id = ? AND id NOT IN
                              (SELECT id FROM security_events WHERE user_id = ? ORDER BY id DESC LIMIT 300)""", (user_id, user_id))
    except Exception:  # pragma: no cover
        current_app.logger.exception("could not record security event")


def now_ts():
    return int(time.time())
