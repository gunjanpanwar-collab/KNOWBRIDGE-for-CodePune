"""
adapters.py - connects the extras to KNOWBRIDGE's own database (db.py) and login (session["role"]).
Roles are the keys in db.ROLES: "reviewer", "developer", "member".
"""
import json

from flask import session

import db


def current_role():
    """The signed-in role, or None if nobody is signed in (same session key as app.py)."""
    r = session.get("role")
    return r if r in db.ROLES else None


def get_sources():
    """[{"name", "text", "roles"}] for every source (permission filtering happens in visible_sources)."""
    with db.get_db() as conn:
        rows = conn.execute("SELECT filename, full_text, allowed_roles FROM sources ORDER BY id").fetchall()
    return [{"name": r["filename"], "text": r["full_text"], "roles": json.loads(r["allowed_roles"])} for r in rows]


def get_approved_claims():
    """Reviewer-APPROVED claims whose evidence quotes were all found in the source text."""
    out = []
    with db.get_db() as conn:
        for c in conn.execute("SELECT id, text FROM claims WHERE review_state='approved' ORDER BY id").fetchall():
            ev = conn.execute(
                "SELECT e.quote, e.quote_found, s.filename FROM evidence e "
                "JOIN sources s ON s.id = e.source_id WHERE e.claim_id=?", (c["id"],)).fetchall()
            if not ev or not all(e["quote_found"] for e in ev):
                continue  # no evidence, or an unverified quote: not "verified project information"
            evidence = [{"source": e["filename"], "quote": e["quote"]} for e in ev]
            out.append({"id": f"C{c['id']}", "text": c["text"], "quote": " ".join(e["quote"] for e in ev),
                        "sources": sorted({e["source"] for e in evidence}), "evidence": evidence})
    return out


def visible_sources(role):
    return [s for s in get_sources() if role == "reviewer" or role in s["roles"]]


def visible_claims(role):
    """Same rule as app.py: a claim is visible only if the role may open EVERY source behind it."""
    names = {s["name"] for s in visible_sources(role)}
    return [c for c in get_approved_claims() if c["sources"] and set(c["sources"]) <= names]
