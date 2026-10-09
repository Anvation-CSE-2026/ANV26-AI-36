"""Wellness & Therapies plan. Every query is filtered by g.user; nothing here reads another member's data."""
import json

from flask import Blueprint, g, jsonify

import safety
from auth import login_required
from db import get_db
from security import record_event, throttle
from services import ai, wellness
from utils import api_error, json_body, now_iso, text_field, validation_error

bp = Blueprint("wellness", __name__, url_prefix="/api/me")


def _payload(db, uid):
    row = db.execute("SELECT * FROM wellness_plans WHERE owner_id = ?", (uid,)).fetchone()
    _, _, _, has = wellness.gather(db, uid)
    return {
        "goals": (row["goals"] if row else None) or "",
        "plan": json.loads(row["content"]) if row and row["content"] else None,
        "meta": {"language": row["language"], "created_at": row["created_at"], "updated_at": row["updated_at"], "edited": bool(row["edited"])}
        if row and row["content"] else None,
        "pending_medicines": wellness.pending_verification(db, uid),
        "has_information": has,
        "ai_available": ai.is_configured(),
    }


@bp.get("/wellness")
@login_required
def get_wellness():
    return jsonify(_payload(get_db(), g.user["id"]))


@bp.put("/wellness/goals")
@login_required
def put_goals():
    goals, err = text_field(json_body(), "goals", "Goals", 600)
    if err:
        return validation_error({"goals": err})
    db = get_db()
    verdict = safety.screen_input(goals or "", g.user["preferred_language"])
    if verdict.blocked:  # goals are sent to the AI, so they pass the same safety guard as chat
        record_event(db, g.user["id"], "assistant_declined", verdict.category)
        return validation_error({"goals": verdict.reply})
    with db:
        db.execute("""INSERT INTO wellness_plans (owner_id, goals, updated_at) VALUES (?,?,?)
                      ON CONFLICT(owner_id) DO UPDATE SET goals = excluded.goals, updated_at = excluded.updated_at""",
                   (g.user["id"], goals, now_iso()))
    return jsonify(_payload(db, g.user["id"]))


@bp.post("/wellness/generate")
@login_required
@throttle("wellness_gen", 10, 3600)
def generate():
    db = get_db()
    if not ai.is_configured():  # never fabricate a personalised plan
        return api_error(503, "ai_not_configured", "A personalised plan needs the AI assistant, which isn't set up on this device yet.")
    try:
        wellness.generate(db, g.user)
    except ValueError:
        return api_error(422, "no_information", "Add a document, a health detail or a wellness goal first, so the plan is based on your own information.")
    except ai.AIError as exc:
        return api_error(502, "ai_unavailable", exc.user_message or "We couldn't prepare the plan right now. Please try again.")
    return jsonify(_payload(db, g.user["id"])), 201


@bp.put("/wellness/plan")
@login_required
def save_plan():
    db, uid = get_db(), g.user["id"]
    row = db.execute("SELECT content FROM wellness_plans WHERE owner_id = ? AND content IS NOT NULL", (uid,)).fetchone()
    if not row:
        return api_error(404, "not_found", "There's no plan to save yet.")
    allergies = [r["title"] for r in db.execute("SELECT title FROM health_records WHERE owner_id = ? AND kind = 'allergy'", (uid,)).fetchall()]
    try:
        plan = wellness.merge_edit(json.loads(row["content"]), (json_body() or {}).get("plan"), allergies)
    except ValueError:
        return validation_error({"plan": "That plan couldn't be saved."})
    with db:
        db.execute("UPDATE wellness_plans SET content = ?, edited = 1, updated_at = ? WHERE owner_id = ?", (json.dumps(plan), now_iso(), uid))
    return jsonify(_payload(db, uid))


@bp.delete("/wellness/plan")
@login_required
def delete_plan():
    db = get_db()
    with db:
        db.execute("UPDATE wellness_plans SET content = NULL, edited = 0, created_at = NULL, updated_at = ? WHERE owner_id = ?", (now_iso(), g.user["id"]))
    return jsonify(_payload(db, g.user["id"]))
