"""KNOWBRIDGE: evidence-linked project handover (Round 2 build)."""
import json
import os
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory, session

load_dotenv()

import db  # noqa: E402  (after load_dotenv so DB_PATH from .env is honoured)
from extract import run_extraction  # noqa: E402

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024  # 300 KB per upload

ALLOWED_EXT = {"txt", "md", "csv", "json"}

db.init_db()
with db.get_db() as _c:
    db.seed_demo(_c)  # so a fresh deploy is never empty


# ---------- helpers ----------
def current_role():
    return session.get("role")


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if current_role() not in db.ROLES:
            return jsonify(error="Please sign in first."), 401
        return f(*a, **kw)
    return wrapper


def reviewer_only(f):
    @wraps(f)
    @login_required
    def wrapper(*a, **kw):
        if current_role() != "reviewer":
            return jsonify(error="Only the reviewer can do this."), 403
        return f(*a, **kw)
    return wrapper


def can_open(role, allowed_roles):
    return role in allowed_roles


def claim_rows(conn):
    """All claims with their evidence and the roles allowed on each source."""
    claims = []
    for c in conn.execute("SELECT * FROM claims ORDER BY id"):
        ev = []
        for e in conn.execute(
            "SELECT e.quote, e.quote_found, s.filename, s.allowed_roles FROM evidence e "
            "JOIN sources s ON s.id = e.source_id WHERE e.claim_id=?", (c["id"],)):
            ev.append({"quote": e["quote"], "found": bool(e["quote_found"]),
                       "source": e["filename"], "roles": json.loads(e["allowed_roles"])})
        claims.append({"id": c["id"], "type": c["type"], "text": c["text"],
                       "status": c["status"], "review": c["review_state"], "evidence": ev})
    return claims


def visible_to(role, claim):
    """PERMISSION RULE: a claim is visible only if the role may open EVERY source behind it."""
    return all(can_open(role, e["roles"]) for e in claim["evidence"])


def build_plan(claims):
    """Rule-based Day-1 / Week-1 plan, built only from claims the viewer may see."""
    by = lambda *types: [c for c in claims if c["type"] in types]
    short = lambda c: c["text"].rstrip(".")
    day1, week1 = [], []
    if by("Decision"):
        day1.append("Read these decisions first: " + "; ".join(short(c) for c in by("Decision")[:3]) + ".")
    if by("Contact"):
        day1.append("Get in touch with: " + "; ".join(short(c) for c in by("Contact")[:3]) + ".")
    if by("Owner"):
        day1.append("Know who owns what: " + "; ".join(short(c) for c in by("Owner")[:3]) + ".")
    gaps = [c for c in claims if c["status"] == "missing" or c["type"] in ("Blocker", "Open question", "Next action")]
    for c in gaps[:4]:
        week1.append("Resolve: " + short(c) + ".")
    for c in by("Risk")[:3]:
        week1.append("Keep an eye on this risk: " + short(c) + ".")
    return {"day1": day1, "week1": week1}


# ---------- pages ----------
@app.get("/")
def home():
    return send_from_directory(app.static_folder, "index.html")


# ---------- auth (demo users) ----------
@app.post("/api/login")
def login():
    role = (request.get_json(silent=True) or {}).get("role")
    if role not in db.ROLES:
        return jsonify(error="Unknown role."), 400
    session["role"] = role
    return jsonify(role=role, label=db.ROLES[role])


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/me")
def me():
    r = current_role()
    return jsonify(role=r, label=db.ROLES.get(r), roles=db.ROLES)


# ---------- sources ----------
@app.get("/api/sources")
@login_required
def list_sources():
    role = current_role()
    with db.get_db() as conn:
        out = []
        for s in conn.execute("SELECT id, filename, source_type, allowed_roles, LENGTH(full_text) AS size FROM sources ORDER BY id"):
            allowed = json.loads(s["allowed_roles"])
            if role == "reviewer" or can_open(role, allowed):
                chunks = conn.execute("SELECT COUNT(*) FROM chunks WHERE source_id=?", (s["id"],)).fetchone()[0]
                out.append({"id": s["id"], "filename": s["filename"], "type": s["source_type"],
                            "size": s["size"], "chunks": chunks, "roles": allowed})
    return jsonify(sources=out)


@app.post("/api/sources")
@reviewer_only
def upload_source():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(error="Choose a file to upload."), 400
    name = os.path.basename(f.filename)
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_EXT:
        return jsonify(error="Only .txt, .md, .csv and .json files are supported."), 400
    text = f.read().decode("utf-8", errors="replace").strip()
    if not text:
        return jsonify(error="That file is empty."), 400
    roles = [r for r in request.form.get("roles", "").split(",") if r in db.ROLES]
    with db.get_db() as conn:
        db.add_source(conn, name, text, roles)
    return jsonify(ok=True)


@app.post("/api/demo-data")
@reviewer_only
def load_demo():
    with db.get_db() as conn:
        n = db.seed_demo(conn, reset=True)
    return jsonify(ok=True, loaded=n)


# ---------- extraction and review ----------
@app.post("/api/extract")
@reviewer_only
def extract():
    with db.get_db() as conn:
        result = run_extraction(conn)
    return jsonify(result), (200 if result.get("ok") else 400)


@app.get("/api/claims")
@reviewer_only
def get_claims():
    with db.get_db() as conn:
        return jsonify(claims=claim_rows(conn))


@app.post("/api/claims/<int:cid>")
@reviewer_only
def update_claim(cid):
    data = request.get_json(silent=True) or {}
    with db.get_db() as conn:
        if not conn.execute("SELECT 1 FROM claims WHERE id=?", (cid,)).fetchone():
            return jsonify(error="Claim not found."), 404
        state = data.get("review")
        if state in ("pending", "approved", "rejected"):
            conn.execute("UPDATE claims SET review_state=? WHERE id=?", (state, cid))
        text = (data.get("text") or "").strip()
        if text:
            conn.execute("UPDATE claims SET text=? WHERE id=?", (text[:500], cid))
    return jsonify(ok=True)


# ---------- handover (server-side permission filter) ----------
@app.get("/api/handover")
@login_required
def handover():
    role = current_role()
    with db.get_db() as conn:
        approved = [c for c in claim_rows(conn) if c["review"] == "approved"]
    shown, restricted = [], 0
    for c in approved:
        if visible_to(role, c):
            # Only send what this role may see: evidence from sources it can open (all of them, by the rule).
            shown.append({"id": c["id"], "type": c["type"], "text": c["text"], "status": c["status"],
                          "evidence": [{"source": e["source"], "quote": e["quote"]} for e in c["evidence"]]})
        else:
            restricted += 1  # nothing about the claim is sent, not even its type
    return jsonify(role=role, claims=shown, restricted=restricted, plan=build_plan(shown))


if __name__ == "__main__":
    app.run(debug=True)
