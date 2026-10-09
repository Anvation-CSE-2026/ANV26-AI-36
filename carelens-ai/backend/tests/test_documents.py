import io
import os
import shutil
import sqlite3
import struct
import tempfile
import unittest
import zlib

from app import create_app


def make_png():
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = zlib.compress(b"\x00\xff\x00\x00")
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", raw) + chunk(b"IEND", b""))


PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
PNG = make_png()
JPG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"

FAMILY = {
    "family_name": "Rao",
    "primary": {"name": "Meena", "login_identifier": "meena", "password": "meena-pass-1"},
    "members": [
        {"name": "Aditya", "relationship": "Son", "login_identifier": "aditya", "password": "aditya-pass-1"},
    ],
}


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.db = os.path.join(self.dir, "t.db")
        self.uploads = os.path.join(self.dir, "uploads")
        self.app = create_app({"DATABASE": self.db, "SECRET_KEY": "t", "UPLOAD_DIR": self.uploads, "PROCESS_SYNC": True})
        self.meena = self.app.test_client()
        self.aditya = self.app.test_client()
        self.anon = self.app.test_client()
        self.meena.post("/api/families", json=FAMILY)
        # each member signs in independently with their own credentials
        r = self.aditya.post("/api/auth/login", json={"login_identifier": "aditya", "password": "aditya-pass-1"})
        self.assertEqual(r.json["user"]["name"], "Aditya")
        self.assertEqual(self.meena.get("/api/auth/me").json["user"]["name"], "Meena")

    def tearDown(self):
        shutil.rmtree(self.dir)

    def upload(self, client, name="Insurance.pdf", data=PDF):
        return client.post("/api/me/documents", data={"file": (io.BytesIO(data), name)},
                           content_type="multipart/form-data")

    def test_upload_stores_record_and_file_for_owner_only(self):
        r = self.upload(self.meena)
        self.assertEqual(r.status_code, 201)
        doc = r.json["document"]
        self.assertEqual((doc["filename"], doc["file_type"], doc["file_size"], doc["processing_status"]),
                         ("Insurance.pdf", "application/pdf", len(PDF), "uploaded"))
        self.assertNotIn("storage_path", doc)
        row = sqlite3.connect(self.db).execute("SELECT owner_id, storage_path FROM documents").fetchone()
        meena_id = self.meena.get("/api/auth/me").json["user"]["id"]
        self.assertEqual(row[0], meena_id)
        self.assertTrue(os.path.isfile(os.path.join(self.uploads, row[1])))
        self.assertEqual([d["id"] for d in self.meena.get("/api/me/documents").json["items"]], [doc["id"]])
        self.assertEqual(self.aditya.get("/api/me/documents").json["items"], [])

    def test_other_member_cannot_reach_document_by_any_route(self):
        did = self.upload(self.meena).json["document"]["id"]
        base = f"/api/me/documents/{did}"
        for path in (base, base + "/file"):
            self.assertEqual(self.aditya.get(path).status_code, 404, path)
        self.assertEqual(self.aditya.delete(base).status_code, 404)
        # still there for the owner, bytes intact
        self.assertEqual(self.meena.get(base).status_code, 200)
        self.assertEqual(self.meena.get(base + "/file").data, PDF)
        self.assertEqual(self.meena.get(base + "/file").mimetype, "application/pdf")

    def test_client_supplied_ids_are_ignored(self):
        did = self.upload(self.meena).json["document"]["id"]
        # owner/user ids in query string or body don't change who the caller is
        mid = self.meena.get("/api/auth/me").json["user"]["id"]
        r = self.aditya.get(f"/api/me/documents?owner_id={mid}&user_id={mid}")
        self.assertEqual(r.json["items"], [])
        r = self.aditya.post("/api/me/documents", data={"file": (io.BytesIO(PNG), "a.png"), "owner_id": str(mid)},
                             content_type="multipart/form-data")
        self.assertEqual(r.status_code, 201)
        owners = sqlite3.connect(self.db).execute("SELECT owner_id FROM documents ORDER BY id").fetchall()
        self.assertEqual(owners[1][0], self.aditya.get("/api/auth/me").json["user"]["id"])
        self.assertEqual([d["filename"] for d in self.meena.get("/api/me/documents").json["items"]], ["Insurance.pdf"])
        # primary member / family head gets no special access either
        self.assertEqual(self.meena.get(f"/api/me/documents/{did + 1}").status_code, 404)

    def test_logged_out_access_is_rejected(self):
        did = self.upload(self.meena).json["document"]["id"]
        base = f"/api/me/documents/{did}"
        for method, path in (("get", "/api/me/documents"), ("get", base), ("get", base + "/file"), ("delete", base)):
            self.assertEqual(getattr(self.anon, method)(path).status_code, 401, path)
        self.assertEqual(self.upload(self.anon).status_code, 401)
        self.assertEqual(self.anon.get("/api/me/knowledge").status_code, 401)
        self.assertEqual(self.anon.get("/api/sharing").status_code, 401)

    def test_only_owner_can_delete_and_file_is_removed(self):
        did = self.upload(self.meena).json["document"]["id"]
        rel = sqlite3.connect(self.db).execute("SELECT storage_path FROM documents").fetchone()[0]
        path = os.path.join(self.uploads, rel)
        self.assertEqual(self.aditya.delete(f"/api/me/documents/{did}").status_code, 404)
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(self.meena.delete(f"/api/me/documents/{did}").status_code, 200)
        self.assertFalse(os.path.exists(path))
        self.assertEqual(self.meena.get("/api/me/documents").json["items"], [])
        self.assertEqual(self.meena.delete(f"/api/me/documents/{did}").status_code, 404)

    def test_validation(self):
        bad = {
            "text renamed pdf": ("notes.pdf", b"just some text"),
            "exe": ("run.exe", b"MZ\x90\x00"),
            "png named pdf": ("pic.pdf", PNG),
            "pdf named png": ("doc.png", PDF),
            "no extension": ("insurance", PDF),
            "empty": ("empty.pdf", b""),
        }
        for label, (name, data) in bad.items():
            self.assertIn(self.upload(self.meena, name, data).status_code, (422,), label)
        self.assertEqual(self.upload(self.meena, "big.pdf", b"%PDF-" + b"0" * (10 * 1024 * 1024)).status_code, 413)
        self.assertEqual(self.meena.post("/api/me/documents", data={}, content_type="multipart/form-data").status_code, 422)
        ok = [("a.jpg", JPG), ("b.JPEG", JPG), ("c.png", PNG), ("d.PDF", PDF)]
        for name, data in ok:
            self.assertEqual(self.upload(self.meena, name, data).status_code, 201, name)
        types = {d["file_type"] for d in self.meena.get("/api/me/documents").json["items"]}
        self.assertEqual(types, {"image/jpeg", "image/png", "application/pdf"})

    def test_filename_cannot_escape_storage(self):
        r = self.upload(self.meena, "../../etc/passwd.pdf")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json["document"]["filename"], "passwd.pdf")
        rel = sqlite3.connect(self.db).execute("SELECT storage_path FROM documents").fetchone()[0]
        self.assertRegex(rel, r"^\d+/[0-9a-f]{32}\.pdf$")
        self.assertFalse(os.path.exists(os.path.join(self.dir, "etc")))

    def test_foreign_origin_writes_blocked(self):
        r = self.meena.post("/api/me/documents", data={"file": (io.BytesIO(PDF), "x.pdf")},
                            content_type="multipart/form-data", headers={"Origin": "https://evil.example"})
        self.assertEqual(r.status_code, 403)
        r = self.meena.post("/api/auth/logout", json={}, headers={"Origin": "https://evil.example"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.meena.get("/api/auth/me").status_code, 200)

    def test_password_change_ends_other_sessions(self):
        other_device = self.app.test_client()
        other_device.post("/api/auth/login", json={"login_identifier": "meena", "password": "meena-pass-1"})
        self.assertEqual(other_device.get("/api/me/documents").status_code, 200)
        r = self.meena.post("/api/me/password", json={"current_password": "meena-pass-1", "new_password": "new-meena-pass"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.meena.get("/api/me/documents").status_code, 200)
        self.assertEqual(other_device.get("/api/me/documents").status_code, 401)

    def test_family_endpoint_exposes_no_documents(self):
        self.upload(self.meena)
        body = self.aditya.get("/api/family").text
        self.assertNotIn("Insurance", body)
        self.assertNotIn("documents", body)


if __name__ == "__main__":
    unittest.main()
