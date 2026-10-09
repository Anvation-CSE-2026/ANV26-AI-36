"""Medicines, reminders, timeline and dashboard. Everything is filtered by g.user."""
from flask import Blueprint, g, jsonify, request

from auth import login_required
from db import get_db
from utils import api_error, json_body, now_iso, parse_when, text_field, validation_error

bp = Blueprint("care", __name__, url_prefix="/api/me")

MED_COLS = "id, name, dosage, frequency, instructions, purpose, source, verified, document_id, active, started_on, created_at"


def _med(db, mid, uid):
    return db.execute(f"SELECT {MED_COLS} FROM medicines WHERE id = ? AND owner_id = ?", (mid, uid)).fetchone()


def med_json(r):
    d = dict(r)
    d["verified"], d["active"] = bool(d["verified"]), bool(d["active"])
    return d


# ---------- medicines ----------
@bp.get("/medicines")
@login_required
def list_medicines():
    rows = get_db().execute(f"SELECT {MED_COLS} FROM medicines WHERE owner_id = ? ORDER BY active DESC, verified ASC, name", (g.user["id"],)).fetchall()
    return jsonify(items=[med_json(r) for r in rows])


def _med_fields(d, partial=False):
    errors, out = {}, {}
    for key, label, mx, req in (("name", "Name", 80, True), ("dosage", "Dosage", 60, False), ("frequency", "Frequency", 80, False),
                                ("instructions", "Instructions", 300, False), ("purpose", "Purpose", 120, False)):
        if partial and key not in d:
            continue
        v, e = text_field(d, key, label, mx, req)
        if e:
            errors[key] = e
        out[key] = v
    if d.get("started_on"):
        v, e = parse_when(d["started_on"], "Start date")
        if e:
            errors["started_on"] = e
        out["started_on"] = v[:10] if v else None
    elif "started_on" in d:
        out["started_on"] = None
    return out, errors


@bp.post("/medicines")
@login_required
def add_medicine():
    out, errors = _med_fields(json_body())
    if errors:
        return validation_error(errors)
    db = get_db()
    with db:
        cur = db.execute("""INSERT INTO medicines (owner_id, name, dosage, frequency, instructions, purpose, started_on, source, verified, created_at)
                            VALUES (?,?,?,?,?,?,?, 'user', 1, ?)""",
                         (g.user["id"], out["name"], out.get("dosage"), out.get("frequency"), out.get("instructions"),
                          out.get("purpose"), out.get("started_on"), now_iso()))
    return jsonify(medicine=med_json(_med(db, cur.lastrowid, g.user["id"]))), 201


@bp.get("/medicines/<int:mid>")
@login_required
def get_medicine(mid):
    db = get_db()
    m = _med(db, mid, g.user["id"])
    if not m:
        return api_error(404, "not_found", "We couldn't find that medicine.")
    doc = db.execute("SELECT id, filename FROM documents WHERE id = ? AND owner_id = ?", (m["document_id"], g.user["id"])).fetchone() if m["document_id"] else None
    rem = db.execute("SELECT id, title, due_at, status FROM reminders WHERE medicine_id = ? AND owner_id = ? ORDER BY due_at DESC LIMIT 20", (mid, g.user["id"])).fetchall()
    return jsonify(medicine=med_json(m), document=dict(doc) if doc else None, reminders=[dict(r) for r in rem])


@bp.patch("/medicines/<int:mid>")
@login_required
def update_medicine(mid):
    db = get_db()
    if not _med(db, mid, g.user["id"]):
        return api_error(404, "not_found", "We couldn't find that medicine.")
    d = json_body()
    out, errors = _med_fields(d, partial=True)
    for flag in ("verified", "active"):
        if flag in d:
            if not isinstance(d[flag], bool):
                errors[flag] = "Invalid value."
            else:
                out[flag] = 1 if d[flag] else 0
    if errors:
        return validation_error(errors)
    if out:
        sets = ", ".join(f"{k} = ?" for k in out)
        with db:
            db.execute(f"UPDATE medicines SET {sets} WHERE id = ? AND owner_id = ?", (*out.values(), mid, g.user["id"]))
    return jsonify(medicine=med_json(_med(db, mid, g.user["id"])))


@bp.delete("/medicines/<int:mid>")
@login_required
def delete_medicine(mid):
    db = get_db()
    with db:
        n = db.execute("DELETE FROM medicines WHERE id = ? AND owner_id = ?", (mid, g.user["id"])).rowcount
    return jsonify(ok=True) if n else api_error(404, "not_found", "We couldn't find that medicine.")


