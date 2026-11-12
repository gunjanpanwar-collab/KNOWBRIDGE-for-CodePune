"""Quote verification: the core trust check.

The AI only proposes claims. This code decides whether each quote really
exists in the cited source, and sets the claim status from that result.
"""
import re

_TRANS = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u00a0": " ",
})


def _norm(s):
    # Same length as the input, so positions stay valid for the original text.
    return s.translate(_TRANS)


def find_quote(quote, text):
    """Return the start position of `quote` inside `text`, or -1 if it is not there.

    Matching ignores case, differences in whitespace, and curly versus straight quotes.
    It does NOT accept reworded text: every word of the quote must appear in order.
    """
    if not quote or not text:
        return -1
    words = _norm(quote).strip().strip("\"'").split()
    if not words:
        return -1
    pattern = r"\s+".join(re.escape(w) for w in words)
    m = re.search(pattern, _norm(text), re.IGNORECASE)
    return m.start() if m else -1


def verify_claim(kind, evidence, sources_by_name):
    """Check every quote of one claim.

    evidence: list of {"source": filename, "quote": text}
    sources_by_name: {filename: full_text}
    Returns (status, checked) where checked is a list of
    {"source", "quote", "position", "found"}. status is one of:
      verified - every quote was found in its source
      missing  - a gap (for example a task with no owner) whose evidence was found
      inferred - at least one quote could not be found, so a human must confirm it
    Returns (None, []) when the claim has no usable evidence, so the caller drops it.
    """
    checked = []
    for ev in evidence or []:
        name, quote = ev.get("source"), ev.get("quote")
        if name not in sources_by_name or not quote:
            continue
        pos = find_quote(quote, sources_by_name[name])
        checked.append({"source": name, "quote": quote, "position": pos, "found": pos >= 0})
    if not checked:
        return None, []
    if not all(c["found"] for c in checked):
        return "inferred", checked
    return ("missing" if kind == "gap" else "verified"), checked
