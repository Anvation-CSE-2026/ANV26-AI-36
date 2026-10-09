"""SQLite access and versioned migrations.

Add a new SQL string to MIGRATIONS to evolve the schema (documents, sharing
permissions, emergency profiles, audit records, ...). Existing databases are
upgraded automatically on startup via PRAGMA user_version.
"""
import sqlite3

from flask import current_app, g

MIGRATIONS = [
    # v1 — families and individual accounts
    """
    CREATE TABLE families (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    );
    CREATE TABLE users (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        family_id         INTEGER NOT NULL REFERENCES families(id) ON DELETE CASCADE,
        name              TEXT NOT NULL,
        relationship      TEXT NOT NULL,
        login_identifier  TEXT NOT NULL UNIQUE COLLATE NOCASE,
        password_hash     TEXT NOT NULL,
        is_primary        INTEGER NOT NULL DEFAULT 0,
        created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    );
    CREATE INDEX idx_users_family ON users(family_id);
    """,
    # v2 — session invalidation counter and per-user documents
    """
    ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0;
    CREATE TABLE documents (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        filename           TEXT NOT NULL,
        file_type          TEXT NOT NULL,
        file_size          INTEGER NOT NULL,
        uploaded_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        processing_status  TEXT NOT NULL DEFAULT 'uploaded'
                           CHECK (processing_status IN ('uploaded', 'processing', 'processed', 'failed')),
        storage_path       TEXT NOT NULL UNIQUE
    );
    CREATE INDEX idx_documents_owner ON documents(owner_id, uploaded_at);
    """,
    # v3 — health, medicines, reminders, sharing, emergency, diet, AI
    """
    ALTER TABLE users ADD COLUMN preferred_language TEXT NOT NULL DEFAULT 'en';
    ALTER TABLE families ADD COLUMN is_sample INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE documents ADD COLUMN processing_note TEXT;

    CREATE TABLE health_profiles (
        user_id        INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        date_of_birth  TEXT, sex TEXT, blood_group TEXT,
        height_cm      REAL, weight_kg REAL, notes TEXT,
        updated_at     TEXT NOT NULL
    );
    CREATE TABLE health_records (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        kind         TEXT NOT NULL CHECK (kind IN ('allergy','condition','history','other')),
        title        TEXT NOT NULL, detail TEXT,
        source       TEXT NOT NULL DEFAULT 'user',
        created_at   TEXT NOT NULL
    );
    CREATE INDEX idx_health_records_owner ON health_records(owner_id, kind);

    CREATE TABLE document_extractions (
        document_id  INTEGER PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
        text         TEXT NOT NULL, method TEXT NOT NULL,
        char_count   INTEGER NOT NULL, extracted_at TEXT NOT NULL
    );
    CREATE TABLE document_findings (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        label        TEXT NOT NULL, value TEXT NOT NULL, unit TEXT,
        reference_range TEXT, flag TEXT, source_line TEXT NOT NULL
    );
    CREATE INDEX idx_findings_doc ON document_findings(document_id);
    CREATE TABLE document_analyses (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        language     TEXT NOT NULL, content TEXT NOT NULL, model TEXT,
        created_at   TEXT NOT NULL,
        UNIQUE (document_id, language)
    );

    CREATE TABLE medicines (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name         TEXT NOT NULL, dosage TEXT, frequency TEXT, instructions TEXT,
        purpose      TEXT,
        source       TEXT NOT NULL DEFAULT 'user' CHECK (source IN ('user','document')),
        verified     INTEGER NOT NULL DEFAULT 1,
        document_id  INTEGER REFERENCES documents(id) ON DELETE SET NULL,
        active       INTEGER NOT NULL DEFAULT 1,
        started_on   TEXT,
        created_at   TEXT NOT NULL
    );
    CREATE INDEX idx_medicines_owner ON medicines(owner_id, active);

    CREATE TABLE reminders (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title        TEXT NOT NULL,
        kind         TEXT NOT NULL CHECK (kind IN ('medicine','appointment','test','custom')),
        description  TEXT, due_at TEXT NOT NULL,
        status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','done')),
        completed_at TEXT,
        medicine_id  INTEGER REFERENCES medicines(id) ON DELETE SET NULL,
        created_at   TEXT NOT NULL
    );
    CREATE INDEX idx_reminders_owner ON reminders(owner_id, status, due_at);

    CREATE TABLE timeline_events (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        kind         TEXT NOT NULL CHECK (kind IN ('appointment','test','event')),
        title        TEXT NOT NULL, detail TEXT, event_date TEXT NOT NULL,
        created_at   TEXT NOT NULL
    );
    CREATE INDEX idx_timeline_owner ON timeline_events(owner_id, event_date);

    CREATE TABLE sharing_permissions (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        grantee_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        resource_type  TEXT NOT NULL CHECK (resource_type IN ('document','medicine','health_profile','emergency')),
        resource_id    INTEGER,
        created_at     TEXT NOT NULL, expires_at TEXT, revoked_at TEXT
    );
    CREATE INDEX idx_sharing_grantee ON sharing_permissions(grantee_id, revoked_at);
    CREATE INDEX idx_sharing_owner ON sharing_permissions(owner_id);

    CREATE TABLE emergency_contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name TEXT NOT NULL, phone TEXT NOT NULL, relationship TEXT, created_at TEXT NOT NULL
    );
    CREATE TABLE emergency_info (
        user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        notes TEXT, updated_at TEXT NOT NULL
    );
    CREATE TABLE diet_preferences (
        user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        restrictions TEXT, preferences TEXT, updated_at TEXT NOT NULL
    );
    CREATE TABLE diet_guidance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        content TEXT NOT NULL, language TEXT NOT NULL, model TEXT, created_at TEXT NOT NULL
    );

    CREATE TABLE ai_conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title TEXT NOT NULL, created_at TEXT NOT NULL
    );
    CREATE TABLE ai_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL REFERENCES ai_conversations(id) ON DELETE CASCADE,
        role TEXT NOT NULL CHECK (role IN ('user','assistant')),
        content TEXT NOT NULL, sources TEXT, created_at TEXT NOT NULL
    );
    CREATE INDEX idx_ai_messages_conv ON ai_messages(conversation_id, id);

    CREATE TABLE activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        action TEXT NOT NULL, resource_type TEXT, resource_id INTEGER, created_at TEXT NOT NULL
    );
    CREATE INDEX idx_activity_owner ON activity_log(owner_id, id);
    """,
    """
    CREATE TABLE wellness_plans (
        owner_id    INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        goals       TEXT,
        content     TEXT,
        language    TEXT,
        model       TEXT,
        edited      INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT,
        updated_at  TEXT NOT NULL
    );
    """,
    # v5 — security audit trail (adds a table; touches no existing data)
    """
    CREATE TABLE IF NOT EXISTS security_events (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
        kind        TEXT NOT NULL,
        detail      TEXT,
        ip          TEXT,
        created_at  TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_security_events_user ON security_events(user_id, id);
    """,
]


def get_db():
    if "db" not in g:
        conn = sqlite3.connect(current_app.config["DATABASE"], timeout=15)  # wait, don't fail, if the background reader holds the file
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA secure_delete = ON")  # deleted health data is overwritten, not just unlinked
        g.db = conn
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db(path):
    conn = sqlite3.connect(path)
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        for i, script in enumerate(MIGRATIONS[version:], start=version + 1):
            conn.executescript(script)
            conn.execute(f"PRAGMA user_version = {i}")
        conn.commit()
    finally:
        conn.close()


def init_app(app):
    app.teardown_appcontext(close_db)
    init_db(app.config["DATABASE"])
