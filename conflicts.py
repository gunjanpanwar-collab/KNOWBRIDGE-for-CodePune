"""Conflict detection: plain Python that decides when two claims disagree.

The AI tags each fact claim with a short `subject` (what it is about, e.g. "Razorpay switch
deadline") and a `value` (e.g. "30 September"). This code, not the AI, then compares them.
Two claims conflict when they are about the same subject but give different values.
"""
import re

STOP = {"the", "a", "an", "of", "for", "to", "is", "are", "was", "were", "and", "in", "on", "s",
        "by", "with", "this", "that", "current", "new", "final"}

MONTHS = {m: i for i, names in enumerate(
    [("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"), ("may",),
     ("jun", "june"), ("jul", "july"), ("aug", "august"), ("sep", "sept", "september"),
     ("oct", "october"), ("nov", "november"), ("dec", "december")], start=1) for m in names}

_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_SLASH = re.compile(r"^(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})$")  # day/month/year
_DM = re.compile(r"^(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]{3,9})\.?(?:,?\s+(\d{4}))?$")
_MD = re.compile(r"^([a-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?$")


def subject_tokens(subject):
    toks = re.findall(r"[a-z0-9]+", (subject or "").lower())
    return {t[:-1] if len(t) > 3 and t.endswith("s") else t for t in toks if t not in STOP}


def same_subject(a, b):
    ta, tb = subject_tokens(a), subject_tokens(b)
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= 0.6


def parse_date(value):
    """Return (year or None, month, day) if the WHOLE value is a date, else None."""
    v = (value or "").strip().lower().rstrip(".")
    m = _ISO.match(v)
    if m:
        return int(m[1]), int(m[2]), int(m[3])
    m = _SLASH.match(v)
    if m:
        year = int(m[3]) + (2000 if int(m[3]) < 100 else 0)
        return year, int(m[2]), int(m[1])
    m = _DM.match(v)
    if m and m[2] in MONTHS:
        return (int(m[3]) if m[3] else None), MONTHS[m[2]], int(m[1])
    m = _MD.match(v)
    if m and m[1] in MONTHS:
        return (int(m[3]) if m[3] else None), MONTHS[m[1]], int(m[2])
    return None


def _norm_value(v):
    return re.sub(r"[^a-z0-9]+", " ", (v or "").lower()).strip()


def values_differ(a, b):
    da, db = parse_date(a), parse_date(b)
    if da and db:
        same_day = da[1:] == db[1:]
        same_year = da[0] is None or db[0] is None or da[0] == db[0]
        return not (same_day and same_year)
    na, nb = _norm_value(a), _norm_value(b)
    if not na or not nb:
        return False
    return not (na == nb or na in nb or nb in na)


def find_conflicts(items):
    """items: list of {"subject": str, "value": str}. Returns a list of groups, each a list of
    indexes into `items` (at least two) whose claims disagree about the same subject."""
    n = len(items)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            a, b = items[i], items[j]
            if a.get("subject") and b.get("subject") and a.get("value") and b.get("value") \
                    and same_subject(a["subject"], b["subject"]) and values_differ(a["value"], b["value"]):
                parent[find(i)] = find(j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return [g for g in groups.values() if len(g) >= 2]
