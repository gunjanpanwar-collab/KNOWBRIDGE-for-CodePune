"""Conflict detection tests. Run with: python -m unittest discover -s tests -v"""
import os
import sys
import tempfile
import unittest

os.environ["NO_AI"] = "1"
os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "test.db"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module  # noqa: E402
import db  # noqa: E402
from conflicts import find_conflicts, parse_date, same_subject, values_differ  # noqa: E402
from extract import run_extraction  # noqa: E402


class Rules(unittest.TestCase):
    def test_dates_in_different_formats_are_the_same_day(self):
        self.assertFalse(values_differ("15 October", "2026-10-15"))
        self.assertFalse(values_differ("Oct 15, 2026", "15th October 2026"))
        self.assertFalse(values_differ("15/10/2026", "15 October"))
        self.assertTrue(values_differ("30 September", "15 October"))
        self.assertTrue(values_differ("15 October 2025", "15 October 2026"))

    def test_non_dates(self):
        self.assertTrue(values_differ("Karan", "Meera"))
        self.assertFalse(values_differ("Karan", "karan sharma"))
        self.assertFalse(values_differ("", "Meera"))  # missing value never conflicts
        self.assertIsNone(parse_date("Karan"))

    def test_subject_matching(self):
        self.assertTrue(same_subject("Razorpay switch deadline", "Deadline for the Razorpay switch"))
        self.assertTrue(same_subject("Razorpay switch deadline", "razorpay checkout switch deadline"))
        self.assertFalse(same_subject("email bug owner", "domain renewal owner"))
        self.assertFalse(same_subject("", "anything"))

    def test_grouping(self):
        items = [{"subject": "Razorpay deadline", "value": "30 September"},
                 {"subject": "Deadline for Razorpay", "value": "15 October"},
                 {"subject": "razorpay deadline", "value": "2026-10-15"},
                 {"subject": "Mobile menu owner", "value": "Meera"},
                 {"subject": "Mobile menu owner", "value": "Meera"},
                 {"subject": "", "value": "x"}]
        self.assertEqual(find_conflicts(items), [[0, 1, 2]])

    def test_agreeing_claims_do_not_conflict(self):
        items = [{"subject": "Menu owner", "value": "Meera"}, {"subject": "Owner of menu", "value": "Meera"}]
        self.assertEqual(find_conflicts(items), [])


class InTheApp(unittest.TestCase):
    def setUp(self):
        db.init_db()
        with db.get_db() as c:
            db.seed_demo(c, reset=True)

    def login(self, role):
        c = app_module.app.test_client()
        c.post("/api/login", json={"role": role})
        return c

    def test_demo_deadline_conflict_is_flagged_with_both_sides(self):
        rev = self.login("reviewer")
        rev.post("/api/extract")
        claims = rev.get("/api/claims").get_json()["claims"]
        conflicting = [c for c in claims if c["status"] == "conflicting"]
        self.assertEqual(len(conflicting), 3)
        quotes = " ".join(e["quote"] for c in conflicting for e in c["evidence"])
        self.assertIn("30 September", quotes)
        self.assertIn("15 October", quotes)
        by_text = {c["text"]: len(c["conflicts_with"]) for c in conflicting}
        # the 30 September claim disagrees with both others; the two 15 October claims agree with each other
        self.assertEqual(sorted(by_text.values()), [1, 1, 2])

    def test_rejecting_the_stale_claims_resolves_the_conflict(self):
        rev = self.login("reviewer")
        rev.post("/api/extract")
        claims = rev.get("/api/claims").get_json()["claims"]
        conflicting = [c for c in claims if c["status"] == "conflicting"]
        stale = next(c for c in conflicting if "30 September" in c["text"])
        rev.post(f"/api/claims/{stale['id']}", json={"review": "rejected"})
        after = rev.get("/api/claims").get_json()["claims"]
        # the two remaining claims agree with each other (15 October), so no live conflict remains
        live = [c for c in after if c["review"] != "rejected"]
        self.assertEqual([c for c in live if c["status"] == "conflicting"], [])
        self.assertEqual(sum(1 for c in live if c["status"] == "verified" and "Razorpay" in c["text"] and "15" in c["text"]), 2)

    def test_conflicting_claims_reach_the_handover_labelled_and_with_the_other_side(self):
        rev = self.login("reviewer")
        rev.post("/api/extract")
        for c in rev.get("/api/claims").get_json()["claims"]:
            rev.post(f"/api/claims/{c['id']}", json={"review": "approved"})
        h = self.login("member").get("/api/handover").get_json()
        conflicting = [c for c in h["claims"] if c["status"] == "conflicting"]
        self.assertEqual(len(conflicting), 3)
        self.assertTrue(all(c["conflicts"] for c in conflicting))
        self.assertTrue(any("disagree" in line.lower() for line in h["plan"]["week1"]))

    def test_counterpart_from_a_restricted_source_is_never_sent(self):
        def proposer(conn):
            return [
                {"type": "Decision", "kind": "fact", "subject": "Launch date", "value": "1 December",
                 "statement": "Launch is 1 December.",
                 "evidence": [{"source": "meeting_notes_12.md", "quote": "Dev renews the domain every August."}]},
                {"type": "Decision", "kind": "fact", "subject": "Launch date", "value": "9 January",
                 "statement": "SECRET leadership says launch is 9 January.",
                 "evidence": [{"source": "leadership_chat_private.txt", "quote": "Not yet. Let's wait until the sponsor confirms the new date."}]},
            ]
        with db.get_db() as conn:
            r = run_extraction(conn, proposer=proposer)
        self.assertEqual(r["conflicting"], 2)
        rev = self.login("reviewer")
        for c in rev.get("/api/claims").get_json()["claims"]:
            rev.post(f"/api/claims/{c['id']}", json={"review": "approved"})
        h = self.login("member").get("/api/handover").get_json()
        self.assertNotIn("secret", str(h).lower())
        self.assertNotIn("9 january", str(h).lower())
        visible = [c for c in h["claims"] if c["status"] == "conflicting"]
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0]["conflicts"], [])
        self.assertEqual(visible[0]["hidden_conflicts"], 1)

    def test_claims_with_unfound_quotes_never_create_conflicts(self):
        def proposer(conn):
            return [
                {"type": "Decision", "kind": "fact", "subject": "Budget", "value": "100",
                 "statement": "Budget is 100.", "evidence": [{"source": "tasks.csv", "quote": "T1,Switch checkout to Razorpay"}]},
                {"type": "Decision", "kind": "fact", "subject": "Budget", "value": "500",
                 "statement": "Invented budget.", "evidence": [{"source": "tasks.csv", "quote": "a line nobody wrote"}]},
            ]
        with db.get_db() as conn:
            r = run_extraction(conn, proposer=proposer)
        self.assertEqual((r["conflicting"], r["inferred"], r["verified"]), (0, 1, 1))

    def test_old_database_gets_the_new_columns(self):
        with db.get_db() as c:
            cols = [r["name"] for r in c.execute("PRAGMA table_info(claims)")]
        for col in ("subject", "value", "conflict_group"):
            self.assertIn(col, cols)


if __name__ == "__main__":
    unittest.main()
