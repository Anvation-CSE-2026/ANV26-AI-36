"""Health profile, emergency information and diet. All data belongs to g.user."""
import json

from flask import Blueprint, g, jsonify

from auth import login_required
from db import get_db
from security import throttle
from services import ai
from utils import api_error, json_body, now_iso, text_field, validation_error

bp = Blueprint("health", __name__, url_prefix="/api/me")

KINDS = {"allergy", "condition", "history", "other"}
BLOOD = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}
SEX = {"female", "male", "other"}


def health_payload(db, uid):
    hp = db.execute("SELECT * FROM health_profiles WHERE user_id = ?", (uid,)).fetchone()
    recs = db.execute("SELECT id, kind, title, detail, source, created_at FROM health_records WHERE owner_id = ? ORDER BY kind, id", (uid,)).fetchall()
    profile = {k: hp[k] for k in ("date_of_birth", "sex", "blood_group", "height_cm", "weight_kg", "notes")} if hp else \
        {k: None for k in ("date_of_birth", "sex", "blood_group", "height_cm", "weight_kg", "notes")}
    return {"profile": profile, "records": [dict(r) for r in recs]}


@bp.get("/health")
@login_required
def get_health():
    return jsonify(health_payload(get_db(), g.user["id"]))


@bp.put("/health")
@login_required
def put_health():
    d, errors = json_body(), {}
    blood = (d.get("blood_group") or None)
    if blood and blood not in BLOOD:
        errors["blood_group"] = "Choose a valid blood group."
    sex = d.get("sex") or None
    if sex and sex not in SEX:
        errors["sex"] = "Choose a valid option."
    dob = d.get("date_of_birth") or None
    if dob:
        from datetime import date
        try:
            if date.fromisoformat(dob) > date.today():
                errors["date_of_birth"] = "Date of birth can't be in the future."
        except ValueError:
            errors["date_of_birth"] = "Enter a valid date."
    nums = {}
    for k, lo, hi in (("height_cm", 30, 260), ("weight_kg", 1, 400)):
        v = d.get(k)
        if v in (None, ""):
            nums[k] = None
            continue
        try:
            f = float(v)
            if not lo <= f <= hi:
                raise ValueError
            nums[k] = f
        except (TypeError, ValueError):
            errors[k] = "Enter a valid number."
    notes, e = text_field(d, "notes", "Notes", 1000)
    if e:
        errors["notes"] = e
    if errors:
        return validation_error(errors)
    db = get_db()
    with db:
        db.execute("""INSERT INTO health_profiles (user_id, date_of_birth, sex, blood_group, height_cm, weight_kg, notes, updated_at)
                      VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET date_of_birth=excluded.date_of_birth,
                      sex=excluded.sex, blood_group=excluded.blood_group, height_cm=excluded.height_cm,
                      weight_kg=excluded.weight_kg, notes=excluded.notes, updated_at=excluded.updated_at""",
                   (g.user["id"], dob, sex, blood, nums["height_cm"], nums["weight_kg"], notes, now_iso()))
    return jsonify(health_payload(db, g.user["id"]))


