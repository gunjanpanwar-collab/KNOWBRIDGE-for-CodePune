"""Gap interview tests. Run with: python -m unittest discover -s tests -v"""
import os
import sys
import tempfile
import unittest

os.environ["NO_AI"] = "1"
os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "test.db"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module  # noqa: E402
import db  # noqa: E402
from extract import run_extraction  # noqa: E402


class Interview(unittest.TestCase):
    def setUp(self):
        db.init_db()
        with db.get_db() as c:
            db.seed_demo(c, reset=True)
        self.rev = self.login("reviewer")
        self.extract = self.rev.post("/api/extract").get_json()

    def login(self, role):
        c = app_module.app.test_client()
        c.post("/api/login", json={"role": role})
        return c

    def questions(self, client):
        return client.get("/api/questions").get_json()["questions"]

    def approve_all(self):
        for c in self.rev.get("/api/claims").get_json()["claims"]:
            self.rev.post(f"/api/claims/{c['id']}", json={"review": "approved"})

    def test_one_question_per_gap_and_per_conflict_and_none_for_verified_claims(self):
        self.assertEqual(self.extract["questions"], 4)  # 3 missing claims + 1 conflict group
        prompts = [q["prompt"] for q in self.questions(self.rev)]
        self.assertTrue(any("PR #14" in p and "What happened" in p for p in prompts))
        self.assertTrue(any("confirmation email failure" in p and "Who should own" in p for p in prompts))
        self.assertTrue(any("deployment guide" in p for p in prompts))
        conflict = [q for q in self.questions(self.rev) if q["kind"] == "conflict"]
        self.assertEqual(len(conflict), 1)
        self.assertIn("30 September", conflict[0]["prompt"])
        self.assertIn("15 October", conflict[0]["prompt"])

    def test_running_extraction_again_does_not_duplicate_questions(self):
        self.rev.post("/api/extract")
        self.assertEqual(len(self.questions(self.rev)), 4)

    def test_answer_becomes_a_stated_claim_that_is_never_verified(self):
        leaver = self.login("leaver")
        qid = self.questions(leaver)[0]["id"]
        r = leaver.post(f"/api/questions/{qid}/answer", json={"answer": "It broke the signup page, so we rolled it back."})
        self.assertEqual(r.status_code, 200)
        stated = [c for c in self.rev.get("/api/claims").get_json()["claims"] if c["type"] == "Leaver answer"]
        self.assertEqual(len(stated), 1)
        self.assertEqual((stated[0]["status"], stated[0]["review"]), ("stated", "pending"))
        self.assertIn("rolled it back", stated[0]["text"])
        self.assertIn("departing member", stated[0]["text"])

    def test_answer_does_not_reach_the_handover_until_approved(self):
        leaver = self.login("leaver")
        qid = self.questions(leaver)[0]["id"]
        leaver.post(f"/api/questions/{qid}/answer", json={"answer": "Rolled back because of a bug."})
        before = self.login("developer").get("/api/handover").get_json()
        self.assertNotIn("Rolled back", str(before))
        self.approve_all()
        after = self.login("developer").get("/api/handover").get_json()
        self.assertIn("Rolled back", str(after))
        mine = [c for c in after["claims"] if c["type"] == "Leaver answer"]
        self.assertEqual(mine[0]["status"], "stated")

    def test_answering_twice_edits_the_same_claim_and_reopens_review(self):
        leaver = self.login("leaver")
        qid = self.questions(leaver)[0]["id"]
        leaver.post(f"/api/questions/{qid}/answer", json={"answer": "First answer."})
        self.approve_all()
        leaver.post(f"/api/questions/{qid}/answer", json={"answer": "Second, better answer."})
        stated = [c for c in self.rev.get("/api/claims").get_json()["claims"] if c["type"] == "Leaver answer"]
        self.assertEqual(len(stated), 1)
        self.assertIn("Second, better answer.", stated[0]["text"])
        self.assertEqual(stated[0]["review"], "pending")  # the edited answer must be approved again

    def test_empty_and_oversized_answers_are_rejected(self):
        leaver = self.login("leaver")
        qid = self.questions(leaver)[0]["id"]
        self.assertEqual(leaver.post(f"/api/questions/{qid}/answer", json={"answer": "   "}).status_code, 400)
        self.assertEqual(leaver.post(f"/api/questions/{qid}/answer", json={}).status_code, 400)
        self.assertEqual(leaver.post(f"/api/questions/{qid}/answer", json={"answer": "x" * 1001}).status_code, 400)
        self.assertEqual(leaver.post("/api/questions/9999/answer", json={"answer": "hi"}).status_code, 404)

    def test_only_the_departing_member_can_answer_and_only_reviewer_or_leaver_can_read(self):
        qid = self.questions(self.rev)[0]["id"]
        self.assertEqual(self.rev.post(f"/api/questions/{qid}/answer", json={"answer": "hi"}).status_code, 403)
        for role in ("developer", "member"):
            c = self.login(role)
            self.assertEqual(c.get("/api/questions").status_code, 403)
            self.assertEqual(c.post(f"/api/questions/{qid}/answer", json={"answer": "hi"}).status_code, 403)
        self.assertEqual(app_module.app.test_client().get("/api/questions").status_code, 401)

    def test_answer_about_a_github_gap_is_hidden_from_a_role_that_cannot_open_github(self):
        leaver = self.login("leaver")
        pr = next(q for q in self.questions(leaver) if "PR #14" in q["prompt"])
        leaver.post(f"/api/questions/{pr['id']}/answer", json={"answer": "Rolled back: it emailed everyone twice."})
        self.approve_all()
        dev = self.login("developer").get("/api/handover").get_json()
        member = self.login("member").get("/api/handover").get_json()
        self.assertIn("emailed everyone twice", str(dev))        # developer may open the GitHub export
        self.assertNotIn("emailed everyone twice", str(member))  # member may not, so the answer is hidden too
        self.assertNotIn("PR #14", str(member))

    def test_leaver_never_sees_or_can_answer_a_question_from_a_restricted_source(self):
        def proposer(conn):
            return [{"type": "Open question", "kind": "gap", "statement": "Why was the sponsor not told?",
                     "evidence": [{"source": "leadership_chat_private.txt",
                                   "quote": "Not yet. Let's wait until the sponsor confirms the new date."}]},
                    {"type": "Open question", "kind": "gap", "statement": "Who renews the domain?",
                     "evidence": [{"source": "meeting_notes_12.md", "quote": "Dev renews the domain every August."}]}]
        with db.get_db() as conn:
            run_extraction(conn, proposer=proposer)
        leaver = self.login("leaver")
        mine = self.questions(leaver)
        self.assertEqual(len(mine), 1)
        self.assertNotIn("sponsor", str(mine).lower())
        self.assertEqual(len(self.questions(self.rev)), 2)
        hidden = next(q for q in self.questions(self.rev) if "sponsor" in q["prompt"].lower())
        self.assertEqual(leaver.post(f"/api/questions/{hidden['id']}/answer", json={"answer": "x"}).status_code, 404)

    def test_answers_are_masked_like_any_other_text(self):
        leaver = self.login("leaver")
        qid = self.questions(leaver)[0]["id"]
        leaver.post(f"/api/questions/{qid}/answer", json={"answer": "Ask Dev on +91 98765 43210, the password is hunter2."})
        text = str(self.rev.get("/api/claims").get_json())
        self.assertNotIn("98765", text)
        self.assertNotIn("hunter2", text)
        self.assertIn("REDACTED", text)

    def test_reviewer_sees_answers_but_the_question_list_for_a_leaver_marks_saved_answers(self):
        leaver = self.login("leaver")
        qid = self.questions(leaver)[0]["id"]
        leaver.post(f"/api/questions/{qid}/answer", json={"answer": "Because of exams."})
        mine = next(q for q in self.questions(leaver) if q["id"] == qid)
        self.assertEqual(mine["answer"], "Because of exams.")
        seen_by_reviewer = next(q for q in self.questions(self.rev) if q["id"] == qid)
        self.assertEqual(seen_by_reviewer["answer"], "Because of exams.")

    def test_leaver_can_open_only_the_sources_their_role_allows(self):
        names = [s["filename"] for s in self.login("leaver").get("/api/sources").get_json()["sources"]]
        self.assertNotIn("leadership_chat_private.txt", names)
        self.assertIn("github_export.json", names)


if __name__ == "__main__":
    unittest.main()
