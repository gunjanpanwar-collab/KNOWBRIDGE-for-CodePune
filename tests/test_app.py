"""Run with:  python -m unittest discover -s tests -v   (from the project folder)"""
import os
import sys
import tempfile
import unittest

os.environ["NO_AI"] = "1"
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module  # noqa: E402
import db  # noqa: E402
from extract import run_extraction  # noqa: E402
from verify import find_quote, verify_claim  # noqa: E402


class QuoteCheck(unittest.TestCase):
    TEXT = "Decision: switch to Razorpay.\nStripe does not  support INR payouts."

    def test_exact_and_loose_matches(self):
        self.assertGreaterEqual(find_quote("Stripe does not support INR payouts.", self.TEXT), 0)
        self.assertGreaterEqual(find_quote("stripe DOES not support inr payouts", self.TEXT), 0)
        self.assertGreaterEqual(find_quote("Let\u2019s wait", "Let's wait until Monday"), 0)

    def test_reworded_or_invented_quote_is_rejected(self):
        self.assertEqual(find_quote("Stripe cannot handle rupee payments", self.TEXT), -1)
        self.assertEqual(find_quote("", self.TEXT), -1)

    def test_status_rules(self):
        src = {"a.md": self.TEXT}
        ok = [{"source": "a.md", "quote": "switch to Razorpay"}]
        bad = [{"source": "a.md", "quote": "this was never written"}]
        self.assertEqual(verify_claim("fact", ok, src)[0], "verified")
        self.assertEqual(verify_claim("gap", ok, src)[0], "missing")
        self.assertEqual(verify_claim("fact", bad, src)[0], "inferred")
        self.assertEqual(verify_claim("fact", ok + bad, src)[0], "inferred")
        self.assertIsNone(verify_claim("fact", [], src)[0])
        self.assertIsNone(verify_claim("fact", [{"source": "nope.md", "quote": "x"}], src)[0])


class Flow(unittest.TestCase):
    def setUp(self):
        db.init_db()
        with db.get_db() as c:
            db.seed_demo(c, reset=True)
        self.client = app_module.app.test_client()

    def login(self, role):
        c = app_module.app.test_client()
        c.post("/api/login", json={"role": role})
        return c

    def extract_and_approve_all(self):
        rev = self.login("reviewer")
        r = rev.post("/api/extract").get_json()
        for c in rev.get("/api/claims").get_json()["claims"]:
            rev.post(f"/api/claims/{c['id']}", json={"review": "approved"})
        return r

    def test_extraction_counts_and_nothing_dropped(self):
        r = self.extract_and_approve_all()
        self.assertEqual(r["mode"], "sample")
        self.assertEqual(r["dropped"], 0)
        self.assertEqual(r["inferred"], 0)
        self.assertEqual(r["verified"] + r["missing"], 12)

    def test_invented_quote_is_downgraded_and_unsupported_claim_dropped(self):
        def proposer(conn):
            return [
                {"type": "Decision", "kind": "fact", "statement": "Invented decision.",
                 "evidence": [{"source": "meeting_notes_12.md", "quote": "We will move everything to Mars."}]},
                {"type": "Risk", "kind": "fact", "statement": "No evidence at all.", "evidence": []},
                {"type": "Contact", "kind": "fact", "statement": "Real one.",
                 "evidence": [{"source": "meeting_notes_12.md", "quote": "Dev renews the domain every August."}]},
            ]
        with db.get_db() as conn:
            r = run_extraction(conn, proposer=proposer)
        self.assertEqual((r["verified"], r["inferred"], r["dropped"]), (1, 1, 1))

    def test_permission_filter_hides_restricted_claims(self):
        self.extract_and_approve_all()
        rev = self.login("reviewer").get("/api/handover").get_json()
        dev = self.login("developer").get("/api/handover").get_json()
        mem = self.login("member").get("/api/handover").get_json()
        self.assertEqual(len(rev["claims"]), 12)
        self.assertEqual(rev["restricted"], 0)
        # developer cannot open the private chat; member cannot open chat or GitHub export
        self.assertEqual((len(dev["claims"]), dev["restricted"]), (11, 1))
        self.assertEqual((len(mem["claims"]), mem["restricted"]), (9, 3))
        # restricted content must not be present anywhere in the response body
        body_dev = str(dev).lower()
        self.assertNotIn("sponsor", body_dev)
        body_mem = str(mem).lower()
        for secret in ("sponsor", "reverted", "pr #14", "confirmation email failure", "github_export"):
            self.assertNotIn(secret, body_mem)

    def test_only_approved_claims_reach_handover(self):
        rev = self.login("reviewer")
        rev.post("/api/extract")
        self.assertEqual(len(rev.get("/api/handover").get_json()["claims"]), 0)
        first = rev.get("/api/claims").get_json()["claims"][0]["id"]
        rev.post(f"/api/claims/{first}", json={"review": "approved"})
        self.assertEqual(len(rev.get("/api/handover").get_json()["claims"]), 1)
        rev.post(f"/api/claims/{first}", json={"review": "rejected"})
        self.assertEqual(len(rev.get("/api/handover").get_json()["claims"]), 0)

    def test_access_control_on_endpoints(self):
        self.assertEqual(self.client.get("/api/claims").status_code, 401)
        self.assertEqual(self.client.get("/api/handover").status_code, 401)
        mem = self.login("member")
        self.assertEqual(mem.get("/api/claims").status_code, 403)
        self.assertEqual(mem.post("/api/extract").status_code, 403)
        self.assertEqual(mem.post("/api/demo-data").status_code, 403)

    def test_member_only_sees_sources_they_can_open(self):
        names = [s["filename"] for s in self.login("member").get("/api/sources").get_json()["sources"]]
        self.assertNotIn("leadership_chat_private.txt", names)
        self.assertNotIn("github_export.json", names)
        self.assertEqual(len(self.login("reviewer").get("/api/sources").get_json()["sources"]), 5)

    def test_upload_validation(self):
        import io
        rev = self.login("reviewer")
        bad = rev.post("/api/sources", data={"file": (io.BytesIO(b"x"), "evil.exe")}, content_type="multipart/form-data")
        self.assertEqual(bad.status_code, 400)
        empty = rev.post("/api/sources", data={"file": (io.BytesIO(b"  "), "a.txt")}, content_type="multipart/form-data")
        self.assertEqual(empty.status_code, 400)
        ok = rev.post("/api/sources", data={"file": (io.BytesIO(b"Hello notes"), "a.txt"), "roles": "developer"},
                      content_type="multipart/form-data")
        self.assertEqual(ok.status_code, 200)

    def test_empty_project_extraction_is_handled(self):
        with db.get_db() as c:
            c.execute("DELETE FROM sources")
        r = self.login("reviewer").post("/api/extract")
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
