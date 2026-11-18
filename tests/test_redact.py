"""Sensitive-data masking tests. Run with: python -m unittest discover -s tests -v"""
import os
import sys
import tempfile
import unittest

os.environ["NO_AI"] = "1"
os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "test.db"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db  # noqa: E402
from extract import _build_prompt  # noqa: E402
from redact import describe, redact  # noqa: E402
from verify import find_quote  # noqa: E402


class Masking(unittest.TestCase):
    def test_secret_values_are_masked_but_names_kept(self):
        out, c = redact("razorpay_deploy_key=rzp_test_DEMO1234567890 and password: hunter2")
        self.assertNotIn("DEMO1234567890", out)
        self.assertNotIn("hunter2", out)
        self.assertIn("razorpay_deploy_key=[REDACTED:secret]", out)
        self.assertEqual(c["secret"], 2)

    def test_json_style_secret(self):
        out, _ = redact('{"api_key": "abc123XYZ", "user": "riya"}')
        self.assertNotIn("abc123XYZ", out)
        self.assertIn('"user": "riya"', out)

    def test_plain_key_label_is_masked_but_lookalike_words_are_not(self):
        out, _ = redact("key: abc123 and the deployment key=xyz789")
        self.assertNotIn("abc123", out)
        self.assertNotIn("xyz789", out)
        for harmless in ("monkey=banana", "keyboard=us", "keys=few"):
            self.assertEqual(redact(harmless)[0], harmless, harmless)

    def test_password_is_phrase(self):
        out, _ = redact("the password is hunter2 for the server")
        self.assertNotIn("hunter2", out)

    def test_known_token_formats_without_a_label(self):
        
        self.assertNotIn("AIza", out)
        self.assertNotIn("sk-abcdef", out)
        self.assertEqual(c["key"], 2)

    def test_phone_numbers(self):
        for number in ["+91 98765 43210", "9876543210", "98765 43210", "+1 415 555 2671"]:
            out, c = redact(f"call me on {number} tomorrow")
            self.assertNotIn(number, out, number)
            self.assertEqual(c["phone"], 1, number)

    def test_normal_text_dates_and_ids_are_left_alone(self):
        text = "T1,Switch checkout to Razorpay,Karan,In progress,2026-10-15\nIssue #21 created 2026-09-05 by Riya"
        out, c = redact(text)
        self.assertEqual(out, text)
        self.assertEqual(sum(c.values()), 0)

    def test_masking_twice_changes_nothing(self):
        once, _ = redact("key=abc123 call 9876543210")
        twice, c = redact(once)
        self.assertEqual(once, twice)
        self.assertEqual(sum(c.values()), 0)

    def test_empty_and_none(self):
        self.assertEqual(redact("")[0], "")
        self.assertEqual(redact(None)[0], "")

    def test_describe(self):
        self.assertEqual(describe({"secret": 1, "key": 0, "phone": 2}), "1 secret, 2 phone numbers")


class EndToEnd(unittest.TestCase):
    def setUp(self):
        db.init_db()
        with db.get_db() as c:
            db.seed_demo(c, reset=True)

    def test_demo_key_is_masked_everywhere_it_could_leak(self):
        with db.get_db() as c:
            stored = c.execute("SELECT full_text FROM sources WHERE filename='leadership_chat_private.txt'").fetchone()[0]
            chunks = " ".join(r[0] for r in c.execute("SELECT text FROM chunks"))
            prompt = _build_prompt(c)
        for place in (stored, chunks, prompt):
            self.assertNotIn("DEMO1234567890", place)
            self.assertIn("[REDACTED:secret]", stored)

    def test_masked_source_reports_what_it_masked(self):
        import app as app_module
        cl = app_module.app.test_client()
        cl.post("/api/login", json={"role": "reviewer"})
        rows = {s["filename"]: s for s in cl.get("/api/sources").get_json()["sources"]}
        self.assertEqual(rows["leadership_chat_private.txt"]["masked"]["secret"], 1)
        self.assertEqual(sum(rows["tasks.csv"]["masked"].values()), 0)

    def test_uploaded_file_is_masked_before_storage(self):
        import io
        import app as app_module
        cl = app_module.app.test_client()
        cl.post("/api/login", json={"role": "reviewer"})
        data = {"file": (io.BytesIO(b"Call Meera on +91 98765 43210. password: letmein"), "notes.txt"), "roles": "developer"}
        self.assertEqual(cl.post("/api/sources", data=data, content_type="multipart/form-data").status_code, 200)
        with db.get_db() as c:
            text = c.execute("SELECT full_text FROM sources WHERE filename='notes.txt'").fetchone()[0]
        self.assertNotIn("98765", text)
        self.assertNotIn("letmein", text)
        self.assertIn("Call Meera on", text)

    def test_quotes_containing_the_mask_still_verify(self):
        with db.get_db() as c:
            stored = c.execute("SELECT full_text FROM sources WHERE filename='leadership_chat_private.txt'").fetchone()[0]
        self.assertGreaterEqual(find_quote("razorpay_deploy_key=[REDACTED:secret]", stored), 0)

    def test_old_unmasked_database_is_cleaned_on_startup(self):
        with db.get_db() as c:
            c.execute("UPDATE sources SET redactions=NULL, full_text='key=abc123 ok' WHERE filename='tasks.csv'")
            c.execute("INSERT INTO claims (type, text, status) VALUES ('Risk','old','verified')")
        db.init_db()  # what happens when the app starts
        with db.get_db() as c:
            text = c.execute("SELECT full_text FROM sources WHERE filename='tasks.csv'").fetchone()[0]
            claims = c.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
        self.assertNotIn("abc123", text)
        self.assertEqual(claims, 0)  # stale claims are cleared so they are re-extracted


if __name__ == "__main__":
    unittest.main()
