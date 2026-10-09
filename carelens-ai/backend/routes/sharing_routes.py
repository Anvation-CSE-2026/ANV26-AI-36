"""Sharing: OWNER -> permission -> authorised member. All grants are owner-created,
specific, revocable and optionally time-limited. Shared views enforce them per request."""
from flask import Blueprint, g, jsonify, request

import access
from auth import login_required
from db import get_db
import crypto
from routes.health_routes import emergency_payload, health_payload
from security import send_document, throttle
from services.documents import document_detail, get_document_for, read_document_bytes
from services.ai import LANGUAGES
from utils import api_error, json_body, now_iso, parse_when, validation_error

bp = Blueprint("sharing", __name__, url_prefix="/api")

TYPES = {"document": "Document", "medicine": "Medicines", "health_profile": "Health profile", "emergency": "Emergency information"}


def _label(db, rtype, rid):
    if rtype == "document":
        r = db.execute("SELECT filename FROM documents WHERE id = ?", (rid,)).fetchone()
        return r["filename"] if r else "Deleted document"
    if rtype == "medicine":
        if rid is None:
            return "All active medicines"
        r = db.execute("SELECT name FROM medicines WHERE id = ?", (rid,)).fetchone()
        return r["name"] if r else "Deleted medicine"
    return TYPES[rtype]


def _grant_json(db, r, perspective):
    return {"id": r["id"], "resource_type": r["resource_type"], "resource_id": r["resource_id"],
            "label": _label(db, r["resource_type"], r["resource_id"]),
            "type_label": TYPES[r["resource_type"]], "shared_at": r["created_at"], "expires_at": r["expires_at"],
            "member": {"id": r["other_id"], "name": r["other_name"]}, "status": "active"}


@bp.get("/sharing")
@login_required
def list_sharing():
    db, uid = get_db(), g.user["id"]
    now = now_iso()
    granted = db.execute("""SELECT sp.*, u.id AS other_id, u.name AS other_name FROM sharing_permissions sp
                            JOIN users u ON u.id = sp.grantee_id WHERE sp.owner_id = ? AND sp.revoked_at IS NULL
                            AND (sp.expires_at IS NULL OR sp.expires_at > ?) ORDER BY sp.id DESC""", (uid, now)).fetchall()
    received = db.execute("""SELECT sp.*, u.id AS other_id, u.name AS other_name FROM sharing_permissions sp
                             JOIN users u ON u.id = sp.owner_id JOIN users me ON me.id = sp.grantee_id
                             WHERE sp.grantee_id = ? AND sp.revoked_at IS NULL AND (sp.expires_at IS NULL OR sp.expires_at > ?)
                             AND u.family_id = me.family_id ORDER BY sp.id DESC""", (uid, now)).fetchall()
    act = db.execute("""SELECT a.action, a.resource_type, a.resource_id, a.created_at, u.name AS actor FROM activity_log a
                        JOIN users u ON u.id = a.actor_id WHERE a.owner_id = ? ORDER BY a.id DESC LIMIT 15""", (uid,)).fetchall()
    return jsonify(granted=[_grant_json(db, r, "owner") for r in granted],
                   received=[_grant_json(db, r, "grantee") for r in received],
                   activity=[{**dict(a), "label": _label(db, a["resource_type"], a["resource_id"]) if a["resource_type"] else None} for a in act])


@bp.post("/sharing")
@login_required
def create_share():
    d, db, uid = json_body(), get_db(), g.user["id"]
    errors = {}
    rtype, rid = d.get("resource_type"), d.get("resource_id")
    if rtype not in TYPES:
        errors["resource_type"] = "Choose what to share."
    gid = d.get("grantee_id")
    grantee = db.execute("SELECT id, name FROM users WHERE id = ? AND family_id = ? AND id != ?",
                         (gid, g.user["family_id"], uid)).fetchone() if isinstance(gid, int) else None
    if not grantee:
        errors["grantee_id"] = "Choose a member of your family."
    if rtype == "document":
        if not isinstance(rid, int) or not db.execute("SELECT 1 FROM documents WHERE id = ? AND owner_id = ?", (rid, uid)).fetchone():
            errors["resource_id"] = "Choose one of your documents."
    elif rtype == "medicine":
        if rid is not None and (not isinstance(rid, int) or not db.execute("SELECT 1 FROM medicines WHERE id = ? AND owner_id = ?", (rid, uid)).fetchone()):
            errors["resource_id"] = "Choose one of your medicines."
    elif rtype in TYPES:
        rid = None
    expires = None
    if d.get("expires_at"):
        expires, e = parse_when(d["expires_at"], "Expiry")
        if e:
            errors["expires_at"] = e
        elif expires <= now_iso():
            errors["expires_at"] = "Expiry must be in the future."
    if errors:
        return validation_error(errors)
    existing = db.execute("""SELECT id FROM sharing_permissions WHERE owner_id = ? AND grantee_id = ? AND resource_type = ?
                             AND resource_id IS ? AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at > ?)""",
                          (uid, grantee["id"], rtype, rid, now_iso())).fetchone()
    if existing:
        return api_error(409, "already_shared", f"This is already shared with {grantee['name']}.")
    with db:
        cur = db.execute("INSERT INTO sharing_permissions (owner_id, grantee_id, resource_type, resource_id, created_at, expires_at) VALUES (?,?,?,?,?,?)",
                         (uid, grantee["id"], rtype, rid, now_iso(), expires))
    access.log_activity(db, uid, uid, f"shared with {grantee['name']}", rtype, rid)
    return jsonify(ok=True, id=cur.lastrowid), 201


