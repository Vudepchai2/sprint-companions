"""Claude Code hooks for quiet notes. Both run on the sprinter's machine and must never get in the way."""
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from . import inbox, notes_state
from ..home import notes_dir, update_settings
from .secrets import redact

OPT_IN_QUESTION = ("Want the companions to keep up with your build sessions? "
                   "They only keep what you type, on this machine. You can turn it off any time.")

CTX = ("Sprint companions: quiet notes are not set up yet. At a natural moment in this session, "
       "never in the middle of a task, ask the user once, in one line: "
       f"\"{OPT_IN_QUESTION}\" Then run `companions notes on` or `companions notes off` "
       "with the Bash tool (never PowerShell) to match their answer. Don't ask again.")

_BARE_SLASH = re.compile(r"/\S*")

# The launcher writes each prompt's payload to notes/pending and starts the engine in the background
# with --payload, so the sprinter never waits for Python. The file is the only raw copy of the prompt.
PENDING_MAX_AGE = 300  # seconds: older payload files were left by an engine that died; never kept


def pending_dir() -> Path:
    return notes_dir() / "pending"


def _in_pending(path: Path) -> bool:
    try:
        return os.path.normcase(str(path.resolve().parent)) == os.path.normcase(str(pending_dir().resolve()))
    except OSError:
        return False


def take_payload(path: str) -> str:
    """Read a payload file from notes/pending and delete it at once, whatever it holds.

    A file anywhere else is neither read nor deleted. Never raises; returns "" when there's nothing.
    """
    p = Path(path)
    if not _in_pending(p):
        return ""
    try:
        return p.read_bytes().decode("utf-8-sig", errors="replace")
    except OSError:
        return ""
    finally:
        try:
            p.unlink()
        except OSError:
            pass


def sweep_pending(now: float | None = None) -> None:
    """Delete payload files older than PENDING_MAX_AGE. Never raises."""
    now = time.time() if now is None else now
    try:
        entries = list(os.scandir(pending_dir()))
    except OSError:
        return
    for e in entries:
        try:
            if e.is_file(follow_symlinks=False) and now - e.stat(follow_symlinks=False).st_mtime > PENDING_MAX_AGE:
                os.unlink(e.path)
        except OSError:
            continue


def prompt(stdin_text: str) -> None:
    """UserPromptSubmit: keep what the sprinter typed, secrets removed. Never raises, prints nothing.

    Every folder is captured; only startup folders are read back later, so a folder confirmed
    afterwards still has its notes.
    """
    try:
        if notes_state() != "on":
            return
        payload = json.loads(stdin_text)
        if not isinstance(payload, dict):
            return
        text, cwd, session = payload.get("prompt"), payload.get("cwd"), payload.get("session_id")
        if not isinstance(text, str) or not isinstance(cwd, str) or not cwd:
            return
        text = text.strip()
        if not text or _BARE_SLASH.fullmatch(text):
            return
        inbox.append({"session": session if isinstance(session, str) else "",
                      "cwd": cwd, "text": redact(text)})
    except Exception:
        return


def session_start(stdin_text: str) -> str:
    """SessionStart: prune the inbox, and ask for opt-in once. Returns the JSON to print, or ""."""
    sweep_pending()
    try:
        inbox.prune(datetime.now(timezone.utc).date())
    except Exception:
        pass
    if notes_state() != "unset":
        return ""
    update_settings(quiet_notes="asked")
    return json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": CTX}})
