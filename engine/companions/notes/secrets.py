"""Remove anything that looks like a secret from a note before it is written."""
import re

REMOVED = "[removed]"

_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\b[rsp]k_(?:live|test)_[A-Za-z0-9]{10,}"),  # Stripe secret, restricted and publishable keys
    re.compile(r"\bwhsec_[A-Za-z0-9]{10,}"),  # Stripe webhook secrets
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_\w{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}(?![0-9A-Za-z_-])"),  # Google API keys: 39 characters
    re.compile(r"xox[abprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"eyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]{5,}"),
]
# A password in a connection string, scheme://user:password@host: only the password goes. It can't
# hold a / or an @, so a port and a path (https://host:8080/docs@v2) are never taken for one.
_URL_PASSWORD = re.compile(r"(?i)\b([a-z][a-z0-9+.-]{0,30}://[^\s:/@]*:)([^\s/@]+)(@)")
# The credentials in an Authorization header, with or without a scheme word.
_AUTH_HEADER = re.compile(r"(?i)(\bauthorization[\"']?\s*[:=]\s*[\"']?(?:(?:bearer|basic|token|digest)\s+)?)"
                          r"([^\s\"']{5,}[^\s\"'.,;:)])")  # a full stop or comma after it stays
# "bearer <token>" anywhere: the token must look like one (a digit in it, or 20 characters or more),
# so "the bearer of bad news" and "bearer bonds" stay. A full stop right after it stays too.
_BEARER = re.compile(r"(?i)\b(bearer\s+)((?=[\w.~+/=-]*\d)[\w.~+/=-]{7,}[\w~+/=-]|[\w.~+/=-]{19,}[\w~+/=-])")
# key = value, keeping the key name and separator and replacing only the value. The key may sit
# inside a larger identifier (DB_PASSWORD, dbPassword, STRIPE_SECRET_KEY) and be quoted, as in JSON.
# A suffix must start with _ or -, so plain words like "tokens:" or "secretary:" are left alone. An
# identifier ending in _key or -key (STRIPE_KEY, access-key) counts too; a bare "key:" is prose.
# A quoted value goes whole, spaces and closing quote included.
_KEY_VALUE = re.compile(
    r"(?i)\b([\w-]*(?:password|passwd|pwd|secret|token|api[_-]?key)(?:[_-][\w-]*)?|[a-z0-9]+(?:[_-][a-z0-9]+)*[_-]key)"
    r"([\"']?\s*[:=]\s*)"
    r"(\"[^\"\n]*\"?|'[^'\n]*'?|\S+)")
# "secret:" and "token:" are founder-speak too ("the secret: customers want sync"). For those two bare
# words before a colon, an unquoted value stays only if it is a plain lowercase word. Anything with a
# digit, a symbol or a capital goes, at any length. Trailing punctuation is split off first and kept.
_PROSE_KEYS = ("secret", "token")
_TRAILING = re.compile(r"[.,;:)!?]+$")
_LONG_OPAQUE = re.compile(r"\b[A-Za-z0-9+/_-]{40,}\b")


def _key_value(m: re.Match) -> str:
    key, sep, value = m.group(1), m.group(2), m.group(3)
    if key.lower() in _PROSE_KEYS and sep.strip() == ":" and value[:1] not in "\"'":
        tail = _TRAILING.search(value)
        tail = tail.group(0) if tail else ""
        core = value[:len(value) - len(tail)]
        if not core:
            return m.group(0)
        if core.isascii() and core.isalpha() and core.islower():
            return m.group(0)
        return key + sep + REMOVED + tail
    return key + sep + REMOVED


def redact(text: str) -> str:
    for pattern in _PATTERNS:
        text = pattern.sub(REMOVED, text)
    text = _URL_PASSWORD.sub(lambda m: m.group(1) + REMOVED + m.group(3), text)
    text = _AUTH_HEADER.sub(lambda m: m.group(1) + REMOVED, text)
    text = _BEARER.sub(lambda m: m.group(1) + REMOVED, text)
    text = _KEY_VALUE.sub(_key_value, text)
    return _LONG_OPAQUE.sub(REMOVED, text)
