"""Turns tasks.csv / GitHub export into completed / pending / blocked / deadline views."""
import csv
import io
import json
import re
from datetime import date, datetime

ALIASES = {
    "id": ("id", "key", "number", "task_id"),
    "title": ("title", "task", "name", "summary", "description"),
    "owner": ("owner", "assignee", "assigned_to", "assigned"),
    "status": ("status", "state"),
    "due": ("due", "due_date", "deadline", "due date", "target_date"),
    "blocked_by": ("blocked_by", "blocker", "depends_on", "dependency"),
    "priority": ("priority",),
}
DONE = {"done", "completed", "complete", "closed", "merged", "resolved", "finished"}
BLOCKED = {"blocked", "on hold", "on_hold", "hold", "waiting", "stuck"}
DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%b %d, %Y", "%d %b %Y", "%B %d, %Y")


def parse_date(raw):
    if not raw:
        return None
    raw = str(raw).strip()
    for fmt in DATE_FORMATS:
        for candidate in (raw, raw[:10]):
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                pass
    return None


def norm_status(raw, labels=(), text=""):
    s = (raw or "").strip().lower()
    if s in DONE:
        return "completed"
    if s in BLOCKED or any("block" in l.lower() for l in labels):
        return "blocked"
    if re.search(r"\bblocked (by|on)\b", (text or "").lower()):
        return "blocked"
    return "pending"


def _pick(row, key):
    for alias in ALIASES[key]:
        if alias in row and str(row[alias]).strip():
            return str(row[alias]).strip()
    return ""


def parse_tasks_csv(text, source):
    rows = csv.DictReader(io.StringIO(text))
    out = []
    for i, raw in enumerate(rows, 1):
        row = {(k or "").strip().lower(): (v or "") for k, v in raw.items()}
        title = _pick(row, "title")
        if not title:
            continue
        out.append({
            "id": _pick(row, "id") or f"T{i}", "title": title, "owner": _pick(row, "owner"),
            "status": norm_status(_pick(row, "status"), text=" ".join(row.values())),
            "due": parse_date(_pick(row, "due")), "priority": _pick(row, "priority").lower(),
            "blocked_by": _pick(row, "blocked_by"), "source": source, "kind": "task",
        })
    return out


def _label_names(item):
    return [(l.get("name", "") if isinstance(l, dict) else str(l)) for l in item.get("labels", []) or []]


def _assignee(item):
    a = item.get("assignee") or (item.get("assignees") or [None])[0]
    return (a.get("login") or a.get("name") or "") if isinstance(a, dict) else (a or "")


def parse_github(text, source):
    data = json.loads(text)
    if isinstance(data, dict):
        items = []
        for key in ("issues", "pull_requests", "pulls", "items"):
            items += data.get(key, []) or []
    else:
        items = data
    out = []
    for it in items:
        if not isinstance(it, dict) or not it.get("title"):
            continue
        labels = _label_names(it)
        merged = bool(it.get("merged") or it.get("merged_at"))
        state = "merged" if merged else str(it.get("state", ""))
        due = it.get("due_date") or it.get("due_on") or (it.get("milestone") or {}).get("due_on")
        is_pr = "pull_request" in it or "merged" in it or "merged_at" in it or "pr" in str(it.get("type", "")).lower()
        out.append({
            "id": f"#{it['number']}" if it.get("number") else it.get("id", ""),
            "title": it["title"], "owner": _assignee(it),
            "status": norm_status(state, labels, it.get("body") or ""),
            "due": parse_date(due), "priority": "high" if any("high" in l.lower() or "urgent" in l.lower() for l in labels) else "",
            "blocked_by": "", "source": source, "kind": "pull request" if is_pr else "issue",
        })
    return out


def build_dashboard(sources, today=None):
    today = today or date.today()
    tasks, warnings = [], []
    for s in sources:
        name = s["name"].lower()
        try:
            if name.endswith(".csv"):
                tasks += parse_tasks_csv(s["text"], s["name"])
            elif name.endswith(".json"):
                tasks += parse_github(s["text"], s["name"])
        except Exception as e:  # one bad file must not break the dashboard
            warnings.append(f"Could not read {s['name']}: {e}")

    def public(t):
        d = t["due"]
        return {**t, "due": d.isoformat() if d else None, "days_left": (d - today).days if d else None}

    items = [public(t) for t in tasks]
    pick = lambda st: [t for t in items if t["status"] == st]
    open_items = [t for t in items if t["status"] != "completed" and t["due"]]
    deadlines = sorted(open_items, key=lambda t: t["due"])
    for t in deadlines:
        t["bucket"] = "overdue" if t["days_left"] < 0 else "due soon" if t["days_left"] <= 7 else "upcoming"
    return {
        "as_of": today.isoformat(),
        "counts": {"total": len(items), "completed": len(pick("completed")), "pending": len(pick("pending")),
                   "blocked": len(pick("blocked")), "overdue": sum(t["bucket"] == "overdue" for t in deadlines)},
        "completed": pick("completed"), "pending": pick("pending"), "blocked": pick("blocked"),
        "deadlines": deadlines, "warnings": warnings,
    }