@bp.post("/health/records")
@login_required
def add_record():
    d = json_body()
    errors = {}
    if d.get("kind") not in KINDS:
        errors["kind"] = "Choose a type."
    title, e = text_field(d, "title", "Title", 120, True)
    if e:
        errors["title"] = e
    detail, e = text_field(d, "detail", "Details", 500)
    if e:
        errors["detail"] = e
    if errors:
        return validation_error(errors)
    db = get_db()
    with db:
        cur = db.execute("INSERT INTO health_records (owner_id, kind, title, detail, created_at) VALUES (?,?,?,?,?)",
                         (g.user["id"], d["kind"], title, detail, now_iso()))
    row = db.execute("SELECT id, kind, title, detail, source, created_at FROM health_records WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(record=dict(row)), 201


@bp.delete("/health/records/<int:rid>")
@login_required
def delete_record(rid):
    db = get_db()
    with db:
        n = db.execute("DELETE FROM health_records WHERE id = ? AND owner_id = ?", (rid, g.user["id"])).rowcount
    return jsonify(ok=True) if n else api_error(404, "not_found", "We couldn't find that entry.")


# ---------- emergency ----------
def emergency_payload(db, uid):
    hp = db.execute("SELECT blood_group FROM health_profiles WHERE user_id = ?", (uid,)).fetchone()
    info = db.execute("SELECT notes FROM emergency_info WHERE user_id = ?", (uid,)).fetchone()
    recs = db.execute("SELECT kind, title, detail FROM health_records WHERE owner_id = ? AND kind IN ('allergy','condition') ORDER BY kind, id", (uid,)).fetchall()
    meds = db.execute("SELECT name, dosage, frequency FROM medicines WHERE owner_id = ? AND active = 1 AND verified = 1 ORDER BY name", (uid,)).fetchall()
    contacts = db.execute("SELECT id, name, phone, relationship FROM emergency_contacts WHERE owner_id = ? ORDER BY id", (uid,)).fetchall()
    return {"blood_group": hp["blood_group"] if hp else None, "notes": info["notes"] if info else None,
            "allergies": [dict(r) for r in recs if r["kind"] == "allergy"],
            "conditions": [dict(r) for r in recs if r["kind"] == "condition"],
            "medicines": [dict(m) for m in meds], "contacts": [dict(c) for c in contacts]}


@bp.get("/emergency")
@login_required
def get_emergency():
    return jsonify(emergency_payload(get_db(), g.user["id"]))


@bp.put("/emergency")
@login_required
def put_emergency():
    notes, e = text_field(json_body(), "notes", "Notes", 1000)
    if e:
        return validation_error({"notes": e})
    db = get_db()
    with db:
        db.execute("""INSERT INTO emergency_info (user_id, notes, updated_at) VALUES (?,?,?)
                      ON CONFLICT(user_id) DO UPDATE SET notes = excluded.notes, updated_at = excluded.updated_at""",
                   (g.user["id"], notes, now_iso()))
    return jsonify(emergency_payload(db, g.user["id"]))


@bp.post("/emergency/contacts")
@login_required
def add_contact():
    d, errors = json_body(), {}
    name, e = text_field(d, "name", "Name", 80, True)
    if e:
        errors["name"] = e
    phone, e = text_field(d, "phone", "Phone number", 30, True)
    if e:
        errors["phone"] = e
    elif not __import__("re").fullmatch(r"[+\d][\d ()\-]{5,28}", phone):
        errors["phone"] = "Enter a valid phone number."
    rel, e = text_field(d, "relationship", "Relationship", 40)
    if e:
        errors["relationship"] = e
    if errors:
        return validation_error(errors)
    db = get_db()
    if db.execute("SELECT COUNT(*) AS n FROM emergency_contacts WHERE owner_id = ?", (g.user["id"],)).fetchone()["n"] >= 10:
        return api_error(422, "limit_reached", "You can save up to 10 contacts.")
    with db:
        db.execute("INSERT INTO emergency_contacts (owner_id, name, phone, relationship, created_at) VALUES (?,?,?,?,?)",
                   (g.user["id"], name, phone, rel, now_iso()))
    return jsonify(emergency_payload(db, g.user["id"])), 201


@bp.delete("/emergency/contacts/<int:cid>")
@login_required
def delete_contact(cid):
    db = get_db()
    with db:
        n = db.execute("DELETE FROM emergency_contacts WHERE id = ? AND owner_id = ?", (cid, g.user["id"])).rowcount
    return jsonify(emergency_payload(db, g.user["id"])) if n else api_error(404, "not_found", "We couldn't find that contact.")


# ---------- diet ----------
def diet_payload(db, uid):
    pref = db.execute("SELECT restrictions, preferences FROM diet_preferences WHERE user_id = ?", (uid,)).fetchone()
    recs = db.execute("SELECT kind, title FROM health_records WHERE owner_id = ? AND kind IN ('allergy','condition') ORDER BY id", (uid,)).fetchall()
    gd = db.execute("SELECT content, language, created_at FROM diet_guidance WHERE owner_id = ? ORDER BY id DESC LIMIT 1", (uid,)).fetchone()
    return {
        "preferences": {"restrictions": pref["restrictions"] if pref else None, "preferences": pref["preferences"] if pref else None},
        # Deterministic: exactly what the user told us — no AI involved.
        "allergies": [r["title"] for r in recs if r["kind"] == "allergy"],
        "conditions": [r["title"] for r in recs if r["kind"] == "condition"],
        "guidance": {**json.loads(gd["content"]), "language": gd["language"], "created_at": gd["created_at"]} if gd else None,
        "has_documents": bool(db.execute("SELECT 1 FROM documents d JOIN document_extractions e ON e.document_id = d.id WHERE d.owner_id = ? LIMIT 1", (uid,)).fetchone()),
        "ai_available": ai.is_configured(),
    }


@bp.get("/diet")
@login_required
def get_diet():
    return jsonify(diet_payload(get_db(), g.user["id"]))


@bp.put("/diet/preferences")
@login_required
def put_diet_prefs():
    d, errors = json_body(), {}
    r, e = text_field(d, "restrictions", "Restrictions", 500)
    if e:
        errors["restrictions"] = e
    p, e = text_field(d, "preferences", "Preferences", 500)
    if e:
        errors["preferences"] = e
    if errors:
        return validation_error(errors)
    db = get_db()
    with db:
        db.execute("""INSERT INTO diet_preferences (user_id, restrictions, preferences, updated_at) VALUES (?,?,?,?)
                      ON CONFLICT(user_id) DO UPDATE SET restrictions=excluded.restrictions, preferences=excluded.preferences,
                      updated_at=excluded.updated_at""", (g.user["id"], r, p, now_iso()))
    return jsonify(diet_payload(db, g.user["id"]))


@bp.post("/diet/guidance")
@login_required
@throttle("diet_gen", 10, 3600)
def make_guidance():
    db = get_db()
    try:
        ai.diet_guidance(db, g.user)
    except ValueError:
        return api_error(422, "no_information", "Add a document, an allergy, a condition or a food preference first, so guidance is based on your own information.")
    except ai.AINotConfigured:
        return api_error(503, "ai_not_configured", "Personalised guidance needs the AI assistant, which isn't set up on this device yet.")
    except ai.AIError as exc:
        return api_error(502, "ai_unavailable", exc.user_message or "We couldn't prepare guidance right now. Please try again.")
    return jsonify(diet_payload(db, g.user["id"]))
