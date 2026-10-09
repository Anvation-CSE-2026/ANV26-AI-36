"""Per-member personal space. Everything here is scoped to the signed-in user.

Rule for every endpoint in this file: the owner is always g.user["id"], taken
from the session. No endpoint accepts an owner or user id from the client, and
every document query filters by owner_id in SQL. A document that belongs to
someone else is indistinguishable from one that doesn't exist (404).
Family membership never grants access to these records.
"""
import os
import re
import uuid
from pathlib import Path

from flask import Blueprint, current_app, g, jsonify, request

import crypto
from auth import login_required
from db import get_db
from security import send_document, throttle
from services import ai
from services.documents import document_detail, document_json, get_document_for, read_document_bytes, start_processing
from utils import api_error, json_body

bp = Blueprint("personal", __name__, url_prefix="/api/me")

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_DOCS_PER_USER = 200
# canonical extension -> (mime type, accepted filename extensions)
KINDS = {
    "pdf": ("application/pdf", {"pdf"}),
    "jpg": ("image/jpeg", {"jpg", "jpeg"}),
    "png": ("image/png", {"png"}),
}
BAD_FILE = "Please choose a PDF, JPG or PNG file."
# PDFs that can run scripts, launch programs or carry hidden attachments are refused: these files are opened in the
# browser and can be shared with family members.
_ACTIVE_PDF = re.compile(rb"/(?:JavaScript|JS|Launch|EmbeddedFiles?|RichMedia|XFA)(?![A-Za-z0-9])")
ACTIVE_PDF_MSG = "This PDF contains scripts or hidden attachments, so it can't be added. Save a plain copy (for example with “Print to PDF”) and try again."


def _sniff(head):
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    return None


def _clean_filename(name):
    name = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    return name[:120] or "document"


def _upload_root():
    root = Path(current_app.config["UPLOAD_DIR"])
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


_doc_json = document_json


def _own_document(doc_id):
    """The only way a document is ever loaded: by id AND owner."""
    return get_db().execute(
        "SELECT * FROM documents WHERE id = ? AND owner_id = ?", (doc_id, g.user["id"])
    ).fetchone()


def _not_found():
    return api_error(404, "not_found", "We couldn't find that document.")


@bp.get("/documents")
@login_required
def list_documents():
    rows = get_db().execute(
        "SELECT * FROM documents WHERE owner_id = ? ORDER BY uploaded_at DESC, id DESC",
        (g.user["id"],),
    ).fetchall()
    return jsonify(items=[_doc_json(r) for r in rows])


@bp.post("/documents")
@login_required
@throttle("upload", 40, 3600)
def upload_document():
    f = request.files.get("file")
    if f is None or not f.filename:
        return api_error(422, "validation", "Choose a file to add.", {"file": "Choose a file to add."})
    data = f.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        msg = "That file is too large. The limit is 10 MB."
        return api_error(413, "too_large", msg, {"file": msg})
    if not data:
        return api_error(422, "validation", "That file is empty.", {"file": "That file is empty."})

    filename = _clean_filename(f.filename)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    kind = _sniff(data[:16])
    # Content must match a supported type AND the extension must agree with it.
    if kind is None or ext not in KINDS[kind][1]:
        return api_error(422, "unsupported_file", BAD_FILE, {"file": BAD_FILE})

    if kind == "pdf" and _ACTIVE_PDF.search(data):
        return api_error(422, "unsupported_file", ACTIVE_PDF_MSG, {"file": ACTIVE_PDF_MSG})

    db = get_db()
    owner = g.user["id"]
    count = db.execute("SELECT COUNT(*) AS n FROM documents WHERE owner_id = ?", (owner,)).fetchone()["n"]
    if count >= MAX_DOCS_PER_USER:
        msg = "You've reached the document limit."
        return api_error(422, "limit_reached", msg, {"file": msg})

    root = _upload_root()
    rel = f"{owner}/{uuid.uuid4().hex}.{kind}"  # server-generated; client name never touches the disk
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    with open(full, "xb") as out:
        out.write(crypto.encrypt_bytes(data))  # encrypted at rest; file_size below stays the original size
    try:
        os.chmod(full, 0o600)
    except OSError:
        pass
    try:
        with db:
            cur = db.execute(
                """INSERT INTO documents (owner_id, filename, file_type, file_size, storage_path)
                   VALUES (?, ?, ?, ?, ?)""",
                (owner, filename, KINDS[kind][0], len(data), rel),
            )
    except Exception:
        full.unlink(missing_ok=True)
        raise
    row = db.execute("SELECT * FROM documents WHERE id = ?", (cur.lastrowid,)).fetchone()
    start_processing(current_app._get_current_object(), row["id"])
    return jsonify(document=_doc_json(row)), 201


