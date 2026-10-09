"""Permission model: OWNER -> grant -> AUTHORIZED MEMBER -> data.

A member can read another member's record only through an active, unexpired,
unrevoked row in sharing_permissions — and only while both are in the same
family. Family membership alone never grants access.
"""
from utils import now_iso


def has_grant(db, user_id, owner_id, resource_type, resource_id=None):
    if owner_id == user_id:
        return True
    row = db.execute(
        """SELECT 1 FROM sharing_permissions sp
           JOIN users o ON o.id = sp.owner_id
           JOIN users g ON g.id = sp.grantee_id
           WHERE sp.owner_id = ? AND sp.grantee_id = ? AND sp.resource_type = ?
             AND sp.revoked_at IS NULL AND (sp.expires_at IS NULL OR sp.expires_at > ?)
             AND o.family_id = g.family_id
             AND (sp.resource_id IS NULL OR sp.resource_id IS ?)
           LIMIT 1""",
        (owner_id, user_id, resource_type, now_iso(), resource_id),
    ).fetchone()
    return row is not None


def received_grants(db, user_id):
    """Active grants other members have given this user (with owner names)."""
    return db.execute(
        """SELECT sp.id, sp.owner_id, sp.resource_type, sp.resource_id, sp.created_at, sp.expires_at,
                  o.name AS owner_name
           FROM sharing_permissions sp
           JOIN users o ON o.id = sp.owner_id
           JOIN users g ON g.id = sp.grantee_id
           WHERE sp.grantee_id = ? AND sp.revoked_at IS NULL
             AND (sp.expires_at IS NULL OR sp.expires_at > ?) AND o.family_id = g.family_id
           ORDER BY sp.id DESC""",
        (user_id, now_iso()),
    ).fetchall()


def log_activity(db, actor_id, owner_id, action, resource_type=None, resource_id=None):
    with db:
        db.execute(
            "INSERT INTO activity_log (actor_id, owner_id, action, resource_type, resource_id, created_at) VALUES (?,?,?,?,?,?)",
            (actor_id, owner_id, action, resource_type, resource_id, now_iso()),
        )
