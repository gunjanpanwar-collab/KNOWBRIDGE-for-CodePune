"""Sensitive-data masking.

Runs on every source BEFORE it is stored, chunked, sent to the AI or shown to anyone
(including the reviewer). Secrets and phone numbers are replaced by a placeholder such as
[REDACTED:secret], so they cannot leak through claims, quotes or the AI prompt.
"""
import re

MASK = "[REDACTED:{}]"

# name = value  (or "name": "value") where the NAME suggests a secret
_KV = re.compile(
    r"""(?ix)
    \b([\w.-]*(?:api[_-]?key|apikey|secret|token|passw(?:or)?d|passcode|pwd|
        private[_-]?key|access[_-]?key|deploy[_-]?key|credentials?|
        (?<![A-Za-z0-9])key(?![A-Za-z0-9]))[\w.-]*)
    (["']?)(\s*[:=]\s*)(["']?)([^\s"',;]+)
    """)
# "the password is hunter2"
_SAYS = re.compile(r"(?i)\b(password|passcode|pin)(\s+is\s+)(\S+)")
# well-known token formats
_TOKENS = re.compile(
    r"\b(?:rzp_(?:test|live)_[A-Za-z0-9]{6,}|sk-[A-Za-z0-9_\-]{16,}|AIza[0-9A-Za-z_\-]{20,}|"
    r"gh[pousr]_[A-Za-z0-9]{20,}|xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|"
    r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})")
# phone numbers: Indian mobiles (with or without +91 / spaces) and international +CC numbers
_PHONES = [
    re.compile(r"(?<![\w.])(?:\+91[\s-]?|0)?[6-9]\d{9}(?!\d)"),
    re.compile(r"(?<![\w.])(?:\+91[\s-]?)?[6-9]\d{4}[\s-]\d{5}(?!\d)"),
    re.compile(r"(?<![\w.])\+\d{1,3}[\s-]?\(?\d{1,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}(?!\d)"),
]


def _is_masked(s):
    return s.startswith("[REDACTED")


def redact(text):
    """Return (masked_text, counts). counts has the keys secret, key and phone."""
    counts = {"secret": 0, "key": 0, "phone": 0}

    def kv(m):
        name, q1, sep, q2, value = m.groups()
        if _is_masked(value):
            return m.group(0)
        counts["secret"] += 1
        return f"{name}{q1}{sep}{q2}{MASK.format('secret')}"

    def says(m):
        if _is_masked(m.group(3)):
            return m.group(0)
        counts["secret"] += 1
        return f"{m.group(1)}{m.group(2)}{MASK.format('secret')}"

    def token(m):
        counts["key"] += 1
        return MASK.format("key")

    def phone(m):
        counts["phone"] += 1
        return MASK.format("phone")

    text = _KV.sub(kv, text or "")
    text = _SAYS.sub(says, text)
    text = _TOKENS.sub(token, text)
    for pat in _PHONES:
        text = pat.sub(phone, text)
    return text, counts


def describe(counts):
    """Short human-readable summary, e.g. '1 secret, 2 phone numbers'."""
    names = {"secret": ("secret", "secrets"), "key": ("API key", "API keys"),
             "phone": ("phone number", "phone numbers")}
    parts = [f"{n} {names[k][0] if n == 1 else names[k][1]}" for k, n in counts.items() if n]
    return ", ".join(parts)
