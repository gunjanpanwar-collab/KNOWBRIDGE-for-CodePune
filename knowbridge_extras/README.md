# KnowBridge extras (wired to db.py)

Adds: task dashboard (completed / pending / blocked / deadlines), explainable next-step
recommendations, and a chatbot that answers only from approved claims and links its sources.

## Install (Flask)
1. Copy the `knowbridge_extras/` folder next to your `app.py`.
2. In `app.py`:
   ```python
   from knowbridge_extras import init_app
   init_app(app)
   ```
3. Edit `knowbridge_extras/adapters.py` (3 TODOs): role lookup, sources, approved claims.
4. Add to your main page before `</body>` (adds the chat bubble):
   `<script src="/kb-extras/kb_extras.js" defer></script>`
5. Add a link to `/dashboard` in your nav.

## Optional LLM (otherwise rule-based, still works)
Set `GROQ_API_KEY` (or `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`) on Render.
The LLM only rewords recommendations and phrases chat answers; cited fact numbers are verified in code.

## Endpoints
GET /api/extras/dashboard, GET /api/extras/recommendations, POST /api/extras/chat {question},
GET /kb/source/<name>?quote=..., GET /dashboard. Add `?today=2026-11-19` to fix the date for demos.
