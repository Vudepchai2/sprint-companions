"""Claude Code hooks for quiet notes. Both run on the sprinter's machine and must never get in the way."""
import json
import re
from datetime import datetime, timezone

from . import inbox, notes_state
from ..home import update_settings
from .secrets import redact

OPT_IN_QUESTION = ("Want the companions to keep up with your build sessions? "
                   "They only keep what you type, on this machine. You can turn it off any time.")

CTX = ("Sprint companions: quiet notes are not set up yet. At a natural moment in this session, "
       "never in the middle of a task, ask the user once, in one line: "
       f"\"{OPT_IN_QUESTION}\" Then run `companions notes on` or `companions notes off` "
       "to match their answer. Don't ask again.")

_BARE_SLASH = re.compile(r"/\S*")


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
    try:
        inbox.prune(datetime.now(timezone.utc).date())
    except Exception:
        pass
    if notes_state() != "unset":
        return ""
    update_settings(quiet_notes="asked")
    return json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": CTX}})
