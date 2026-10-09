"""Authentication helpers.

Every protected endpoint resolves the caller from the signed session cookie and
never accepts a user id from the client. Personal-data endpoints added later
must filter by g.user["id"]; cross-member access will go through an explicit
permission check (WHAT -> WHO -> WHEN), never through family membership alone.
"""
import os
import time
from functools import wraps

from flask import g, session

from db import get_db
from utils import api_error

# A signed-in browser is signed out after this long without activity (0 disables), and never stays signed in
# longer than MAX_SESSION_SECONDS even if it is used every day.
IDLE_SECONDS = max(0, int(os.environ.get("CARELENS_IDLE_MINUTES", "60") or 0)) * 60
MAX_SESSION_SECONDS = 7 * 24 * 3600


def load_user():
    uid = session.get("uid")
    if uid is None:
        return None
    row = get_db().execute(
        """SELECT u.id, u.family_id, u.name, u.relationship, u.login_identifier,
                  u.is_primary, u.token_version, u.preferred_language, f.name AS family_name, f.is_sample
           FROM users u JOIN families f ON f.id = u.family_id
           WHERE u.id = ?""",
        (uid,),
    ).fetchone()
    # A password change bumps token_version, which ends every older session.
    if row is None or session.get("tv") != row["token_version"]:
        return None
    now = time.time()
    started, last = session.get("iat"), session.get("ts")
    if started is not None and now - started > MAX_SESSION_SECONDS:
        return None
    if IDLE_SECONDS and last is not None and now - last > IDLE_SECONDS:
        return None
    if started is None:  # a session from before this check existed: start counting now
        session["iat"] = int(now)
    if last is None or now - last > 60:  # slide the idle window without rewriting the cookie on every call
        session["ts"] = int(now)
    return row


def start_session(user_id):
    tv = get_db().execute("SELECT token_version FROM users WHERE id = ?", (user_id,)).fetchone()[0]
    session.clear()
    session["uid"] = user_id
    session["tv"] = tv
    session["iat"] = session["ts"] = int(time.time())
    session.permanent = True


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = load_user()
        if user is None:
            session.clear()
            return api_error(401, "unauthenticated", "Please sign in to continue.")
        g.user = user
        return view(*args, **kwargs)

    return wrapped


def primary_required(view):
    @wraps(view)
    def inner(*args, **kwargs):
        if not g.user["is_primary"]:
            return api_error(403, "forbidden", "Only the primary member can do this.")
        return view(*args, **kwargs)

    return login_required(inner)


def user_json(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "relationship": row["relationship"],
        "login_identifier": row["login_identifier"],
        "is_primary": bool(row["is_primary"]),
        "preferred_language": row["preferred_language"],
        "family": {"id": row["family_id"], "name": row["family_name"], "is_sample": bool(row["is_sample"])},
    }
