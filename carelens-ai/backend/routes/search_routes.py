from flask import Blueprint, g, jsonify, request

import access
from auth import login_required
from db import get_db

bp = Blueprint("search", __name__, url_prefix="/api")


def _like(q):
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _snippet(text, q, width=90):
    i = text.lower().find(q.lower())
    if i < 0:
        return None
    s = max(0, i - width // 2)
    return ("…" if s else "") + " ".join(text[s:s + width + len(q)].split()) + "…"


@bp.get("/search")
@login_required
def search():
    """Own records plus records explicitly shared with this user. Nothing else is queried."""
    q = (request.args.get("q") or "").strip()
    kind = request.args.get("type")
    if len(q) < 2:
        return jsonify(items=[], query=q)
    db, uid, like = get_db(), g.user["id"], _like(q)
    items = []
    want = lambda t: kind in (None, "", t)

    if want("document"):
        rows = db.execute("""SELECT d.id, d.filename, d.uploaded_at, d.owner_id, e.text FROM documents d
                             LEFT JOIN document_extractions e ON e.document_id = d.id
                             WHERE d.owner_id = ? AND (d.filename LIKE ? ESCAPE '\\' OR e.text LIKE ? ESCAPE '\\')
                             ORDER BY d.uploaded_at DESC LIMIT 20""", (uid, like, like)).fetchall()
        for r in rows:
            items.append({"type": "document", "id": r["id"], "title": r["filename"], "date": r["uploaded_at"],
                          "snippet": _snippet(r["text"] or "", q), "member": "You", "link": f"/documents/{r['id']}"})
        for gr in access.received_grants(db, uid):
            if gr["resource_type"] != "document":
                continue
            r = db.execute("""SELECT d.id, d.filename, d.uploaded_at, e.text FROM documents d LEFT JOIN document_extractions e ON e.document_id = d.id
                              WHERE d.id = ? AND (d.filename LIKE ? ESCAPE '\\' OR e.text LIKE ? ESCAPE '\\')""", (gr["resource_id"], like, like)).fetchone()
            if r:
                items.append({"type": "document", "id": r["id"], "title": r["filename"], "date": r["uploaded_at"],
                              "snippet": _snippet(r["text"] or "", q), "member": gr["owner_name"], "link": f"/shared/documents/{r['id']}"})
    if want("medicine"):
        for r in db.execute("SELECT id, name, dosage, instructions FROM medicines WHERE owner_id = ? AND (name LIKE ? ESCAPE '\\' OR instructions LIKE ? ESCAPE '\\') LIMIT 20", (uid, like, like)):
            items.append({"type": "medicine", "id": r["id"], "title": r["name"], "date": None, "snippet": r["dosage"], "member": "You", "link": f"/medicines?open={r['id']}"})
    if want("timeline"):
        for r in db.execute("SELECT id, title, detail, event_date FROM timeline_events WHERE owner_id = ? AND (title LIKE ? ESCAPE '\\' OR detail LIKE ? ESCAPE '\\') LIMIT 20", (uid, like, like)):
            items.append({"type": "timeline", "id": r["id"], "title": r["title"], "date": r["event_date"], "snippet": r["detail"], "member": "You", "link": "/timeline"})
        for r in db.execute("SELECT id, title, due_at FROM reminders WHERE owner_id = ? AND title LIKE ? ESCAPE '\\' LIMIT 20", (uid, like)):
            items.append({"type": "timeline", "id": r["id"], "title": r["title"], "date": r["due_at"], "snippet": "Reminder", "member": "You", "link": "/reminders"})
    if want("health"):
        for r in db.execute("SELECT id, kind, title, detail, created_at FROM health_records WHERE owner_id = ? AND (title LIKE ? ESCAPE '\\' OR detail LIKE ? ESCAPE '\\') LIMIT 20", (uid, like, like)):
            items.append({"type": "health", "id": r["id"], "title": r["title"], "date": r["created_at"], "snippet": r["kind"].title(), "member": "You", "link": "/health"})
    items.sort(key=lambda i: i["date"] or "", reverse=True)
    return jsonify(items=items[:50], query=q)
