"""Small shared helpers: error responses, input validation, rate limiting."""
import re
import threading
import time

from flask import jsonify

IDENT_RE = re.compile(r"^[a-z0-9][a-z0-9._@+-]{2,63}$")


def api_error(status, code, message, fields=None):
    body = {"error": {"code": code, "message": message}}
    if fields:
        body["error"]["fields"] = fields
    return jsonify(body), status


def check_name(value, label="Name", maxlen=60):
    v = value.strip() if isinstance(value, str) else ""
    if not v:
        return v, f"{label} is required."
    if len(v) > maxlen:
        return v, f"{label} is too long."
    return v, None


def check_identifier(value):
    v = value.strip().lower() if isinstance(value, str) else ""
    if not v:
        return v, "Login ID is required."
    if not IDENT_RE.match(v):
        return v, "Use 3–64 letters, numbers or . _ @ + - characters."
    return v, None


# Passwords that appear at the top of every leaked-password list. Exact matches only.
COMMON_PASSWORDS = {
    "password", "password1", "password12", "password123", "passw0rd", "p@ssw0rd", "p@ssword", "12345678", "123456789",
    "1234567890", "11111111", "00000000", "88888888", "qwertyui", "qwerty123", "qwertyuiop", "iloveyou", "admin123",
    "administrator", "welcome1", "welcome123", "letmein1", "letmein123", "abcd1234", "abc12345", "1q2w3e4r", "1qaz2wsx",
    "changeme", "changeme123", "test1234", "family123", "carelens", "carelens123", "health123",
}


def check_password(value, identifier=None):
    if not isinstance(value, str) or len(value) < 8:
        return "Use at least 8 characters."
    if len(value) > 128:
        return "Password is too long."
    low = value.strip().lower()
    if low in COMMON_PASSWORDS or len(set(low)) < 3:
        return "That password is too easy to guess. Choose something less common."
    if identifier and low == identifier.strip().lower():
        return "Your password can't be the same as your login ID."
    return None


class RateLimiter:
    """In-memory failure counter. Good enough for a single local process."""

    def __init__(self, limit, window_seconds):
        self.limit, self.window = limit, window_seconds
        self._hits, self._lock = {}, threading.Lock()

    def _recent(self, key):
        cutoff = time.time() - self.window
        hits = [t for t in self._hits.get(key, []) if t > cutoff]
        self._hits[key] = hits
        if len(self._hits) > 5000:  # forget keys that have gone quiet so memory can't grow without bound
            for k in [k for k, v in self._hits.items() if not v or v[-1] <= cutoff]:
                self._hits.pop(k, None)
            self._hits.setdefault(key, hits)
        return hits

    def blocked(self, key):
        with self._lock:
            return len(self._recent(key)) >= self.limit

    def hit(self, key):
        with self._lock:
            self._recent(key).append(time.time())

    def reset(self, key):
        with self._lock:
            self._hits.pop(key, None)

    def count(self, key):
        with self._lock:
            return len(self._recent(key))

    def clear(self):
        with self._lock:
            self._hits.clear()


# ---- shared helpers for the health modules ----
from datetime import datetime, timezone

from flask import request


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def parse_when(value, label="Date"):
    """Accept an ISO date/datetime; return (UTC ISO string, error)."""
    if not isinstance(value, str) or not value.strip():
        return None, f"{label} is required."
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None, f"{label} isn't a valid date."
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"), None


def json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def text_field(data, key, label, maxlen=200, required=False):
    v = data.get(key)
    v = v.strip() if isinstance(v, str) else ""
    if not v:
        return (None, f"{label} is required.") if required else (None, None)
    if len(v) > maxlen:
        return None, f"{label} is too long."
    return v, None


def validation_error(errors):
    return api_error(422, "validation", "Please check the highlighted fields.", errors)
