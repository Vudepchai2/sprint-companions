"""The quiet-notes inbox: one JSONL file per UTC day under notes/inbox, plus notes/state.json.

Ids start with the UTC timestamp, so ordering and "digested through" are plain string comparisons.
"""
import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path

from ..home import notes_dir, read_settings

MAX_TEXT = 4000
KEEP_DAYS = 30
_DAY_FILE = re.compile(r"(\d{4}-\d{2}-\d{2})\.jsonl")
_FIELDS = ("id", "at", "session", "cwd", "text")


def _inbox() -> Path:
    return notes_dir() / "inbox"


def _state_path() -> Path:
    return notes_dir() / "state.json"


def append(entry: dict, now: datetime | None = None) -> None:
    """Add one note to today's (UTC) inbox file. `now` is for tests."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    at = now.isoformat(timespec="microseconds")
    text = entry["text"]
    if len(text) > MAX_TEXT:
        text = text[:MAX_TEXT] + " [cut]"
    line = {"id": f"{at}-{os.urandom(3).hex()}", "at": at,
            "session": entry["session"], "cwd": entry["cwd"], "text": text}
    box = _inbox()
    box.mkdir(parents=True, exist_ok=True)
    with (box / f"{now:%Y-%m-%d}.jsonl").open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def _day_files() -> list[tuple[date, Path]]:
    try:
        paths = list(_inbox().iterdir())
    except OSError:
        return []
    out = []
    for p in paths:
        m = _DAY_FILE.fullmatch(p.name)
        if not m:
            continue
        try:
            out.append((date.fromisoformat(m.group(1)), p))
        except ValueError:
            continue
    return sorted(out)


def _entries(path: Path) -> list[dict]:
    """The well-formed entries in one file; damaged lines are skipped."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if isinstance(e, dict) and all(isinstance(e.get(k), str) for k in _FIELDS):
            out.append({k: e[k] for k in _FIELDS})
    return out


def _digested_through() -> str | None:
    try:
        data = json.loads(_state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = data.get("digested_through") if isinstance(data, dict) else None
    return value if isinstance(value, str) else None


def read(limit: int = 150) -> dict:
    """The oldest `limit` undigested notes, from startup folders only.

    If any of those notes comes from a folder not yet confirmed one way or the other, nothing is
    returned and the folders are listed instead, so the sprinter can be asked first.
    """
    through = _digested_through()
    pending = sorted((e for _, p in _day_files() for e in _entries(p)
                      if through is None or e["id"] > through), key=lambda e: e["id"])
    considered = pending[:limit]
    projects = read_settings().get("projects")
    projects = projects if isinstance(projects, dict) else {}
    unknown: dict[str, int] = {}
    for e in considered:
        if not isinstance(projects.get(e["cwd"]), bool):
            unknown[e["cwd"]] = unknown.get(e["cwd"], 0) + 1
    if unknown:
        return {"entries": [], "more": False, "through": None,
                "unknown_projects": [{"cwd": c, "count": n} for c, n in unknown.items()]}
    return {"entries": [e for e in considered if projects[e["cwd"]] is True],
            "more": len(pending) > len(considered),
            "through": considered[-1]["id"] if considered else None,
            "unknown_projects": []}


def done(through: str) -> None:
    """Mark every note up to and including `through` as digested. Never moves backwards."""
    current = _digested_through()
    if current is not None and through <= current:
        return
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"state.json.tmp-{os.getpid()}")
    tmp.write_text(json.dumps({"digested_through": through}), encoding="utf-8", newline="\n")
    tmp.replace(path)


def prune(today: date) -> int:
    """Delete inbox files older than 30 days and files fully digested, never today's. Returns the count."""
    through = _digested_through()
    deleted = 0
    for day, path in _day_files():
        if day == today:
            continue
        too_old = (today - day).days > KEEP_DAYS
        digested = through is not None and all(e["id"] <= through for e in _entries(path))
        if too_old or digested:
            try:
                path.unlink()
            except OSError:
                continue
            deleted += 1
    return deleted