# ---------- reminders ----------
KINDS = {"medicine", "appointment", "test", "custom"}


def rem_json(r):
    return dict(r)


@bp.get("/reminders")
@login_required
def list_reminders():
    status = request.args.get("status")
    sql = "SELECT * FROM reminders WHERE owner_id = ?"
    args = [g.user["id"]]
    if status in ("pending", "done"):
        sql += " AND status = ?"
        args.append(status)
    sql += " ORDER BY status ASC, due_at ASC LIMIT 200"
    return jsonify(items=[rem_json(r) for r in get_db().execute(sql, args).fetchall()])


def _rem_fields(d, db, partial=False):
    errors, out = {}, {}
    if not partial or "title" in d:
        v, e = text_field(d, "title", "Title", 120, True)
        errors.update({"title": e} if e else {})
        out["title"] = v
    if not partial or "kind" in d:
        if d.get("kind") not in KINDS:
            errors["kind"] = "Choose a type."
        out["kind"] = d.get("kind")
    if not partial or "due_at" in d:
        v, e = parse_when(d.get("due_at"), "Date and time")
        errors.update({"due_at": e} if e else {})
        out["due_at"] = v
    if "description" in d or not partial:
        v, e = text_field(d, "description", "Description", 500)
        errors.update({"description": e} if e else {})
        out["description"] = v
    if d.get("medicine_id") not in (None, ""):
        if not isinstance(d["medicine_id"], int) or not _med(db, d["medicine_id"], g.user["id"]):
            errors["medicine_id"] = "Choose one of your medicines."
        out["medicine_id"] = d["medicine_id"]
    return out, errors


