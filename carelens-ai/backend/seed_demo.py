"""Create a clearly-marked sample family so the product can be explored immediately.

    python seed_demo.py

Everything is created through the same code paths as real use (real PDF upload,
real extraction). The family is flagged as sample data and the app labels it.
Sign in as  meena / aditya / ravi  with password  sample-pass-1
"""
import io
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

from app import create_app
from services.samplepdf import SAMPLE_REPORT, make_text_pdf

PASSWORD = "sample-pass-1"


def seed(app):
    with sqlite3.connect(app.config["DATABASE"]) as c:
        if c.execute("SELECT 1 FROM families WHERE is_sample = 1").fetchone():
            return False
    meena, aditya, ravi = (app.test_client() for _ in range(3))
    meena.post("/api/families", json={
        "family_name": "Sample family", "primary": {"name": "Meena", "login_identifier": "meena", "password": PASSWORD},
        "members": [{"name": "Aditya", "relationship": "Son", "login_identifier": "aditya", "password": PASSWORD},
                    {"name": "Ravi", "relationship": "Husband", "login_identifier": "ravi", "password": PASSWORD}]})
    with sqlite3.connect(app.config["DATABASE"]) as c:
        c.execute("UPDATE families SET is_sample = 1")
    aditya.post("/api/auth/login", json={"login_identifier": "aditya", "password": PASSWORD})
    ids = {r["name"]: r["id"] for r in meena.get("/api/family").json["members"]}

    meena.put("/api/me/health", json={"sex": "female", "blood_group": "O+", "date_of_birth": "1984-06-12"})
    meena.post("/api/me/health/records", json={"kind": "allergy", "title": "Peanuts", "detail": "Sample entry"})
    meena.post("/api/me/health/records", json={"kind": "condition", "title": "Type 2 diabetes", "detail": "Sample entry"})
    meena.put("/api/me/diet/preferences", json={"restrictions": "Vegetarian", "preferences": "Prefers millets and lentils"})
    meena.put("/api/me/emergency", json={"notes": "Sample entry — carries a medicine card in her wallet"})
    meena.post("/api/me/emergency/contacts", json={"name": "Ravi", "phone": "+91 98765 43210", "relationship": "Husband"})

    doc = meena.post("/api/me/documents", content_type="multipart/form-data",
                     data={"file": (io.BytesIO(make_text_pdf(SAMPLE_REPORT)), "Sample - Blood report.pdf")}).json["document"]
    for m in meena.get("/api/me/medicines").json["items"]:
        if m["name"] == "Metformin":
            meena.patch(f"/api/me/medicines/{m['id']}", json={"verified": True})
            when = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
            meena.post("/api/me/reminders", json={"title": "Take Metformin", "kind": "medicine",
                                                  "due_at": when.isoformat(), "medicine_id": m["id"], "description": "After breakfast"})
    when = (datetime.now(timezone.utc) + timedelta(days=28)).replace(hour=9, minute=30, second=0, microsecond=0)
    meena.post("/api/me/reminders", json={"title": "Follow-up review", "kind": "appointment", "due_at": when.isoformat()})
    meena.post("/api/me/timeline/events", json={"kind": "appointment", "title": "Doctor visit (sample)", "event_date": "2026-09-20"})
    meena.post("/api/sharing", json={"grantee_id": ids["Aditya"], "resource_type": "document", "resource_id": doc["id"]})
    meena.post("/api/sharing", json={"grantee_id": ids["Ravi"], "resource_type": "emergency"})
    return True


if __name__ == "__main__":
    app = create_app({"PROCESS_SYNC": True})
    print("Sample family created." if seed(app) else "Sample family already exists.")
    print(f"Sign in as meena, aditya or ravi — password: {PASSWORD}")
