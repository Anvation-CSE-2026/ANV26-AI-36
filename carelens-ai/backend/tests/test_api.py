import os
import sqlite3
import tempfile
import unittest

from app import create_app

FAMILY = {
    "family_name": "Rao",
    "primary": {"name": "Aishu", "login_identifier": "Aishu@Home", "password": "correct-horse"},
    "members": [
        {"name": "Meera", "relationship": "Mother", "login_identifier": "meera", "password": "password-1"},
        {"name": "Ravi", "relationship": "Father", "login_identifier": "ravi", "password": "password-2"},
    ],
}


class ApiTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.app = create_app({"DATABASE": self.path, "SECRET_KEY": "test", "TESTING": False, "PROCESS_SYNC": True})
        self.c = self.app.test_client()

    def tearDown(self):
        os.unlink(self.path)

    def other(self):
        return self.app.test_client()

    def register(self, client=None, body=None):
        return (client or self.c).post("/api/families", json=body or FAMILY)

    def test_register_stores_family_and_hashes_passwords(self):
        r = self.register()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json["user"]["login_identifier"], "aishu@home")
        rows = sqlite3.connect(self.path).execute("SELECT password_hash FROM users").fetchall()
        self.assertEqual(len(rows), 3)
        for (h,) in rows:
            self.assertNotIn("correct-horse", h)
            self.assertNotIn("password-1", h)
            self.assertTrue(h.startswith(("scrypt:", "pbkdf2:")))
        self.assertEqual(self.c.get("/api/auth/me").status_code, 200)

    def test_register_validation_and_duplicates(self):
        bad = {"family_name": "", "primary": {"name": "A", "login_identifier": "x", "password": "short"}}
        r = self.c.post("/api/families", json=bad)
        self.assertEqual(r.status_code, 422)
        self.assertIn("family_name", r.json["error"]["fields"])
        self.assertIn("primary.password", r.json["error"]["fields"])
        self.assertEqual(self.register().status_code, 201)
        r = self.register(self.other())
        self.assertEqual(r.status_code, 409)
        self.assertIn("primary.login_identifier", r.json["error"]["fields"])

    def test_login_logout_and_protection(self):
        self.register()
        c = self.other()
        self.assertEqual(c.get("/api/auth/me").status_code, 401)
        self.assertEqual(c.get("/api/family").status_code, 401)
        self.assertEqual(c.get("/api/me/documents").status_code, 401)
        self.assertEqual(c.post("/api/auth/login", json={"login_identifier": "meera", "password": "nope"}).status_code, 401)
        self.assertEqual(c.post("/api/auth/login", json={"login_identifier": "", "password": ""}).status_code, 422)
        r = c.post("/api/auth/login", json={"login_identifier": "MEERA", "password": "password-1"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json["user"]["name"], "Meera")
        self.assertEqual(c.get("/api/me/documents").json, {"items": []})
        self.assertEqual(c.post("/api/auth/logout", json={}).status_code, 200)
        self.assertEqual(c.get("/api/auth/me").status_code, 401)

    def test_family_listing_and_member_permissions(self):
        self.register()
        r = self.c.get("/api/family")
        self.assertEqual([m["name"] for m in r.json["members"]], ["Aishu", "Meera", "Ravi"])
        self.assertTrue(r.json["members"][0]["is_you"])
        self.assertNotIn("password_hash", r.text)
        new = {"name": "Kiran", "relationship": "Brother", "login_identifier": "kiran", "password": "password-3"}
        self.assertEqual(self.c.post("/api/family/members", json=new).status_code, 201)
        self.assertEqual(len(self.c.get("/api/family").json["members"]), 4)
        self.assertEqual(self.c.post("/api/family/members", json=new).status_code, 409)
        m = self.other()
        m.post("/api/auth/login", json={"login_identifier": "meera", "password": "password-1"})
        new2 = dict(new, login_identifier="kiran2")
        self.assertEqual(m.post("/api/family/members", json=new2).status_code, 403)

    def test_families_are_isolated(self):
        self.register()
        c2 = self.other()
        body = {"family_name": "Other", "primary": {"name": "Zed", "login_identifier": "zed.user", "password": "zedzedzed"}}
        self.assertEqual(self.register(c2, body).status_code, 201)
        names = [m["name"] for m in c2.get("/api/family").json["members"]]
        self.assertEqual(names, ["Zed"])

    def test_profile_and_password(self):
        self.register()
        self.assertEqual(self.c.patch("/api/me", json={"name": "Aishwarya"}).json["user"]["name"], "Aishwarya")
        self.assertEqual(self.c.patch("/api/me", json={"name": " "}).status_code, 422)
        r = self.c.post("/api/me/password", json={"current_password": "bad", "new_password": "brand-new-pass"})
        self.assertEqual(r.status_code, 422)
        r = self.c.post("/api/me/password", json={"current_password": "correct-horse", "new_password": "brand-new-pass"})
        self.assertEqual(r.status_code, 200)
        c = self.other()
        self.assertEqual(c.post("/api/auth/login", json={"login_identifier": "aishu@home", "password": "correct-horse"}).status_code, 401)
        self.assertEqual(c.post("/api/auth/login", json={"login_identifier": "aishu@home", "password": "brand-new-pass"}).status_code, 200)

    def test_non_json_writes_rejected_and_login_rate_limited(self):
        r = self.c.post("/api/auth/login", data="login_identifier=a&password=b",
                        headers={"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(r.status_code, 415)
        self.register()
        codes = [self.other().post("/api/auth/login", json={"login_identifier": "ravi", "password": "wrong"}).status_code for _ in range(12)]
        self.assertEqual(codes[0], 401)
        self.assertEqual(codes[-1], 429)

    def test_unknown_api_route_is_json_404(self):
        r = self.c.get("/api/nope")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json["error"]["code"], "not_found")


if __name__ == "__main__":
    unittest.main()
