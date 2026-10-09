from flask import Blueprint, g, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from auth import login_required, start_session, user_json
from db import get_db
from security import EVENT_LABELS, record_event
from utils import RateLimiter, api_error, check_identifier, check_name, check_password

bp = Blueprint("auth", __name__, url_prefix="/api")

_login_limiter = RateLimiter(limit=10, window_seconds=600)      # per login ID + address
_account_limiter = RateLimiter(limit=40, window_seconds=600)    # per login ID from anywhere (slows distributed guessing)
_password_limiter = RateLimiter(limit=5, window_seconds=600)


def reset_limiters():
    """Called by create_app so each app instance starts with clean counters."""
    for lim in (_login_limiter, _account_limiter, _password_limiter):
        lim.clear()


# Used to keep response time similar when the login ID doesn't exist.
_DUMMY_HASH = generate_password_hash("not-a-real-password")


def _fetch_user(user_id):
    return get_db().execute(
        """SELECT u.id, u.family_id, u.name, u.relationship, u.login_identifier,
                  u.is_primary, u.preferred_language, f.name AS family_name, f.is_sample
           FROM users u JOIN families f ON f.id = u.family_id WHERE u.id = ?""",
        (user_id,),
    ).fetchone()


@bp.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    ident = (data.get("login_identifier") or "").strip().lower() if isinstance(data.get("login_identifier"), str) else ""
    password = data.get("password") if isinstance(data.get("password"), str) else ""
    fields = {}
    if not ident:
        fields["login_identifier"] = "Enter your login ID."
    if not password:
        fields["password"] = "Enter your password."
    if fields:
        return api_error(422, "validation", "Please fill in both fields.", fields)

    if len(ident) > 80 or len(password) > 200:  # nothing valid is this long; don't spend time hashing it
        return api_error(401, "invalid_credentials", "That login ID or password doesn't look right.")
    key = f"{ident}|{request.remote_addr}"
    db = get_db()
    if _login_limiter.blocked(key) or _account_limiter.blocked(ident):
        known = db.execute("SELECT id FROM users WHERE login_identifier = ?", (ident,)).fetchone()
        record_event(db, known["id"] if known else None, "login_blocked")
        return api_error(429, "too_many_attempts", "Too many attempts. Please wait a few minutes and try again.")

    row = db.execute(
        "SELECT id, password_hash FROM users WHERE login_identifier = ?", (ident,)
    ).fetchone()
    ok = check_password_hash(row["password_hash"] if row else _DUMMY_HASH, password)
    if not (row and ok):
        _login_limiter.hit(key)
        _account_limiter.hit(ident)
        if row:
            record_event(db, row["id"], "login_failed")
        return api_error(401, "invalid_credentials", "That login ID or password doesn't look right.")

    _login_limiter.reset(key)
    start_session(row["id"])
    record_event(db, row["id"], "login")
    return jsonify(user=user_json(_fetch_user(row["id"])))


@bp.post("/auth/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@bp.get("/auth/me")
@login_required
def me():
    return jsonify(user=user_json(g.user))


@bp.patch("/me")
@login_required
def update_profile():
    data = request.get_json(silent=True) or {}
    from services.ai import LANGUAGES
    errors = {}
    name, err = (g.user["name"], None) if "name" not in data else check_name(data.get("name"))
    if err:
        errors["name"] = err
    lang = data.get("preferred_language", g.user["preferred_language"])
    if lang not in LANGUAGES:
        errors["preferred_language"] = "Choose one of the available languages."
    if errors:
        return api_error(422, "validation", "Please check the highlighted fields.", errors)
    db = get_db()
    with db:
        db.execute("UPDATE users SET name = ?, preferred_language = ? WHERE id = ?", (name, lang, g.user["id"]))
    return jsonify(user=user_json(_fetch_user(g.user["id"])))


@bp.post("/me/password")
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    key = f"pw|{g.user['id']}"
    if _password_limiter.blocked(key):
        return api_error(429, "too_many_attempts", "Too many attempts. Please wait a few minutes and try again.")
    current, new = data.get("current_password"), data.get("new_password")
    err = check_password(new, g.user["login_identifier"])
    if not err and isinstance(current, str) and new == current:
        err = "Choose a password you haven't used just now."
    if err:
        return api_error(422, "validation", err, {"new_password": err})
    db = get_db()
    row = db.execute("SELECT password_hash FROM users WHERE id = ?", (g.user["id"],)).fetchone()
    if not isinstance(current, str) or not check_password_hash(row["password_hash"], current):
        _password_limiter.hit(key)
        msg = "That isn't your current password."
        return api_error(422, "validation", msg, {"current_password": msg})
    with db:
        db.execute(
            "UPDATE users SET password_hash = ?, token_version = token_version + 1 WHERE id = ?",
            (generate_password_hash(new), g.user["id"]),
        )
    _password_limiter.reset(key)
    start_session(g.user["id"])  # keep this device signed in; all other sessions end
    record_event(db, g.user["id"], "password_changed")
    return jsonify(ok=True)


@bp.get("/me/security")
@login_required
def security_overview():
    """The signed-in person's own recent security events. Contains no health data and no message text."""
    rows = get_db().execute(
        "SELECT kind, detail, ip, created_at FROM security_events WHERE user_id = ? ORDER BY id DESC LIMIT 30", (g.user["id"],)
    ).fetchall()
    return jsonify(events=[{"kind": r["kind"], "label": EVENT_LABELS.get(r["kind"], r["kind"]), "detail": r["detail"],
                            "ip": r["ip"], "at": r["created_at"]} for r in rows])


@bp.post("/me/security/sign-out-everywhere")
@login_required
def sign_out_everywhere():
    """Ends every session (this browser and any other) by bumping the token counter, then signs this browser out too."""
    db = get_db()
    with db:
        db.execute("UPDATE users SET token_version = token_version + 1 WHERE id = ?", (g.user["id"],))
    record_event(db, g.user["id"], "signed_out_everywhere")
    session.clear()
    return jsonify(ok=True)