@bp.get("/documents/<int:doc_id>")
@login_required
def get_document(doc_id):
    row = _own_document(doc_id)
    return jsonify(document=_doc_json(row)) if row else _not_found()


@bp.get("/documents/<int:doc_id>/details")
@login_required
def document_details(doc_id):
    row = _own_document(doc_id)
    if not row:
        return _not_found()
    lang = request.args.get("language") or g.user["preferred_language"]
    return jsonify(**document_detail(get_db(), row, lang if lang in ai.LANGUAGES else "en"))


@bp.get("/documents/<int:doc_id>/text")
@login_required
def document_text(doc_id):
    row = _own_document(doc_id)
    ex = get_db().execute("SELECT text FROM document_extractions WHERE document_id = ?", (doc_id,)).fetchone() if row else None
    return jsonify(text=ex["text"]) if ex else _not_found()


@bp.post("/documents/<int:doc_id>/process")
@login_required
@throttle("reprocess", 30, 3600)
def reprocess_document(doc_id):
    row = _own_document(doc_id)
    if not row:
        return _not_found()
    if row["processing_status"] == "processing":
        return jsonify(document=_doc_json(row))
    db = get_db()
    with db:
        db.execute("UPDATE documents SET processing_status = 'uploaded', processing_note = NULL WHERE id = ?", (doc_id,))
    start_processing(current_app._get_current_object(), doc_id)
    return jsonify(document=_doc_json(_own_document(doc_id))), 202


@bp.post("/documents/<int:doc_id>/analyze")
@login_required
@throttle("analyze", 30, 3600)
def analyze_document(doc_id):
    row = _own_document(doc_id)
    if not row:
        return _not_found()
    lang = json_body().get("language") or g.user["preferred_language"]
    if lang not in ai.LANGUAGES:
        return api_error(422, "validation", "That language isn't available.", {"language": "That language isn't available."})
    db = get_db()
    if not db.execute("SELECT 1 FROM document_extractions WHERE document_id = ?", (doc_id,)).fetchone():
        return api_error(422, "not_processed", "This document hasn't been read yet, so it can't be explained.")
    try:
        ai.analyze_document(db, row, lang)
    except ai.AINotConfigured:
        return api_error(503, "ai_not_configured", "Explanations need the AI assistant, which isn't set up on this device yet.")
    except ai.AIError as exc:
        return api_error(502, "ai_unavailable", exc.user_message or "We couldn't prepare the explanation right now. Please try again.")
    return jsonify(**document_detail(db, row, lang))


@bp.get("/documents/<int:doc_id>/file")
@login_required
def get_document_file(doc_id):
    row = _own_document(doc_id)
    if not row:
        return _not_found()
    try:
        data = read_document_bytes(row)
    except crypto.DecryptionError:
        return api_error(500, "file_unreadable", "This document can't be opened right now.")
    if data is None:
        return _not_found()
    return send_document(data, row["file_type"], row["filename"])


@bp.delete("/documents/<int:doc_id>")
@login_required
def delete_document(doc_id):
    row = _own_document(doc_id)
    if not row:
        return _not_found()
    db = get_db()
    with db:
        db.execute("DELETE FROM documents WHERE id = ? AND owner_id = ?", (doc_id, g.user["id"]))
    full = (_upload_root() / row["storage_path"]).resolve()
    try:
        if _upload_root() in full.parents:
            os.remove(full)
    except FileNotFoundError:
        pass
    return jsonify(ok=True)


@bp.get("/knowledge")
@login_required
def knowledge():
    """Verified, structured information drawn from the user's own records."""
    db, uid = get_db(), g.user["id"]
    rows = db.execute("""SELECT f.id, f.label, f.value, f.unit, f.reference_range, f.flag, d.id AS document_id, d.filename, d.uploaded_at
                         FROM document_findings f JOIN documents d ON d.id = f.document_id
                         WHERE d.owner_id = ? ORDER BY d.uploaded_at DESC, f.id LIMIT 200""", (uid,)).fetchall()
    return jsonify(items=[dict(r) for r in rows])
