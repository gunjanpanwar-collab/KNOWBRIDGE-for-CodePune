"""Explainable next-step recommendations. Scores are deterministic; the LLM (optional) only rewords them."""
import json
import re

from . import adapters, chat, llm


def _score(t):
    score, why = 0, []
    if t["status"] == "blocked":
        score += 50
        why.append("it is blocked" + (f" by {t['blocked_by']}" if t["blocked_by"] else ""))
    d = t["days_left"]
    if d is not None:
        if d < 0:
            score += 40 + min(-d, 30)
            why.append(f"it is {-d} day(s) overdue")
        elif d <= 3:
            score += 30
            why.append(f"it is due in {d} day(s)")
        elif d <= 7:
            score += 20
            why.append(f"it is due in {d} days")
    if not t["owner"]:
        score += 15
        why.append("nobody owns it")
    if t["priority"] in ("high", "urgent", "p0", "p1", "critical"):
        score += 10
        why.append("it is high priority")
    return score, why


def _action(t):
    if t["status"] == "blocked":
        who = f" with {t['blocked_by']}" if t["blocked_by"] else ""
        return f"Unblock \"{t['title']}\": confirm the blocker{who} and agree a date to resolve it."
    if not t["owner"]:
        return f"Assign an owner to \"{t['title']}\" and confirm its deadline."
    if t["days_left"] is not None and t["days_left"] < 0:
        return f"Ask {t['owner']} for a new date on \"{t['title']}\", or re-plan it."
    return f"Make progress on \"{t['title']}\" (owner: {t['owner']})."


def recommend(dash, role, limit=5, polish=True):
    recs = []
    for t in dash["blocked"] + dash["pending"]:
        score, why = _score(t)
        if score == 0:
            continue
        recs.append({"task_id": t["id"], "task": t["title"], "action": _action(t), "score": score,
                     "why": "Because " + " and ".join(why) + ".",
                     "evidence": [{"name": t["source"], "url": chat.source_url(t["source"])}]})
    recs.sort(key=lambda r: -r["score"])
    recs = recs[:limit]
    claims = adapters.visible_claims(role)
    for i, r in enumerate(recs, 1):
        r["id"] = f"R{i}"
        ctx = chat.retrieve(r["task"], claims, k=1, min_score=0.2)  # verified background for this task
        r["context"] = [chat.citation(1, c) for c in ctx]
    if polish and recs and llm.configured():
        _polish(recs)
    return recs


def _polish(recs):
    payload = [{"id": r["id"], "action": r["action"], "why": r["why"]} for r in recs]
    raw = llm.complete(
        "Rewrite each action as one clear, friendly sentence a new team member can act on. Keep every fact "
        "unchanged; do not add names, dates or tasks. Reply with JSON only: {\"R1\": \"...\", ...}",
        json.dumps(payload))
    m = re.search(r"\{.*\}", raw or "", re.S)
    try:
        new = json.loads(m.group(0))
    except Exception:
        return
    for r in recs:
        if isinstance(new.get(r["id"]), str) and new[r["id"]].strip():
            r["action"] = new[r["id"]].strip()
