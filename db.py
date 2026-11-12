"""SQLite schema, chunking and demo-data seeding for KNOWBRIDGE."""
import json
import os
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB_PATH = os.environ.get("DB_PATH", str(BASE / "knowbridge.db"))

ROLES = {
    "reviewer": "Reviewer",
    "developer": "Incoming developer",
    "member": "Incoming non-technical member",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY, filename TEXT NOT NULL, source_type TEXT,
    full_text TEXT NOT NULL, allowed_roles TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    idx INTEGER NOT NULL, start INTEGER NOT NULL, text TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY, type TEXT NOT NULL, text TEXT NOT NULL,
    status TEXT NOT NULL, review_state TEXT NOT NULL DEFAULT 'pending');
CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY, claim_id INTEGER NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    quote TEXT NOT NULL, position INTEGER, chunk_idx INTEGER, quote_found INTEGER NOT NULL);
"""

# Demo sources and who may open them (all data is invented).
DEMO_SOURCES = {
    "meeting_notes_12.md": ["reviewer", "developer", "member"],
    "meeting_notes_14.md": ["reviewer", "developer", "member"],
    "tasks.csv": ["reviewer", "developer", "member"],
    "github_export.json": ["reviewer", "developer"],
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


def add_source(conn, filename, text, roles):
    roles = sorted(set(roles) | {"reviewer"})  # reviewer can always open every source
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
    cur = conn.execute(
        "INSERT INTO sources (filename, source_type, full_text, allowed_roles) VALUES (?,?,?,?)",
        (filename, ext, text, json.dumps(roles)),
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
