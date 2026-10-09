import json

from tests.test_care import Base

ANALYSIS = {"summary": "Your blood count is mostly normal.", "findings": [{"label": "Hemoglobin", "detail": "11.2 g/dL"}],
            "terms": [{"term": "Hemoglobin", "meaning": "Protein that carries oxygen."}], "not_stated": ["The reason for the test."]}


class VoiceTests(Base):
    def test_requires_login(self):
        self.assertEqual(self.app.test_client().post("/api/ai/voice/report", json={}).status_code, 401)

    def test_no_documents(self):
        self.fake_ai("x")
        r = self.meena.post("/api/ai/voice/report", json={"mode": "summary"})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json["error"]["code"], "no_documents")

    def test_validation(self):
        self.assertEqual(self.meena.post("/api/ai/voice/report", json={"mode": "bogus"}).status_code, 422)
        self.assertEqual(self.meena.post("/api/ai/voice/report", json={"language": "xx"}).status_code, 422)
        self.assertEqual(self.meena.post("/api/ai/voice/report", json={"document_id": "1"}).status_code, 422)

    def test_summary_and_read_in_chosen_language(self):
        did = self.upload(self.meena)
        self.fake_ai(json.dumps(ANALYSIS))
        s = self.meena.post("/api/ai/voice/report", json={"mode": "summary", "language": "hi"})
        self.assertEqual(s.status_code, 200, s.json)
        self.assertEqual(s.json["text"], ANALYSIS["summary"])
        self.assertEqual(s.json["language"], "hi")
        self.assertEqual(s.json["document"]["id"], did)
        self.assertIn("Hindi", self.prompts[-1][0])
        r = self.meena.post("/api/ai/voice/report", json={"mode": "read", "language": "kn", "document_id": did})
        self.assertEqual(r.status_code, 200)
        self.assertIn("Hemoglobin: 11.2 g/dL", r.json["text"])
        self.assertIn("Protein that carries oxygen.", r.json["text"])
        self.assertIn("Kannada", self.prompts[-1][0])

    def test_long_document_analysis_includes_all_sections_in_chosen_language(self):
        first = "START OF FULL REPORT. Hemoglobin 11.2 g/dL.\n"
        last = "\nEND OF FULL REPORT. Platelet count 250."
        did = self.upload(self.meena, [first, "Additional report details. " * 700, last])
        self.fake_ai(json.dumps(ANALYSIS))

        r = self.meena.post("/api/ai/voice/report", json={"mode": "summary", "language": "kn", "document_id": did})

        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json["text"], ANALYSIS["summary"])
        user_prompts = "\n".join(messages[0]["content"] for _, messages in self.prompts)
        self.assertIn("START OF FULL REPORT", user_prompts)
        self.assertIn("END OF FULL REPORT", user_prompts)
        self.assertGreaterEqual(len(self.prompts), 3)
        self.assertTrue(all("Kannada" in system for system, _ in self.prompts))

    def test_other_members_document_needs_a_grant(self):
        did = self.upload(self.meena)
        self.fake_ai(json.dumps(ANALYSIS))
        self.assertEqual(self.aditya.post("/api/ai/voice/report", json={"document_id": did}).status_code, 404)
        self.assertEqual(self.share(self.meena, resource_type="document", resource_id=did, grantee_id=self.ids["Aditya"]).status_code, 201)
        self.assertEqual(self.aditya.post("/api/ai/voice/report", json={"document_id": did}).status_code, 200)

    def test_without_ai_read_works_and_summary_explains(self):
        self.upload(self.meena)
        r = self.meena.post("/api/ai/voice/report", json={"mode": "read"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json["ai"])
        self.assertIn("Hemoglobin", r.json["text"])
        s = self.meena.post("/api/ai/voice/report", json={"mode": "summary"})
        self.assertEqual(s.status_code, 503)

    def test_chat_language_override(self):
        self.fake_ai("Namaste")
        r = self.meena.post("/api/ai/chat", json={"message": "hello", "language": "kn"})
        self.assertEqual(r.status_code, 201)
        self.assertIn("Kannada", self.prompts[-1][0])
        self.assertEqual(self.meena.post("/api/ai/chat", json={"message": "hello", "language": "zz"}).status_code, 422)
        self.meena.post("/api/ai/chat", json={"message": "hello again"})
        self.assertIn("English", self.prompts[-1][0])
