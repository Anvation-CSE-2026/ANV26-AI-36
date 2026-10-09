"""Document access, details and the background processing pipeline."""
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flask import current_app

import access
import crypto
from services import ai, extraction, structured
from utils import now_iso

log = logging.getLogger("carelens.documents")


def get_document_for(db, user, doc_id):
    """Return (row, 'owner'|'shared'), or (None, None). The single gate for reading a document."""
    row = db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if row is None:
        return None, None
    if row["owner_id"] == user["id"]:
        return row, "owner"
    if access.has_grant(db, user["id"], row["owner_id"], "document", row["id"]):
        return row, "shared"
    return None, None


def document_json(r):
    return {"id": r["id"], "filename": r["filename"], "file_type": r["file_type"], "file_size": r["file_size"],
            "uploaded_at": r["uploaded_at"], "processing_status": r["processing_status"],
            "processing_note": r["processing_note"]}


def document_detail(db, row, language, include_medicines=True):
    ex = db.execute("SELECT method, char_count, extracted_at FROM document_extractions WHERE document_id = ?", (row["id"],)).fetchone()
    findings = db.execute("SELECT label, value, unit, reference_range, flag FROM document_findings WHERE document_id = ? ORDER BY id", (row["id"],)).fetchall()
    an = db.execute("SELECT language, content, created_at FROM document_analyses WHERE document_id = ? AND language = ?", (row["id"], language)).fetchone()
    if an is None and not include_medicines:  # shared view: show an existing explanation in any language
        an = db.execute("SELECT language, content, created_at FROM document_analyses WHERE document_id = ? ORDER BY id DESC LIMIT 1", (row["id"],)).fetchone()
    out = {
        "document": document_json(row),
        "extraction": dict(ex) if ex else None,
        "findings": [dict(f) for f in findings],
        "analysis": {"language": an["language"], "created_at": an["created_at"], **json.loads(an["content"])} if an else None,
    }
    if include_medicines:
        meds = db.execute("SELECT id, name, dosage, frequency, verified FROM medicines WHERE document_id = ? AND owner_id = ?", (row["id"], row["owner_id"])).fetchall()
        out["medicines"] = [dict(m) for m in meds]
    return out


# At most two documents are read at a time, however many are uploaded, so a burst of uploads can't exhaust the machine.
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="carelens-doc")


def start_processing(app, doc_id):
    if app.config.get("PROCESS_SYNC"):
        process_document(app, doc_id)
    else:
        _pool.submit(process_document, app, doc_id)


def read_document_bytes(row):
    """The stored file as plain bytes (decrypting if needed), or None if it is missing or outside the upload folder."""
    root = Path(current_app.config["UPLOAD_DIR"]).resolve()
    full = (root / row["storage_path"]).resolve()
    if root not in full.parents or not full.is_file():
        return None
    return crypto.read_file(full)


def _set_status(db, doc_id, status, note=None):
    with db:
        db.execute("UPDATE documents SET processing_status = ?, processing_note = ? WHERE id = ?", (status, note, doc_id))


def process_document(app, doc_id):
    """UPLOAD -> extract text -> structured info -> medicines -> (AI analysis)."""
    import sqlite3
    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE"], timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            doc = db.execute("SELECT d.*, u.preferred_language AS lang FROM documents d JOIN users u ON u.id = d.owner_id WHERE d.id = ?", (doc_id,)).fetchone()
            if doc is None:
                return
            _set_status(db, doc_id, "processing")
            path = Path(app.config["UPLOAD_DIR"]).resolve() / doc["storage_path"]
            try:
                with crypto.plain_path(path) as readable:  # decrypted copy lives only for this block
                    text, method = extraction.extract_text(readable, doc["file_type"])
            except extraction.ExtractionUnavailable as exc:
                return _set_status(db, doc_id, "failed", str(exc))
            except extraction.ExtractionFailed as exc:
                return _set_status(db, doc_id, "failed", str(exc))
            except (OSError, crypto.DecryptionError):
                return _set_status(db, doc_id, "failed", "This document's file couldn't be opened.")

            findings = structured.find_lab_values(text)
            meds = structured.find_medicines(text)
            with db:
                db.execute("DELETE FROM document_extractions WHERE document_id = ?", (doc_id,))
                db.execute("DELETE FROM document_findings WHERE document_id = ?", (doc_id,))
                db.execute("INSERT INTO document_extractions (document_id, text, method, char_count, extracted_at) VALUES (?,?,?,?,?)",
                           (doc_id, text, method, len(text), now_iso()))
                for f in findings:
                    db.execute("""INSERT INTO document_findings (document_id, label, value, unit, reference_range, flag, source_line)
                                  VALUES (?,?,?,?,?,?,?)""", (doc_id, f["label"], f["value"], f["unit"], f["reference_range"], f["flag"], f["source_line"]))
                existing = {r["name"].lower() for r in db.execute("SELECT name FROM medicines WHERE owner_id = ? AND active = 1", (doc["owner_id"],))}
                db.execute("DELETE FROM medicines WHERE document_id = ? AND source = 'document' AND verified = 0", (doc_id,))
                for m in meds:
                    if m["name"].lower() in existing:
                        continue
                    db.execute("""INSERT INTO medicines (owner_id, name, dosage, frequency, instructions, purpose, source, verified, document_id, created_at)
                                  VALUES (?,?,?,?,?,?, 'document', 0, ?, ?)""",
                               (doc["owner_id"], m["name"], m["dosage"], m["frequency"], m["instructions"], m["purpose"], doc_id, now_iso()))

            note = None
            if ai.is_configured():
                try:
                    ai.analyze_document(db, doc, doc["lang"])
                except Exception:  # AI trouble never fails the document
                    log.exception("analysis failed for document %s", doc_id)
                    note = "Your document was read, but the explanation couldn't be prepared. You can retry it."
            _set_status(db, doc_id, "processed", note)
        except Exception:
            log.exception("processing failed for document %s", doc_id)
            _set_status(db, doc_id, "failed", "We couldn't process this document right now. Please try again.")
        finally:
            db.close()
