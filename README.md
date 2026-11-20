# KNOWBRIDGE

**Turn a departing teammate's scattered project files into a handover a new person can trust and act on.**

**Live demo:** https://knowbridge-for-codepune-crnr.onrender.com
*(Free hosting sleeps when idle, so the first load can take about a minute. All demo data in `demo_data/` is invented.)*

Built for the CodePune hackathon problem: *build a system that converts scattered project activity into a usable handover when a team member leaves.*

> **The AI proposes. Python code verifies every quote. A human approves. The server shows each role only what it may open.**

---

## The problem

When someone leaves a project, what they know is spread across meeting notes, task lists, code exports and private chats. The new person has to dig through all of it, and usually misses what matters most: why a decision was made, who owns what, what is blocked, and what nobody wrote down.

Generic AI summaries make this worse. They sound confident, can invent details, and show everyone everything, including files that should stay private.

## What KnowBridge does

```
flowchart LR
    A[Project files] --> B[AI proposes claims]
    B --> C[Code verifies quotes]
    C --> D[Reviewer approves]
    D --> E[Role-aware handover]
    D --> F[Dashboard and next steps]
    D --> G[Verified chatbot]
```

| What it gives you |
|---|---|
| **Evidence-linked claims** | Every claim carries an exact quote from a named source file |
| **Code-verified quotes** | Quotes are checked against the source text. Invented quotes are never shown as verified |
| **Human review** | Nothing reaches a new hire until a reviewer approves, edits or rejects it |
| **Role-based access** | A claim is sent only if the viewer's role may open every source behind it |
| **Day-1 / Week-1 plan** | A starter plan built only from the claims the viewer may see |
| **Project dashboard** | Completed, pending, blocked and overdue work, plus deadlines |
| **Next-step recommendations** | Prioritised actions, each with a plain-English reason and source link |
| **Verified chatbot** | Answers only from approved information and links its sources |

---

## Features in detail

### 1. Evidence-linked, verified claims
Gemini returns claims as JSON, each with an exact quote. `verify.py` then checks that every quote exists in the source it cites:
- **Verified** (or **Missing** for a gap): the quote was found.
- **Inferred**: the quote was not found, so it is clearly marked and not treated as verified.
- **Dropped**: no evidence at all, so it never appears.

If the AI is unavailable (quota, 503, no key), the app falls back to a saved sample extraction and says so on screen.

### 2. Human-in-the-loop review
The reviewer approves, edits or rejects each claim. Only approved claims reach the handover, the dashboard recommendations and the chatbot.

### 3. Permissions enforced on the server
Each source lists which roles may open it: **Reviewer**, **Incoming developer** and **Incoming non-technical member**. Restricted claims are replaced by a placeholder, and none of their content is sent to the browser. The same rule applies to the dashboard, recommendations, chatbot and source links.

### 4. Project dashboard (`/dashboard`)
Reads the task list and the GitHub export and shows:
- completed, pending and blocked work
- deadlines grouped as **overdue**, **due soon** and **upcoming**
- only the data the signed-in role may open

### 5. Explainable next-step recommendations
Tasks are scored by transparent rules: blocked, overdue, due within days, no owner, high priority. Each recommendation shows **why** it was suggested and links to its source. Where a verified claim matches the task, it is attached as background. An optional LLM can reword the text, but it cannot change the facts.

### 6. Verified chatbot ("Ask KnowBridge")
Ask in plain language: *"Why did we choose this vendor?"* or *"What is blocked?"* The chatbot answers only from approved claims the user may see, plus task status. Every answer carries source links, and a link opens the source file with the supporting quote highlighted. If the answer is not in the verified record, it says so instead of guessing.

---

## How KnowBridge is different

| Typical approach | KnowBridge |
|---|---|
| AI summarises files and you trust it | AI **proposes**, code **verifies** each quote, a human **approves** |
| Summaries without sources | Every claim and chatbot answer links to its source, with the quote highlighted |
| A chatbot that answers from everything it has read | Answers **only** from approved, verified claims and refuses otherwise |
| Everyone sees the same output | Each role sees only what it may open. Restricted files return "not found", so their existence is not revealed |
| A wiki or document dump | Extracts decisions, owners, blockers, risks and open questions, then builds a Day-1 / Week-1 plan |
| Opaque AI suggestions | Next steps come from visible rules with a "because..." reason |
| Silent about missing information | Gaps are surfaced as **Missing** claims for the reviewer |

