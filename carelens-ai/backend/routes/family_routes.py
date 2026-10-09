import sqlite3

from flask import Blueprint, g, jsonify, request
from werkzeug.security import generate_password_hash

from auth import login_required, primary_required, start_session, user_json
from db import get_db
from routes.auth_routes import _fetch_user
from security import throttle
from utils import api_error, check_identifier, check_name, check_password

bp = Blueprint("family", __name__, url_prefix="/api")

MAX_FAMILY_SIZE = 30


def _validate_member(raw, prefix, errors, with_relationship=True):
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    out["name"], e = check_name(raw.get("name"), "Name")
    if e:
        errors[f"{prefix}.name"] = e
    if with_relationship:
        out["relationship"], e = check_name(raw.get("relationship"), "Relationship", 40)
        if e:
            errors[f"{prefix}.relationship"] = e
    out["login_identifier"], e = check_identifier(raw.get("login_identifier"))
    if e:
        errors[f"{prefix}.login_identifier"] = e
    e = check_password(raw.get("password"), out["login_identifier"])
    if e:
        errors[f"{prefix}.password"] = e
    out["password"] = raw.get("password")
    return out


def _taken(db, identifiers):
    if not identifiers:
        return set()
    marks = ",".join("?" * len(identifiers))
    rows = db.execute(
        f"SELECT login_identifier FROM users WHERE login_identifier IN ({marks})", identifiers
    ).fetchall()
    return {r["login_identifier"].lower() for r in rows}


def _insert_user(db, family_id, m, relationship, is_primary):
    cur = db.execute(
        """INSERT INTO users (family_id, name, relationship, login_identifier, password_hash, is_primary)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (family_id, m["name"], relationship, m["login_identifier"],
         generate_password_hash(m["password"]), 1 if is_primary else 0),
    )
    return cur.lastrowid


@bp.post("/families")
@throttle("create_family", 20, 3600, per="ip")
def create_family():
    data = request.get_json(silent=True) or {}
    errors = {}
    family_name, e = check_name(data.get("family_name"), "Family name")
    if e:
        errors["family_name"] = e
    primary = _validate_member(data.get("primary"), "primary", errors, with_relationship=False)

    members_raw = data.get("members") or []
    if not isinstance(members_raw, list) or len(members_raw) > 12:
        return api_error(422, "validation", "You can add up to 12 members at a time.")
    members = [_validate_member(m, f"members.{i}", errors) for i, m in enumerate(members_raw)]

    seen = {primary["login_identifier"]: "primary"}
    for i, m in enumerate(members):
        ident = m["login_identifier"]
        if ident and ident in seen:
            errors.setdefault(f"members.{i}.login_identifier", "This login ID is already used above.")
        seen.setdefault(ident, f"members.{i}")
    if errors:
        return api_error(422, "validation", "Please check the highlighted fields.", errors)

    db = get_db()
    taken = _taken(db, list(seen))
    if taken:
        fields = {f"{path}.login_identifier": "This login ID is already taken." for ident, path in seen.items() if ident in taken}
        return api_error(409, "identifier_taken", "Some login IDs are already taken.", fields)

    try:
        with db:
            fam_id = db.execute("INSERT INTO families (name) VALUES (?)", (family_name,)).lastrowid
            primary_id = _insert_user(db, fam_id, primary, "Self", True)
            for m in members:
                _insert_user(db, fam_id, m, m["relationship"], False)
    except sqlite3.IntegrityError:
        return api_error(409, "identifier_taken", "One of those login IDs was just taken. Please try another.")

    start_session(primary_id)
    return jsonify(user=user_json(_fetch_user(primary_id))), 201


@bp.get("/family")
@login_required
def get_family():
    rows = get_db().execute(
        """SELECT id, name, relationship, is_primary FROM users
           WHERE family_id = ? ORDER BY is_primary DESC, id""",
        (g.user["family_id"],),
    ).fetchall()
    # Only identity/membership details are exposed here — never personal data.
    members = [
        {"id": r["id"], "name": r["name"], "relationship": r["relationship"],
         "is_primary": bool(r["is_primary"]), "is_you": r["id"] == g.user["id"]}
        for r in rows
    ]
    return jsonify(family={"id": g.user["family_id"], "name": g.user["family_name"]}, members=members)


@bp.post("/family/members")
@primary_required
def add_member():
    errors = {}
    m = _validate_member(request.get_json(silent=True), "member", errors)
    if errors:
        fields = {k.split(".", 1)[1]: v for k, v in errors.items()}
        return api_error(422, "validation", "Please check the highlighted fields.", fields)
    db = get_db()
    count = db.execute("SELECT COUNT(*) AS n FROM users WHERE family_id = ?", (g.user["family_id"],)).fetchone()["n"]
    if count >= MAX_FAMILY_SIZE:
        return api_error(422, "family_full", "This family has reached its member limit.")
    if _taken(db, [m["login_identifier"]]):
        msg = "This login ID is already taken."
        return api_error(409, "identifier_taken", msg, {"login_identifier": msg})
    try:
        with db:
            new_id = _insert_user(db, g.user["family_id"], m, m["relationship"], False)
    except sqlite3.IntegrityError:
        msg = "This login ID is already taken."
        return api_error(409, "identifier_taken", msg, {"login_identifier": msg})
    return jsonify(member={"id": new_id, "name": m["name"], "relationship": m["relationship"],
                           "is_primary": False, "is_you": False}), 201


@bp.get("/family/members/<int:member_id>")
@login_required
def member_profile(member_id):
    """Membership details only, plus what this member has explicitly shared with the viewer."""
    import access
    from routes.sharing_routes import _label, TYPES
    db = get_db()
    m = db.execute("SELECT id, name, relationship, is_primary, created_at FROM users WHERE id = ? AND family_id = ?",
                   (member_id, g.user["family_id"])).fetchone()
    if not m:
        return api_error(404, "not_found", "We couldn't find that family member.")
    shared = [] if m["id"] == g.user["id"] else [
        {"id": r["id"], "resource_type": r["resource_type"], "resource_id": r["resource_id"],
         "type_label": TYPES[r["resource_type"]], "label": _label(db, r["resource_type"], r["resource_id"]), "shared_at": r["created_at"]}
        for r in access.received_grants(db, g.user["id"]) if r["owner_id"] == m["id"]]
    return jsonify(member={"id": m["id"], "name": m["name"], "relationship": m["relationship"], "is_primary": bool(m["is_primary"]),
                           "is_you": m["id"] == g.user["id"], "joined_at": m["created_at"], "status": "Active"}, shared_with_you=shared)


@bp.patch("/family/members/<int:member_id>")
@primary_required
def update_member(member_id):
    d = request.get_json(silent=True) or {}
    rel, e = check_name(d.get("relationship"), "Relationship", 40)
    if e:
        return api_error(422, "validation", e, {"relationship": e})
    db = get_db()
    row = db.execute("SELECT id FROM users WHERE id = ? AND family_id = ? AND is_primary = 0", (member_id, g.user["family_id"])).fetchone()
    if not row:
        return api_error(404, "not_found", "We couldn't find that family member.")
    with db:
        db.execute("UPDATE users SET relationship = ? WHERE id = ?", (rel, member_id))
    return jsonify(ok=True, relationship=rel)
