"""AI claim extraction (Gemini) with an honest fallback to a saved sample.

The AI only PROPOSES claims. verify.py checks every quote afterwards.
"""
import json
import os
import re
import time
from pathlib import Path

from verify import verify_claim

BASE = Path(__file__).resolve().parent
TYPES = {"Decision", "Owner", "Risk", "Dependency", "Blocker", "Open question",
         "Next action", "Contact"}

PROMPT = """You extract project-handover knowledge from source files.
Return ONLY a JSON array. Each item must have exactly these keys:
  "type": one of Decision, Owner, Risk, Dependency, Blocker, Open question, Next action, Contact
  "kind": "fact" for something the sources state, or "gap" for something expected but missing
          (a task with no owner, a decision or revert with no recorded reason, an unresolved issue)
  "statement": one short sentence in plain English
  "evidence": a list of {"source": "<exact filename>", "quote": "<text copied from that file>"}

Rules:
- Every quote MUST be copied exactly, character for character, from the named file. Never paraphrase a quote.
- Use short quotes (one line or one sentence). Every claim needs at least one quote.
- Do not invent anything. If you are unsure, leave the claim out.
- Never put passwords, API keys or phone numbers in a statement or quote.
- Prefer 10 to 25 useful claims over a long list.

SOURCES:
"""


def _build_prompt(conn):
    parts = []
    for s in conn.execute("SELECT id, filename FROM sources ORDER BY id"):
        parts.append(f"=== FILE: {s['filename']} ===")
        for c in conn.execute("SELECT idx, text FROM chunks WHERE source_id=? ORDER BY idx", (s["id"],)):
            parts.append(f"[chunk {c['idx']}]\n{c['text']}")
    return PROMPT + "\n".join(parts)


def _parse_json(text):
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    data = json.loads(text)
    if isinstance(data, dict):
        data = data.get("claims", [])
    if not isinstance(data, list):
        raise ValueError("model did not return a JSON list")
    return data


def call_gemini(prompt, attempts=2):
    """Call Gemini and return a list of proposed claims. Raises on failure."""
    from google import genai
    from google.genai import types

    client = genai.Client()  # reads GEMINI_API_KEY from the environment
    model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    last = None
    for i in range(attempts):
        try:
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            return _parse_json(resp.text)
        except Exception as e:  # network, quota, 503, bad JSON
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"Gemini failed: {str(last)[:150]}")


def load_sample():
    return json.loads((BASE / "sample_claims.json").read_text(encoding="utf-8"))


def run_extraction(conn, proposer=None):
    """Replace all claims with freshly proposed and verified ones. Returns a summary dict."""
    sources = {r["filename"]: dict(r) for r in conn.execute(
        "SELECT id, filename, full_text FROM sources")}
    if not sources:
        return {"ok": False, "error": "Upload at least one source first."}

    mode, note, proposed = "ai", "", None
    use_ai = os.environ.get("NO_AI") != "1" and os.environ.get("GEMINI_API_KEY")
    if proposer is not None:
        proposed = proposer(conn)
    elif use_ai:
        try:
            proposed = call_gemini(_build_prompt(conn))
        except Exception as e:
            note = f"The AI was unavailable ({e}). Showing the saved sample extraction instead."
    else:
        note = "No AI key set or NO_AI=1. Showing the saved sample extraction instead."
    if proposed is None:
        mode, proposed = "sample", load_sample()

    texts = {name: s["full_text"] for name, s in sources.items()}
    conn.execute("DELETE FROM claims")
    counts = {"verified": 0, "inferred": 0, "missing": 0, "dropped": 0}
    for item in proposed:
        if not isinstance(item, dict):
            counts["dropped"] += 1
            continue
        ctype = item.get("type")
        statement = str(item.get("statement", "")).strip()
        if ctype not in TYPES or not statement:
            counts["dropped"] += 1
            continue
        status, checked = verify_claim(item.get("kind"), item.get("evidence"), texts)
        if status is None:  # no usable evidence: drop it, never show an unsupported claim
            counts["dropped"] += 1
            continue
        cur = conn.execute("INSERT INTO claims (type, text, status) VALUES (?,?,?)",
                           (ctype, statement, status))
        for ev in checked:
            sid = sources[ev["source"]]["id"]
            chunk = None
            if ev["found"]:
                row = conn.execute(
                    "SELECT idx FROM chunks WHERE source_id=? AND start<=? ORDER BY start DESC LIMIT 1",
                    (sid, ev["position"])).fetchone()
                chunk = row["idx"] if row else None
            conn.execute(
                "INSERT INTO evidence (claim_id, source_id, quote, position, chunk_idx, quote_found)"
                " VALUES (?,?,?,?,?,?)",
                (cur.lastrowid, sid, ev["quote"], ev["position"], chunk, 1 if ev["found"] else 0))
        counts[status] += 1
    return {"ok": True, "mode": mode, "note": note, **counts}
