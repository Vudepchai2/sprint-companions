"""Claude Code hooks for quiet notes. Both run on the sprinter's machine and must never get in the way."""
import json
import re
from datetime import datetime, timezone

from . import inbox, notes_state
from ..home import settings_state
from .secrets import redact

OPT_IN_QUESTION = ("Want the companions to keep up with your build sessions? "
                   "They only keep what you type, on this machine. You can turn it off any time.")

CTX = ("Sprint companions: quiet notes are not set up yet. At a natural moment in this session, "
       "never in the middle of a task, ask the user once, in one line: "
       f"\"{OPT_IN_QUESTION}\" In the turn where you ask it, run `companions notes asked` "
       "with the Bash tool (never PowerShell), so it isn't asked again. When they answer, run "
       "`companions notes on` or `companions notes off` with the Bash tool to match. "
       "Don't ask again.")

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
    """SessionStart: prune the inbox, and ask for the opt-in. Returns the JSON to print, or "".

    The note appears in every session while quiet notes are `unset`. It marks nothing itself: Claude
    runs `companions notes asked` once it has really put the question, so a session that never found
    a moment to ask leaves the next one to ask.
    """
    try:
        inbox.prune(datetime.now(timezone.utc).date())
    except Exception:
        pass
    if notes_state() != "unset" or settings_state()[0] == "unreadable":
        return ""  # an unreadable settings file couldn't record the answer, so don't ask yet
    return json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": CTX}})
