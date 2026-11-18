"""Gap interview: turns every Missing or Conflicting claim into a specific question for the
departing member. Questions are built by plain code from the claims, not by the AI."""
import json


def _sentence(text):
    text = (text or "").strip()
    return text if text.endswith((".", "?", "!")) else text + "."


def _source_ids(conn, claim_ids):
    ids = set()
    for cid in claim_ids:
        for r in conn.execute("SELECT DISTINCT source_id FROM evidence WHERE claim_id=?", (cid,)):
            ids.add(r["source_id"])
    return sorted(ids)


def generate_questions(conn):
    """Replace all questions with fresh ones. Returns how many were created."""
    conn.execute("DELETE FROM questions")
    claims = conn.execute(
        "SELECT id, type, text, status, conflict_group FROM claims WHERE status IN ('missing','conflicting') ORDER BY id"
    ).fetchall()
    done_groups, n = set(), 0
    for c in claims:
        if c["status"] == "conflicting":
            g = c["conflict_group"]
            if g in done_groups:
                continue
            done_groups.add(g)
            members = [r for r in claims if r["conflict_group"] == g]
            sides = " versus ".join(f"\u201c{m['text'].rstrip('.')}\u201d" for m in members[:3])
            prompt = f"The sources disagree: {sides}. Which one is correct, and what changed?"
            kind, ids = "conflict", [m["id"] for m in members]
        else:
            if c["type"] == "Open question":
                prompt = f"{_sentence(c['text'])} What happened, and why?"
            elif c["type"] in ("Blocker", "Next action"):
                prompt = f"{_sentence(c['text'])} Who should own this, and what is the next step?"
            else:
                prompt = f"{_sentence(c['text'])} What should the next person know about this?"
            kind, ids = "gap", [c["id"]]
        conn.execute(
            "INSERT INTO questions (kind, prompt, about, claim_id, sources) VALUES (?,?,?,?,?)",
            (kind, prompt, c["text"][:90], ids[0], json.dumps(_source_ids(conn, ids))))
        n += 1
    return n
