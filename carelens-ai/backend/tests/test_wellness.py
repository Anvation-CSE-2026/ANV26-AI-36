import json
import unittest

from services import wellness
from tests.test_care import Base


def plan_reply(**over):
    base = {"facts": [{"text": "Your report says Type 2 diabetes.", "doc_id": 1, "quote": "Type 2 diabetes mellitus"},
                      {"text": "Invented fact", "doc_id": 1, "quote": "this phrase is not in the document"}],
            "diet": {"summary": "S", "items": [{"text": "Choose millets", "basis": "F1"}, {"text": "Peanut chutney", "basis": "general"}], "avoid": []},
            "exercise": {"summary": "Gentle", "items": [{"text": "Walk 20 minutes", "basis": "general"}], "cautions": []},
            "sleep_mental": {"summary": "Sleep", "items": [{"text": "Fixed bedtime", "basis": "general"}]},
            "therapies": [{"name": "Yoga", "benefits": "Relaxation", "risks": "Strain", "evidence": "Mixed", "ask_doctor": "Ask first"},
                          {"name": "Herbal cure", "benefits": "It cures diabetes", "risks": "", "evidence": "", "ask_doctor": ""}],
            "weekly_plan": [{"day": "Monday", "items": ["Walk", "Stop taking your tablets"]}],
            "follow_ups": [], "limits": []}
    base.update(over)
    return json.dumps(base)


class WellnessTests(Base):
    def setUp(self):
        super().setUp()
        self.upload(self.meena, lines=["Diagnosis: Type 2 diabetes mellitus", "Fasting Glucose 142 mg/dL 70-100"], name="Diabetes Report.pdf")
        self.meena.post("/api/me/health/records", json={"kind": "allergy", "title": "Peanut"})

    def test_requires_ai_and_information(self):
        self.assertEqual(self.meena.post("/api/me/wellness/generate", json={}).status_code, 503)   # nothing is fabricated offline
        self.fake_ai(plan_reply())
        self.assertEqual(self.aditya.post("/api/me/wellness/generate", json={}).status_code, 422)  # Aditya has no information of his own

    def test_generate_validates_and_labels(self):
        self.fake_ai(plan_reply())
        r = self.meena.post("/api/me/wellness/generate", json={})
        self.assertEqual(r.status_code, 201)
        p = r.json["plan"]
        self.assertEqual([f["quote"] for f in p["facts"]], ["Type 2 diabetes mellitus"])             # unverifiable fact dropped
        self.assertFalse(p["facts"][0]["confirmed"])                                                  # needs the user's confirmation
        self.assertEqual([i["text"] for i in p["diet"]["items"]], ["Choose millets"])                 # allergen removed
        self.assertEqual(p["diet"]["items"][0]["basis"], "F1")
        self.assertEqual([t["name"] for t in p["therapies"]], ["Yoga"])                               # cure claim removed
        self.assertEqual(p["weekly_plan"][0]["items"], ["Walk"])                                      # medication advice removed
        self.assertIn("Type 2 diabetes", self.prompts[-1][1][0]["content"])
        self.assertIn("never name a disease", self.prompts[-1][0].lower())

    def test_edit_confirm_and_privacy(self):
        self.fake_ai(plan_reply())
        self.meena.post("/api/me/wellness/generate", json={})
        p = self.meena.get("/api/me/wellness").json["plan"]
        p["facts"][0]["confirmed"] = True
        p["facts"][0]["quote"] = "tampered"
        p["diet"]["items"].append({"text": "Add more dal", "basis": "general"})
        r = self.meena.put("/api/me/wellness/plan", json={"plan": p})
        self.assertEqual(r.status_code, 200)
        saved = r.json["plan"]
        self.assertTrue(saved["facts"][0]["confirmed"])
        self.assertEqual(saved["facts"][0]["quote"], "Type 2 diabetes mellitus")                      # facts cannot be rewritten
        self.assertEqual(len(saved["diet"]["items"]), 2)
        self.assertTrue(r.json["meta"]["edited"])
        self.assertIsNone(self.aditya.get("/api/me/wellness").json["plan"])                           # another member sees nothing
        self.assertEqual(self.aditya.put("/api/me/wellness/plan", json={"plan": p}).status_code, 404)
        self.assertEqual(self.outsider.get("/api/me/wellness").json["goals"], "")

    def test_goals_and_pending_medicines(self):
        self.assertEqual(self.meena.put("/api/me/wellness/goals", json={"goals": "x" * 700}).status_code, 422)
        self.assertEqual(self.meena.put("/api/me/wellness/goals", json={"goals": "Lose weight slowly"}).json["goals"], "Lose weight slowly")
        import sqlite3
        c = sqlite3.connect(self.db); c.row_factory = sqlite3.Row
        self.assertIn("Lose weight", wellness.gather(c, self.ids["Meena"])[0])
        self.assertNotIn("Lose weight", wellness.gather(c, self.ids["Aditya"])[0])

    def test_page_numbers_from_quotes(self):
        docs = {7: {"filename": "a.pdf", "pages": ["Intro text", "Advice: avoid sugary drinks daily"]}}
        plan = wellness.clean({"facts": [{"text": "Avoid sugary drinks", "doc_id": 7, "quote": "avoid sugary drinks"}]}, docs, [])
        self.assertEqual(plan["facts"][0]["page"], 2)
        self.assertEqual(wellness.clean({"facts": [{"text": "x", "doc_id": 99, "quote": "Intro text"}]}, docs, [])["facts"], [])


if __name__ == "__main__":
    unittest.main()
