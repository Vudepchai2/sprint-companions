"""Quiet notes: what the sprinter types, kept on this machine after they opt in."""
from ..home import read_settings, settings_state, update_settings

STATES = ("unset", "asked", "on", "off")


def notes_state() -> str:
    """unset, asked, on or off, from the quiet_notes setting; unset when settings are missing or damaged."""
    state, data = settings_state()
    value = data.get("quiet_notes") if state == "ok" else None
    return value if value in STATES else "unset"


def set_project(cwd: str, startup: bool) -> None:
    """Record whether a project folder is the startup. Only startup folders' notes are digested."""
    projects = read_settings().get("projects")
    projects = dict(projects) if isinstance(projects, dict) else {}
    projects[cwd] = bool(startup)
    update_settings(projects=projects)
