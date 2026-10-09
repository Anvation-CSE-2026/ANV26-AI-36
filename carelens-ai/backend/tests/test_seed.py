import os, shutil, tempfile, unittest
from app import create_app
from seed_demo import PASSWORD, seed


class SeedTest(unittest.TestCase):
    def test_seed_is_real_idempotent_and_private(self):
        d = tempfile.mkdtemp()
        try:
            app = create_app({"DATABASE": d + "/t.db", "SECRET_KEY": "x", "UPLOAD_DIR": d + "/u", "PROCESS_SYNC": True})
            self.assertTrue(seed(app)); self.assertFalse(seed(app))
            m, a, r = (app.test_client() for _ in range(3))
            for c, u in ((m, "meena"), (a, "aditya"), (r, "ravi")):
                self.assertEqual(c.post("/api/auth/login", json={"login_identifier": u, "password": PASSWORD}).status_code, 200)
            self.assertTrue(m.get("/api/auth/me").json["user"]["family"]["is_sample"])
            docs = m.get("/api/me/documents").json["items"]
            self.assertEqual((len(docs), docs[0]["processing_status"]), (1, "processed"))
            self.assertEqual(a.get("/api/me/documents").json["items"], [])
            self.assertEqual(a.get(f"/api/shared/documents/{docs[0]['id']}").status_code, 200)
            self.assertEqual(r.get(f"/api/shared/documents/{docs[0]['id']}").status_code, 404)
            uid = m.get("/api/auth/me").json["user"]["id"]
            self.assertEqual(r.get(f"/api/shared/people/{uid}/emergency").status_code, 200)
            self.assertEqual(a.get(f"/api/shared/people/{uid}/emergency").status_code, 404)
            prof = r.get(f"/api/family/members/{uid}").json
            self.assertEqual(prof["shared_with_you"][0]["label"], "Emergency information")
            self.assertEqual(r.patch("/api/family/members/" + str(uid), json={"relationship": "x"}).status_code, 403)
            self.assertEqual(m.get("/api/me/dashboard").json["reminders"]["pending"], 2)
        finally:
            shutil.rmtree(d, ignore_errors=True)
