import json

from flask import Blueprint, g, jsonify, request

import access
import safety
from auth import login_required, primary_required
from db import get_db
from security import record_event, throttle
from services import ai, extraction
from utils import api_error, json_body, now_iso, validation_error

bp = Blueprint("ai", __name__, url_prefix="/api")


@bp.get("/ai/status")
@login_required
def status():
    return jsonify(configured=ai.is_configured(), languages=ai.LANGUAGES, capabilities=extraction.capabilities())


def _mask(k):
    """Only the last four characters, and only ever shown to the primary member."""
    return ("…" + k[-4:]) if k and len(k) > 12 else ("set" if k else "")


def _settings_json():
    cfg = ai.load_config()
    show = bool(g.user["is_primary"])
    return {"configured": ai.is_configured(), "provider": ai.provider_name(),
            "saved_provider": cfg.get("provider"), "saved_model": cfg.get("model", ""),
            "key_hint": _mask(cfg.get("key", "")) if show else "", "providers": list(ai.ENV_KEYS)}


@bp.get("/ai/settings")
@login_required
def get_settings():
    return jsonify(**_settings_json(), can_edit=bool(g.user["is_primary"]))


@bp.put("/ai/settings")
@primary_required
def put_settings():
    d = json_body()
    prov, key, model = d.get("provider"), (d.get("key") or "").strip(), (d.get("model") or "").strip()
    errors = {}
    if prov not in ai.ENV_KEYS:
        errors["provider"] = "Choose a provider."
    if not key:
        existing = ai.load_config()
        if existing.get("provider") == prov and existing.get("key"):
            key = existing["key"]
        else:
            errors["key"] = "Paste your API key."
    if len(key) > 300 or len(model) > 80:
        errors["key"] = "That value is too long."
    if errors:
        return validation_error(errors)
    ai.save_config(prov, key, model)
    return jsonify(**_settings_json())


@bp.delete("/ai/settings")
@primary_required
def delete_settings():
    ai.clear_config()
    return jsonify(**_settings_json())


@bp.post("/ai/test")
@primary_required
@throttle("ai_test", 10, 600)
def test_connection():
    if not ai.is_configured():
        return api_error(503, "ai_not_configured", "Save an API key first.")
    try:
        reply = ai.complete("Reply with the single word OK.", [{"role": "user", "content": "Say OK"}], 20)
    except ai.AIError as exc:
        return api_error(502, "ai_unavailable", exc.user_message or "The AI service didn't accept the request. Check the key and try again.")
    return jsonify(ok=True, reply=reply[:40], provider=ai.provider_name())


def _msg(r):
    return {"id": r["id"], "role": r["role"], "content": r["content"], "sources": json.loads(r["sources"] or "[]"), "created_at": r["created_at"]}


@bp.get("/ai/conversations")
@login_required
def conversations():
    rows = get_db().execute("SELECT id, title, created_at FROM ai_conversations WHERE owner_id = ? ORDER BY id DESC LIMIT 50", (g.user["id"],)).fetchall()
    return jsonify(items=[dict(r) for r in rows])


def _own_conv(db, cid):
    return db.execute("SELECT * FROM ai_conversations WHERE id = ? AND owner_id = ?", (cid, g.user["id"])).fetchone()


@bp.get("/ai/conversations/<int:cid>")
@login_required
def conversation(cid):
    db = get_db()
    c = _own_conv(db, cid)
    if not c:
        return api_error(404, "not_found", "We couldn't find that conversation.")
    msgs = db.execute("SELECT * FROM ai_messages WHERE conversation_id = ? ORDER BY id", (cid,)).fetchall()
    return jsonify(conversation=dict(c), messages=[_msg(m) for m in msgs])


@bp.delete("/ai/conversations/<int:cid>")
@login_required
def delete_conversation(cid):
    db = get_db()
    with db:
        n = db.execute("DELETE FROM ai_conversations WHERE id = ? AND owner_id = ?", (cid, g.user["id"])).rowcount
    return jsonify(ok=True) if n else api_error(404, "not_found", "We couldn't find that conversation.")


def _declined_exchange(db, cid, verdict, category):
    """Answer a request the safety guard stopped. The AI provider is never contacted, and the blocked text is not
    stored (so it can never be fed back into a later prompt)."""
    with db:
        if not cid:
            cid = db.execute("INSERT INTO ai_conversations (owner_id, title, created_at) VALUES (?,?,?)",
                             (g.user["id"], "Request declined", now_iso())).lastrowid
        db.execute("INSERT INTO ai_messages (conversation_id, role, content, created_at) VALUES (?, 'user', ?, ?)",
                   (cid, "[Message not kept: this request was declined for safety.]", now_iso()))
        mid = db.execute("INSERT INTO ai_messages (conversation_id, role, content, sources, created_at) VALUES (?, 'assistant', ?, ?, ?)",
                         (cid, verdict.reply, "[]", now_iso())).lastrowid
    record_event(db, g.user["id"], "assistant_declined", category)
    m = db.execute("SELECT * FROM ai_messages WHERE id = ?", (mid,)).fetchone()
    return jsonify(conversation_id=cid, message=_msg(m), declined=True), 201


