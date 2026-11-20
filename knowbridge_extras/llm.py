"""Optional LLM access via any OpenAI-compatible endpoint (Groq, OpenAI, OpenRouter...). No extra packages."""
import json
import os
import urllib.request

BASE = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
KEY = os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY")
MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")


def configured():
    return bool(KEY)


def complete(system, user, timeout=20):
    """Return the model's text, or None on any failure (callers fall back to rule-based output)."""
    if not KEY:
        return None
    body = json.dumps({
        "model": MODEL, "temperature": 0,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(
        BASE.rstrip("/") + "/chat/completions", data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)["choices"][0]["message"]["content"]
    except Exception:
        return None
