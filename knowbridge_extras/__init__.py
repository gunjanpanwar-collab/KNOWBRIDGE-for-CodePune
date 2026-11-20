"""KnowBridge extras: dashboard, next-step recommendations, verified-claims chatbot.

Usage in your Flask app:   from knowbridge_extras import init_app;  init_app(app)
"""
from datetime import date
from html import escape
from urllib.parse import quote as _q  # noqa: F401

from flask import Blueprint, abort, jsonify, request, send_from_directory

from . import adapters, chat, recommender
from .dashboard import build_dashboard

bp = Blueprint("kb_extras", __name__, static_folder="static", static_url_path="/kb-extras")


def _today():
    try:  # ?today=2026-11-19 lets you demo deadlines with fixed dates
        return date.fromisoformat(request.args.get("today", ""))
    except ValueError:
        return date.today()


@bp.get("/api/extras/dashboard")
def api_dashboard():
    role = adapters.current_role()
    if not role:
        return jsonify(error="Please sign in first."), 401
    return jsonify(role=role, **build_dashboard(adapters.visible_sources(role), _today()))


@bp.get("/api/extras/recommendations")
def api_recommendations():
    role = adapters.current_role()
    if not role:
        return jsonify(error="Please sign in first."), 401
    dash = build_dashboard(adapters.visible_sources(role), _today())
    return jsonify(role=role, recommendations=recommender.recommend(dash, role))


@bp.post("/api/extras/chat")
def api_chat():
    role = adapters.current_role()
    if not role:
        return jsonify(error="Please sign in first."), 401
    question = ((request.get_json(silent=True) or {}).get("question") or "").strip()[:500]
    if not question:
        return jsonify(error="Ask a question."), 400
    return jsonify(chat.answer(question, role, _today()))


@bp.get("/kb/source/<path:name>")
def view_source(name):
    src = next((s for s in adapters.visible_sources(adapters.current_role()) if s["name"] == name), None)
    if not src:
        abort(404)  # 404, not 403: don't reveal that a restricted file exists
    text, quote = src["text"], request.args.get("quote", "")
    i = text.lower().find(quote.lower()) if quote else -1
    body = (escape(text) if i < 0 else escape(text[:i]) + "<mark>" + escape(text[i:i + len(quote)])
            + "</mark>" + escape(text[i + len(quote):]))
    return (f"<!doctype html><meta charset=utf-8><title>{escape(name)}</title>"
            "<style>body{font:15px/1.6 system-ui;max-width:760px;margin:2rem auto;padding:0 1rem}"
            "pre{white-space:pre-wrap}mark{background:#ffe08a}</style>"
            f"<p><a href='/'>&larr; Back to KnowBridge</a></p><h2>{escape(name)}</h2><pre>{body}</pre>")


@bp.get("/dashboard")
def dashboard_page():
    return send_from_directory(bp.static_folder, "dashboard.html")


TAG = '<script src="/kb-extras/kb_extras.js" defer></script>'


def init_app(app):
    app.register_blueprint(bp)

    @app.after_request
    def inject_script(resp):  # adds the chat bubble to your home page without editing index.html
        if request.path == "/" and resp.status_code == 200 and resp.mimetype == "text/html":
            resp.direct_passthrough = False
            html = resp.get_data(as_text=True)
            if "kb_extras.js" not in html and "</body>" in html:
                resp.set_data(html.replace("</body>", TAG + "</body>", 1))
        return resp
