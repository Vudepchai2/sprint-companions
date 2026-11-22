"""Remove anything that looks like a secret from a note before it is written."""
import re

REMOVED = "[removed]"

_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_\w{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"xox[abprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"eyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]{5,}"),
]
# key = value, keeping the key name and separator and replacing only the value. The key may sit
# inside a larger identifier (DB_PASSWORD, dbPassword, STRIPE_SECRET_KEY) and be quoted, as in JSON.
# A suffix must start with _ or -, so plain words like "tokens:" or "secretary:" are left alone.
# A quoted value goes whole, spaces and closing quote included.
_KEY_VALUE = re.compile(
    r"(?i)\b([\w-]*(?:password|passwd|pwd|secret|token|api[_-]?key)(?:[_-][\w-]*)?)"
    r"([\"']?\s*[:=]\s*)"
    r"(\"[^\"\n]*\"?|'[^'\n]*'?|\S+)")
_LONG_OPAQUE = re.compile(r"\b[A-Za-z0-9+/_-]{40,}\b")


def redact(text: str) -> str:
    for pattern in _PATTERNS:
        text = pattern.sub(REMOVED, text)
    text = _KEY_VALUE.sub(lambda m: m.group(1) + m.group(2) + REMOVED, text)
    return _LONG_OPAQUE.sub(REMOVED, text)
