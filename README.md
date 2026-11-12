# KNOWBRIDGE

Turns a project's scattered files into a reviewable, evidence-linked handover.
The AI **proposes** claims, Python code **verifies** every quote, a human **approves**,
and the server shows each role only what it may open.

All demo data in `demo_data/` is invented.

## Run it locally

```
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
pip install -r requirements.txt
copy .env.example .env            # then put your key in .env
python app.py                     # open http://127.0.0.1:5000
```

Sign in as **Reviewer**, click **Load demo data**, then **Extract claims**, review and approve
claims, then sign in as the other roles to see what each may open.

## How it works

1. **Sources.** Uploaded `.txt`, `.md`, `.csv`, `.json` files are stored and split into numbered chunks.
   Each source lists which roles may open it.
2. **Extract (`extract.py`).** Gemini returns claims as JSON, each with an exact quote.
   If the AI is unavailable (quota, 503, no key), the app uses a saved sample extraction and says so on screen.
3. **Verify (`verify.py`).** Code checks that every quote exists in its cited source.
   Found = Verified (or Missing for a gap). Not found = Inferred. No evidence = dropped.
4. **Review.** The reviewer approves, edits or rejects each claim. Only approved claims reach the handover.
5. **Handover (`app.py`).** A claim is sent only if the viewer's role may open EVERY source behind it.
   Restricted claims are replaced by a placeholder, and none of their content is sent to the browser.
   The Day-1 and Week-1 plan is built from the claims the viewer may see.

## Tests

```
python -m unittest discover -s tests -v
```

Covers quote matching, invented quotes, dropped claims, the permission filter and endpoint access control.

## Deploy (Render, free tier)

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Environment variables: `GEMINI_API_KEY`, `GEMINI_MODEL` (optional), `SECRET_KEY` (any long random text)
- Never commit `.env`. The free tier resets the database on restart; demo data is re-loaded automatically.

## Known limitations (Round 2)

- Demo sign-in only: three fixed roles, no passwords.
- Status **Conflicting**, the gap interview, sensitive-data masking and the access log are not built yet.
- No version history or acknowledgement yet.
- Extraction quality depends on the AI; that is why every claim is checked and human-approved.
- Free-tier AI limits can cause the saved-sample fallback to be used.

## Planned for Round 3

Gap interview, conflict detection with sensitive-data redaction and an access log,
and version history with acknowledgement and more source types.