@bp.delete("/sharing/<int:sid>")
@login_required
def revoke_share(sid):
    db, uid = get_db(), g.user["id"]
    row = db.execute("""SELECT sp.*, u.name AS grantee FROM sharing_permissions sp JOIN users u ON u.id = sp.grantee_id
                        WHERE sp.id = ? AND sp.owner_id = ? AND sp.revoked_at IS NULL""", (sid, uid)).fetchone()
    if not row:
        return api_error(404, "not_found", "We couldn't find that permission.")
    with db:
        db.execute("UPDATE sharing_permissions SET revoked_at = ? WHERE id = ?", (now_iso(), sid))
    access.log_activity(db, uid, uid, f"stopped sharing with {row['grantee']}", row["resource_type"], row["resource_id"])
    return jsonify(ok=True)


# ---------- what other members shared with me (each call re-checks the grant) ----------
def _gone():
    return api_error(404, "not_found", "That isn't available.")


@bp.get("/shared/documents/<int:doc_id>")
@login_required
def shared_document(doc_id):
    db = get_db()
    row, how = get_document_for(db, g.user, doc_id)
    if row is None:
        return _gone()
    owner = db.execute("SELECT id, name FROM users WHERE id = ?", (row["owner_id"],)).fetchone()
    if how == "shared":
        access.log_activity(db, g.user["id"], row["owner_id"], f"{g.user['name']} viewed", "document", doc_id)
    lang = g.user["preferred_language"]
    return jsonify(owner=dict(owner), **document_detail(db, row, lang, include_medicines=False))


@bp.post("/shared/documents/<int:doc_id>/analyze")
@login_required
@throttle("analyze", 30, 3600)
def shared_document_analyze(doc_id):
    from services import ai
    db = get_db()
    row, how = get_document_for(db, g.user, doc_id)
    if row is None:
        return _gone()
    lang = g.user["preferred_language"]
    if not db.execute("SELECT 1 FROM document_extractions WHERE document_id = ?", (doc_id,)).fetchone():
        return api_error(422, "not_processed", "This document hasn't been read yet, so it can't be explained.")
    try:
        ai.analyze_document(db, row, lang)
    except ai.AINotConfigured:
        return api_error(503, "ai_not_configured", "Explanations need the AI assistant, which isn't set up on this device yet.")
    except ai.AIError as exc:
        return api_error(502, "ai_unavailable", exc.user_message or "We couldn't prepare the explanation right now. Please try again.")
    owner = db.execute("SELECT id, name FROM users WHERE id = ?", (row["owner_id"],)).fetchone()
    return jsonify(owner=dict(owner), **document_detail(db, row, lang, include_medicines=False))


@bp.get("/shared/documents/<int:doc_id>/file")
@login_required
def shared_document_file(doc_id):
    db = get_db()
    row, how = get_document_for(db, g.user, doc_id)
    if row is None:
        return _gone()
    try:
        data = read_document_bytes(row)
    except crypto.DecryptionError:
        return api_error(500, "file_unreadable", "This document can't be opened right now.")
    if data is None:
        return _gone()
    return send_document(data, row["file_type"], row["filename"])


def _member_view(owner_id):
    return get_db().execute("SELECT id, name FROM users WHERE id = ? AND family_id = ?", (owner_id, g.user["family_id"])).fetchone()


@bp.get("/shared/people/<int:owner_id>/health")
@login_required
def shared_health(owner_id):
    db = get_db()
    owner = _member_view(owner_id)
    if not owner or owner_id == g.user["id"] or not access.has_grant(db, g.user["id"], owner_id, "health_profile"):
        return _gone()
    access.log_activity(db, g.user["id"], owner_id, f"{g.user['name']} viewed", "health_profile")
    return jsonify(owner=dict(owner), **health_payload(db, owner_id))


@bp.get("/shared/people/<int:owner_id>/emergency")
@login_required
def shared_emergency(owner_id):
    db = get_db()
    owner = _member_view(owner_id)
    if not owner or owner_id == g.user["id"] or not access.has_grant(db, g.user["id"], owner_id, "emergency"):
        return _gone()
    access.log_activity(db, g.user["id"], owner_id, f"{g.user['name']} viewed", "emergency")
    return jsonify(owner=dict(owner), **emergency_payload(db, owner_id))


@bp.get("/shared/people/<int:owner_id>/medicines")
@login_required
def shared_medicines(owner_id):
    db = get_db()
    owner = _member_view(owner_id)
    if not owner or owner_id == g.user["id"]:
        return _gone()
    rows = db.execute("SELECT id, name, dosage, frequency, instructions, purpose FROM medicines WHERE owner_id = ? AND active = 1 AND verified = 1 ORDER BY name", (owner_id,)).fetchall()
    items = [dict(r) for r in rows if access.has_grant(db, g.user["id"], owner_id, "medicine", r["id"])]
    if not items:
        return _gone()
    access.log_activity(db, g.user["id"], owner_id, f"{g.user['name']} viewed", "medicine")
    return jsonify(owner=dict(owner), items=items)