@bp.post("/reminders")
@login_required
def add_reminder():
    db = get_db()
    out, errors = _rem_fields(json_body(), db)
    if errors:
        return validation_error(errors)
    with db:
        cur = db.execute("""INSERT INTO reminders (owner_id, title, kind, description, due_at, medicine_id, created_at)
                            VALUES (?,?,?,?,?,?,?)""",
                         (g.user["id"], out["title"], out["kind"], out["description"], out["due_at"], out.get("medicine_id"), now_iso()))
    row = db.execute("SELECT * FROM reminders WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(reminder=rem_json(row)), 201


@bp.patch("/reminders/<int:rid>")
@login_required
def update_reminder(rid):
    db = get_db()
    if not db.execute("SELECT 1 FROM reminders WHERE id = ? AND owner_id = ?", (rid, g.user["id"])).fetchone():
        return api_error(404, "not_found", "We couldn't find that reminder.")
    d = json_body()
    out, errors = _rem_fields(d, db, partial=True)
    if "status" in d:
        if d["status"] not in ("pending", "done"):
            errors["status"] = "Invalid status."
        else:
            out["status"] = d["status"]
            out["completed_at"] = now_iso() if d["status"] == "done" else None
    if errors:
        return validation_error(errors)
    if out:
        with db:
            db.execute(f"UPDATE reminders SET {', '.join(f'{k} = ?' for k in out)} WHERE id = ? AND owner_id = ?", (*out.values(), rid, g.user["id"]))
    return jsonify(reminder=rem_json(db.execute("SELECT * FROM reminders WHERE id = ?", (rid,)).fetchone()))


@bp.delete("/reminders/<int:rid>")
@login_required
def delete_reminder(rid):
    db = get_db()
    with db:
        n = db.execute("DELETE FROM reminders WHERE id = ? AND owner_id = ?", (rid, g.user["id"])).rowcount
    return jsonify(ok=True) if n else api_error(404, "not_found", "We couldn't find that reminder.")


# ---------- timeline ----------
@bp.get("/timeline")
@login_required
def timeline():
    db, uid = get_db(), g.user["id"]
    ev = []
    for r in db.execute("SELECT id, filename, uploaded_at FROM documents WHERE owner_id = ?", (uid,)):
        ev.append({"key": f"doc-{r['id']}", "type": "document", "title": f"Document added: {r['filename']}", "detail": None,
                   "date": r["uploaded_at"], "ref": {"type": "document", "id": r["id"]}})
    for r in db.execute("SELECT id, name, dosage, created_at, started_on, verified FROM medicines WHERE owner_id = ? AND verified = 1", (uid,)):
        ev.append({"key": f"med-{r['id']}", "type": "medicine", "title": f"Medicine added: {r['name']}", "detail": r["dosage"],
                   "date": (r["started_on"] + "T00:00:00.000Z") if r["started_on"] else r["created_at"], "ref": {"type": "medicine", "id": r["id"]}})
    for r in db.execute("SELECT id, title, kind, due_at, status FROM reminders WHERE owner_id = ?", (uid,)):
        ev.append({"key": f"rem-{r['id']}", "type": "reminder", "title": r["title"], "detail": f"{r['kind'].title()} reminder · {r['status']}",
                   "date": r["due_at"], "ref": {"type": "reminder", "id": r["id"]}})
    for r in db.execute("SELECT id, kind, title, detail, event_date FROM timeline_events WHERE owner_id = ?", (uid,)):
        ev.append({"key": f"evt-{r['id']}", "type": r["kind"], "title": r["title"], "detail": r["detail"], "date": r["event_date"],
                   "ref": {"type": "event", "id": r["id"]}, "deletable": True})
    ev.sort(key=lambda e: e["date"], reverse=True)
    before = request.args.get("before")
    if before:
        ev = [e for e in ev if e["date"] < before]
    return jsonify(items=ev[:40], more=len(ev) > 40)


@bp.post("/timeline/events")
@login_required
def add_event():
    d, errors = json_body(), {}
    if d.get("kind") not in ("appointment", "test", "event"):
        errors["kind"] = "Choose a type."
    title, e = text_field(d, "title", "Title", 120, True)
    errors.update({"title": e} if e else {})
    detail, e = text_field(d, "detail", "Details", 500)
    errors.update({"detail": e} if e else {})
    when, e = parse_when(d.get("event_date"), "Date")
    errors.update({"event_date": e} if e else {})
    if errors:
        return validation_error(errors)
    db = get_db()
    with db:
        db.execute("INSERT INTO timeline_events (owner_id, kind, title, detail, event_date, created_at) VALUES (?,?,?,?,?,?)",
                   (g.user["id"], d["kind"], title, detail, when, now_iso()))
    return jsonify(ok=True), 201


@bp.delete("/timeline/events/<int:eid>")
@login_required
def delete_event(eid):
    db = get_db()
    with db:
        n = db.execute("DELETE FROM timeline_events WHERE id = ? AND owner_id = ?", (eid, g.user["id"])).rowcount
    return jsonify(ok=True) if n else api_error(404, "not_found", "We couldn't find that event.")


# ---------- dashboard (one call for the home screen) ----------
@bp.get("/dashboard")
@login_required
def dashboard():
    db, uid = get_db(), g.user["id"]
    one = lambda sql, *a: db.execute(sql, a).fetchone()[0]
    docs = db.execute("SELECT id, filename, uploaded_at, processing_status FROM documents WHERE owner_id = ? ORDER BY uploaded_at DESC LIMIT 3", (uid,)).fetchall()
    meds = db.execute("SELECT id, name, dosage, frequency, verified FROM medicines WHERE owner_id = ? AND active = 1 ORDER BY verified DESC, name LIMIT 3", (uid,)).fetchall()
    rems = db.execute("SELECT id, title, kind, due_at FROM reminders WHERE owner_id = ? AND status = 'pending' ORDER BY due_at LIMIT 3", (uid,)).fetchall()
    return jsonify(
        documents={"total": one("SELECT COUNT(*) FROM documents WHERE owner_id = ?", uid), "recent": [dict(r) for r in docs]},
        medicines={"total": one("SELECT COUNT(*) FROM medicines WHERE owner_id = ? AND active = 1", uid),
                   "unverified": one("SELECT COUNT(*) FROM medicines WHERE owner_id = ? AND active = 1 AND verified = 0", uid),
                   "recent": [{**dict(r), "verified": bool(r["verified"])} for r in meds]},
        reminders={"pending": one("SELECT COUNT(*) FROM reminders WHERE owner_id = ? AND status = 'pending'", uid), "upcoming": [dict(r) for r in rems]},
        health={"allergies": one("SELECT COUNT(*) FROM health_records WHERE owner_id = ? AND kind = 'allergy'", uid),
                "conditions": one("SELECT COUNT(*) FROM health_records WHERE owner_id = ? AND kind = 'condition'", uid)},
        sharing={"granted": one("SELECT COUNT(*) FROM sharing_permissions WHERE owner_id = ? AND revoked_at IS NULL", uid),
                 "received": len(__import__("access").received_grants(db, uid))},
        emergency={"contacts": one("SELECT COUNT(*) FROM emergency_contacts WHERE owner_id = ?", uid)},
        family={"members": one("SELECT COUNT(*) FROM users WHERE family_id = ?", g.user["family_id"])},
    )