@bp.post("/ai/chat")
@login_required
@throttle("ai_chat", 40, 600)
def chat():
    d, db = json_body(), get_db()
    q = d.get("message")
    if not isinstance(q, str) or not q.strip():
        return validation_error({"message": "Type a question first."})
    q = q.strip()
    if len(q) > 1500:
        return validation_error({"message": "Please keep questions under 1,500 characters."})
    doc_id = d.get("document_id")
    if doc_id is not None and (not isinstance(doc_id, int) or isinstance(doc_id, bool)):
        return validation_error({"document_id": "Invalid document."})
    lang = d.get("language")
    if lang is not None and lang not in ai.LANGUAGES:
        return validation_error({"language": "That language isn't available."})

    cid = d.get("conversation_id")
    conv = None
    if cid is not None:
        conv = _own_conv(db, cid) if isinstance(cid, int) and not isinstance(cid, bool) else None
        if not conv:
            return api_error(404, "not_found", "We couldn't find that conversation.")

    # Safety guard first: anything that could harm the user or a patient, or attack privacy/security, stops here.
    verdict = safety.screen_input(q, lang or g.user["preferred_language"])
    if verdict.blocked:
        return _declined_exchange(db, conv["id"] if conv else None, verdict, verdict.category)

    history = db.execute("SELECT role, content FROM ai_messages WHERE conversation_id = ? ORDER BY id", (conv["id"],)).fetchall() if conv else []

    try:
        text, sources = ai.answer(db, g.user, q, history, doc_id, lang)
    except PermissionError:
        return api_error(404, "not_found", "That document isn't available.")
    except ai.AINotConfigured:
        return api_error(503, "ai_not_configured", "The AI assistant isn't set up on this device yet.")
    except ai.AIError as exc:
        return api_error(502, "ai_unavailable", exc.user_message or "We couldn't get an answer right now. Please try again.")

    out = safety.screen_output(text, lang or g.user["preferred_language"])
    if out.blocked:  # the AI's own answer was unsafe: show the safe message instead
        text, sources = out.reply, []
        record_event(db, g.user["id"], "assistant_declined", out.category)

    with db:
        if not conv:
            cur = db.execute("INSERT INTO ai_conversations (owner_id, title, created_at) VALUES (?,?,?)", (g.user["id"], q[:60], now_iso()))
            cid = cur.lastrowid
        db.execute("INSERT INTO ai_messages (conversation_id, role, content, created_at) VALUES (?, 'user', ?, ?)", (cid, q, now_iso()))
        mcur = db.execute("INSERT INTO ai_messages (conversation_id, role, content, sources, created_at) VALUES (?, 'assistant', ?, ?, ?)",
                          (cid, text, json.dumps(sources), now_iso()))
    for s in sources:
        if s["type"] == "document":
            row = db.execute("SELECT owner_id FROM documents WHERE id = ?", (s["id"],)).fetchone()
            if row and row["owner_id"] != g.user["id"]:
                access.log_activity(db, g.user["id"], row["owner_id"], f"{g.user['name']} asked the assistant about", "document", s["id"])
    m = db.execute("SELECT * FROM ai_messages WHERE id = ?", (mcur.lastrowid,)).fetchone()
    return jsonify(conversation_id=cid, message=_msg(m)), 201


@bp.post("/ai/voice/report")
@login_required
@throttle("ai_voice", 30, 600)
def voice_report():
    """Text for the voice assistant to speak: a summary, or the full explanation, of a report."""
    d, db = json_body(), get_db()
    mode = d.get("mode", "summary")
    if mode not in ("summary", "read"):
        return validation_error({"mode": "Choose summary or read."})
    doc_id = d.get("document_id")
    if doc_id is not None and (not isinstance(doc_id, int) or isinstance(doc_id, bool)):
        return validation_error({"document_id": "Invalid document."})
    lang = d.get("language") or g.user["preferred_language"]
    if lang not in ai.LANGUAGES:
        return validation_error({"language": "That language isn't available."})
    try:
        text, doc = ai.voice_report(db, g.user, doc_id, lang, mode)
    except PermissionError:
        return api_error(404, "not_found", "That document isn't available.")
    except LookupError:
        return api_error(404, "no_documents", "You haven't added a report yet. Upload one in Documents first.")
    except ValueError:
        return api_error(422, "not_processed", "This report hasn't been read yet. Please wait a moment and try again.")
    except ai.AINotConfigured:
        return api_error(503, "ai_not_configured", "Summaries need the AI assistant. Connect it in Settings, or ask me to read the report as written.")
    except ai.AIError as exc:
        return api_error(502, "ai_unavailable", exc.user_message or "We couldn't prepare that right now. Please try again.")
    return jsonify(text=text, language=lang, mode=mode, ai=ai.is_configured(), document={"id": doc["id"], "filename": doc["filename"]})