---

## Try it in two minutes

1. Sign in as **Reviewer**, click **Load demo data**, then **Extract claims**.
2. Approve a few claims in the **Review** tab.
3. Open **Handover** to see the Day-1 and Week-1 plan.
4. Open `/dashboard?today=2026-11-19` for task status, deadlines and next steps. The `today` parameter fixes the date so the demo deadlines look right.
5. Click **Ask KnowBridge** and try *"What is blocked?"* or a question about a decision. Click a source link to see the highlighted quote.
6. Sign out and sign in as **Incoming non-technical member**. Ask about the private leadership chat. KnowBridge says it cannot find it.

## Run it locally

```
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
pip install -r requirements.txt
copy .env.example .env            # then put your key in .env
python app.py                     # open http://127.0.0.1:5000
```

Environment variables (see `.env.example`):

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Key for live claim extraction |
| `GEMINI_MODEL` | Gemini model name |
| `SECRET_KEY` | Signs login sessions. Use long random text in production |
| `NO_AI` | Set to `1` to skip the live AI call and use the saved sample extraction |
| `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` | Optional: smoother wording for chat answers and recommendations |

Never commit `.env`.

## How it works

1. **Sources.** Uploaded `.txt`, `.md`, `.csv` and `.json` files (up to 300 KB) are stored and split into numbered chunks. Each source lists which roles may open it.
2. **Extract (`extract.py`).** Gemini returns claims as JSON, each with an exact quote.
3. **Verify (`verify.py`).** Code checks every quote against its cited source.
4. **Review.** The reviewer approves, edits or rejects each claim.
5. **Handover (`app.py`).** A claim is sent only if the viewer's role may open every source behind it. The Day-1 and Week-1 plan is built from the claims the viewer may see.
6. **Extras (`knowbridge_extras/`).** The dashboard, recommendations and chatbot read the same approved claims and the same permission rule.

## Project structure

```
app.py                 Flask app: auth, sources, extraction, review, handover
db.py                  SQLite schema, chunking, demo-data seeding
extract.py             Gemini claim extraction with fallback
verify.py              Quote verification against source text
knowbridge_extras/     Dashboard, recommendations and verified chatbot
  adapters.py          Connects the extras to the database and login
  dashboard.py         Task parsing and dashboard data
  recommender.py       Explainable next-step scoring
  chat.py              Retrieval-based chatbot over approved claims
  llm.py               Optional LLM wording (rule-based without a key)
  static/              Dashboard page and chat widget
demo_data/             Invented sample project files
static/                Main web interface
tests/                 Unit tests
```

## API overview

| Endpoint | Description |
|---|---|
| `POST /api/login`, `POST /api/logout`, `GET /api/me` | Demo role sign-in |
| `GET /api/sources`, `POST /api/sources` | List sources (role-filtered) and upload (reviewer) |
| `POST /api/extract` | Run extraction (reviewer) |
| `GET /api/claims`, `POST /api/claims/<id>` | Review claims (reviewer) |
| `GET /api/handover` | Role-filtered approved claims and plan |
| `GET /api/extras/dashboard` | Task status and deadlines |
| `GET /api/extras/recommendations` | Explainable next steps |
| `POST /api/extras/chat` | Verified chatbot |
| `GET /kb/source/<name>?quote=...` | Source viewer with highlighted quote |

## Tests

```
python -m unittest discover -s tests -v
```

Covers quote matching, invented quotes, dropped claims, the permission filter and endpoint access control.

## Deploy (Render, free tier)

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Environment variables: `GEMINI_API_KEY`, `GEMINI_MODEL` (optional), `SECRET_KEY` (any long random text)
- The free tier resets the database on restart. Demo data is re-loaded automatically.

## Roadmap

Gap interview with the leaving member, conflict detection with sensitive-data redaction and an access log, and version history with acknowledgement and more source types.

## Team

Built at CodePune hackathon by **Gauri** ([@GaurisharmaO](https://github.com/GaurisharmaO)) , **Gunjan Panwar** ([@gunjanpanwar-collab](https://github.com/gunjanpanwar-collab)), **Stuti** ([@Stuti-2009](https://github.com/Stuti-2009)) and  **vaibhavi lamba**.

