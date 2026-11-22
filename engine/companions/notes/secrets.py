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
# Same match as (?i)\b(password|...|api[_-]?key)\b\s*[:=]\s*\S+, with the separator grouped
# so the key name and separator stay and only the value goes.
_KEY_VALUE = re.compile(r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key)\b(\s*[:=]\s*)\S+")
_LONG_OPAQUE = re.compile(r"\b[A-Za-z0-9+/_-]{40,}\b")


def redact(text: str) -> str:
    for pattern in _PATTERNS:
        text = pattern.sub(REMOVED, text)
    text = _KEY_VALUE.sub(lambda m: m.group(1) + m.group(2) + REMOVED, text)
    return _LONG_OPAQUE.sub(REMOVED, text)
