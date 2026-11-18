"""SQLite schema, chunking and demo-data seeding for KNOWBRIDGE."""
import json
import os
import sqlite3
from pathlib import Path

from redact import redact

BASE = Path(__file__).resolve().parent
DB_PATH = os.environ.get("DB_PATH", str(BASE / "knowbridge.db"))

ROLES = {
    "reviewer": "Reviewer",
    "developer": "Incoming developer",
    "member": "Incoming non-technical member",
    "leaver": "Departing member",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY, filename TEXT NOT NULL, source_type TEXT,
    full_text TEXT NOT NULL, allowed_roles TEXT NOT NULL, redactions TEXT);
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    idx INTEGER NOT NULL, start INTEGER NOT NULL, text TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY, type TEXT NOT NULL, text TEXT NOT NULL,
    status TEXT NOT NULL, review_state TEXT NOT NULL DEFAULT 'pending',
    subject TEXT, value TEXT, conflict_group INTEGER, question_id INTEGER, inherit TEXT);
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY, kind TEXT NOT NULL, prompt TEXT NOT NULL, about TEXT NOT NULL,
    claim_id INTEGER NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    sources TEXT NOT NULL, answer TEXT, answered_at TEXT, answer_claim_id INTEGER);
CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY, claim_id INTEGER NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    quote TEXT NOT NULL, position INTEGER, chunk_idx INTEGER, quote_found INTEGER NOT NULL);
"""

# Demo sources and who may open them (all data is invented).
DEMO_SOURCES = {
    "meeting_notes_12.md": ["reviewer", "developer", "member", "leaver"],
    "meeting_notes_14.md": ["reviewer", "developer", "member", "leaver"],
    "tasks.csv": ["reviewer", "developer", "member", "leaver"],
    "github_export.json": ["reviewer", "developer", "leaver"],
    "leadership_chat_private.txt": ["reviewer"],
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA)
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(sources)")]
        if "redactions" not in cols:  # databases created before Round 3
            conn.execute("ALTER TABLE sources ADD COLUMN redactions TEXT")
        ccols = [r["name"] for r in conn.execute("PRAGMA table_info(claims)")]
        for col, kind in (("subject", "TEXT"), ("value", "TEXT"), ("conflict_group", "INTEGER"),
                          ("question_id", "INTEGER"), ("inherit", "TEXT")):
            if col not in ccols:  # databases created before conflict detection
                conn.execute(f"ALTER TABLE claims ADD COLUMN {col} {kind}")
        redact_existing(conn)
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO users (name, role) VALUES (?, ?)",
                [("Demo Reviewer", "reviewer"), ("Demo Developer", "developer"),
                 ("Demo Member", "member")],
            )


def chunk_text(text, size=1200):
    """Split text into numbered chunks on line boundaries. Returns (idx, start, text)."""
    chunks, buf, start, pos = [], "", 0, 0
    for line in text.splitlines(keepends=True):
        if buf and len(buf) + len(line) > size:
            chunks.append((len(chunks), start, buf))
            buf, start = "", pos
        buf += line
        pos += len(line)
    if buf:
        chunks.append((len(chunks), start, buf))
    return chunks or [(0, 0, text)]


def redact_existing(conn):
    """Safety net: mask any source stored before masking existed, rebuild its chunks,
    and clear old claims (their quotes may no longer match the masked text)."""
    changed = False
    for r in conn.execute("SELECT id, full_text FROM sources WHERE redactions IS NULL").fetchall():
        text, counts = redact(r["full_text"])
        conn.execute("UPDATE sources SET full_text=?, redactions=? WHERE id=?",
                     (text, json.dumps(counts), r["id"]))
        conn.execute("DELETE FROM chunks WHERE source_id=?", (r["id"],))
        for idx, start, chunk in chunk_text(text):
            conn.execute("INSERT INTO chunks (source_id, idx, start, text) VALUES (?,?,?,?)",
                         (r["id"], idx, start, chunk))
        changed = True
    if changed:
        conn.execute("DELETE FROM claims")


def add_source(conn, filename, text, roles):
    roles = sorted(set(roles) | {"reviewer"})  # reviewer can always open every source
    text, counts = redact(text)  # mask secrets and phone numbers BEFORE storing
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
    cur = conn.execute(
        "INSERT INTO sources (filename, source_type, full_text, allowed_roles, redactions) VALUES (?,?,?,?,?)",
        (filename, ext, text, json.dumps(roles), json.dumps(counts)),
    )
    sid = cur.lastrowid
    for idx, start, chunk in chunk_text(text):
        conn.execute(
            "INSERT INTO chunks (source_id, idx, start, text) VALUES (?,?,?,?)",
            (sid, idx, start, chunk),
        )
    return sid


def seed_demo(conn, reset=False):
    if reset:
        conn.execute("DELETE FROM claims")
        conn.execute("DELETE FROM sources")
    if conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] > 0:
        return 0
    n = 0
    for filename, roles in DEMO_SOURCES.items():
        path = BASE / "demo_data" / filename
        if path.exists():
            add_source(conn, filename, path.read_text(encoding="utf-8"), roles)
            n += 1
    return n
