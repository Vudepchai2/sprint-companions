import json
from datetime import datetime, timedelta, timezone

import pytest

from conftest import run_cli
from companions.notes.hooks import OPT_IN_QUESTION

PAYLOAD = {"session_id": "abc", "cwd": "/w/clinic-app", "hook_event_name": "UserPromptSubmit",
           "prompt": "first clinic signed, €200/month", "transcript_path": "/x.jsonl"}


def inbox_is_empty(home):
    box = home / "notes" / "inbox"
    return not box.exists() or not any(box.iterdir())


def test_prompt_hook_captures_when_on(home):
    run_cli("notes", "on"); run_cli("notes", "project", "/w/clinic-app", "--startup", "yes")
    r = run_cli("hook", "prompt", input=json.dumps(PAYLOAD))
    assert r.returncode == 0 and r.stdout == "" and r.stderr == ""
    e = json.loads(run_cli("notes", "read").stdout)["entries"][0]
    assert (e["session"], e["cwd"], e["text"]) == ("abc", "/w/clinic-app", PAYLOAD["prompt"])


@pytest.mark.parametrize("state", [None, "asked", "off", "damaged"])
def test_prompt_hook_captures_nothing_unless_on(home, state):      # Review Focus 2
    if state == "damaged":
        (home / "settings.json").write_text("{not json", encoding="utf-8")
    elif state is not None:
        (home / "settings.json").write_text(json.dumps({"quiet_notes": state}), encoding="utf-8")
    r = run_cli("hook", "prompt", input=json.dumps(PAYLOAD))
    assert r.returncode == 0 and r.stdout == "" and r.stderr == ""
    assert inbox_is_empty(home)


@pytest.mark.parametrize("stdin", ["", "not json", "[]", json.dumps({"prompt": 5}),
                                   json.dumps({"prompt": "hi", "cwd": 7}), "﻿{", "null"])
def test_prompt_hook_survives_bad_input(home, stdin):               # Review Focus 1
    run_cli("notes", "on")
    r = run_cli("hook", "prompt", input=stdin)
    assert r.returncode == 0 and r.stdout == "" and r.stderr == ""
    assert inbox_is_empty(home)


def test_prompt_hook_survives_unwritable_home(home):
    run_cli("notes", "on"); (home / "notes").write_text("a file, not a folder")
    r = run_cli("hook", "prompt", input=json.dumps(PAYLOAD))
    assert r.returncode == 0 and r.stdout == "" and r.stderr == ""


def test_prompt_hook_survives_unreadable_settings(home):
    (home / "settings.json").mkdir()
    r = run_cli("hook", "prompt", input=json.dumps(PAYLOAD))
    assert r.returncode == 0 and r.stdout == "" and r.stderr == ""
    assert inbox_is_empty(home)


def test_prompt_hook_redacts_before_writing(home):                  # Review Focus 3
    run_cli("notes", "on")
    run_cli("hook", "prompt", input=json.dumps({**PAYLOAD, "prompt": "key sk-" + "x" * 30}))
    raw = "".join(p.read_text(encoding="utf-8") for p in (home / "notes" / "inbox").iterdir())
    assert "xxxxxxxxxx" not in raw and "[removed]" in raw


def test_prompt_hook_skips_empty_and_slash_only(home):
    run_cli("notes", "on"); run_cli("notes", "project", "/w/clinic-app", "--startup", "yes")
    for prompt in ("", "   ", "/mm", "  /mm  ", "/"):
        r = run_cli("hook", "prompt", input=json.dumps({**PAYLOAD, "prompt": prompt}))
        assert r.returncode == 0 and r.stdout == ""
    assert inbox_is_empty(home)
    run_cli("hook", "prompt", input=json.dumps({**PAYLOAD, "prompt": "/mm should we raise?"}))
    entries = json.loads(run_cli("notes", "read").stdout)["entries"]
    assert [e["text"] for e in entries] == ["/mm should we raise?"]


def test_session_start_note_asks_for_the_opt_in(home):
    r = run_cli("hook", "session-start", input="{}")
    assert r.returncode == 0 and r.stderr == ""
    out = json.loads(r.stdout)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert OPT_IN_QUESTION in ctx and "companions notes on" in ctx
    assert "companions notes asked" in ctx  # run once the question has really been put
    # On Windows, Claude Code also has a PowerShell tool, which can't run the bash launcher.
    assert "with the Bash tool" in ctx


def test_session_start_note_repeats_until_the_question_is_really_asked(home):
    """The note only tells Claude to ask. If no natural moment came (a pure coding session, or the
    sprinter quit early), the next session must ask again: emitting the note marks nothing."""
    assert run_cli("hook", "session-start", input="{}").stdout != ""
    assert run_cli("notes", "status").stdout.strip() == "unset"
    assert run_cli("hook", "session-start", input="{}").stdout != ""
    r = run_cli("notes", "asked")
    assert (r.returncode, r.stdout.strip()) == (0, "quiet notes: asked")
    assert run_cli("notes", "status").stdout.strip() == "asked"
    assert run_cli("hook", "session-start", input="{}").stdout == ""


@pytest.mark.parametrize("state", ["on", "off"])
def test_notes_asked_never_undoes_an_answer(home, state):
    run_cli("notes", state)
    r = run_cli("notes", "asked")
    assert r.returncode == 0 and r.stdout.strip() == f"quiet notes: {state}"
    assert run_cli("notes", "status").stdout.strip() == state


def test_opt_in_question_is_exact_copy():
    assert OPT_IN_QUESTION == ("Want the companions to keep up with your build sessions? "
                               "They only keep what you type, on this machine. You can turn it off any time.")


@pytest.mark.parametrize("state", ["on", "off"])
def test_session_start_is_silent_once_answered(home, state):
    run_cli("notes", state)
    r = run_cli("hook", "session-start", input="{}")
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    assert run_cli("notes", "status").stdout.strip() == state


def test_session_start_prunes(home):
    box = home / "notes" / "inbox"
    box.mkdir(parents=True)
    today = datetime.now(timezone.utc).date()
    old = box / f"{today - timedelta(days=31):%Y-%m-%d}.jsonl"
    current = box / f"{today:%Y-%m-%d}.jsonl"
    line = json.dumps({"id": "x", "at": "x", "session": "s", "cwd": "/w", "text": "t"}) + "\n"
    old.write_text(line, encoding="utf-8")
    current.write_text(line, encoding="utf-8")
    run_cli("notes", "on")
    r = run_cli("hook", "session-start", input="{}")
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    assert not old.exists() and current.exists()


@pytest.mark.parametrize("stdin", ["", "not json", "[]"])
def test_session_start_survives_bad_input_and_broken_notes_folder(home, stdin):
    (home / "notes").write_text("a file, not a folder")
    r = run_cli("hook", "session-start", input=stdin)
    assert r.returncode == 0 and r.stderr == ""
    assert json.loads(r.stdout)["hookSpecificOutput"]["hookEventName"] == "SessionStart"


def test_session_start_survives_unreadable_settings(home):
    (home / "settings.json").mkdir()
    r = run_cli("hook", "session-start", input="{}")
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


def test_notes_on_off_status(home):
    assert run_cli("notes", "status").stdout.strip() == "unset"
    assert run_cli("notes", "on").stdout.strip() == "quiet notes: on"
    assert run_cli("notes", "status").stdout.strip() == "on"
    assert run_cli("notes", "off").stdout.strip() == "quiet notes: off"
    assert run_cli("notes", "status").stdout.strip() == "off"


def test_notes_status_is_unset_when_settings_damaged(home):
    (home / "settings.json").write_text("{not json", encoding="utf-8")
    assert run_cli("notes", "status").stdout.strip() == "unset"


def test_notes_project_read_limit_and_done(home):
    run_cli("notes", "on")
    for i in range(3):
        run_cli("hook", "prompt", input=json.dumps({**PAYLOAD, "prompt": f"note {i}"}))
    blocked = json.loads(run_cli("notes", "read").stdout)
    assert blocked["unknown_projects"] == [{"cwd": "/w/clinic-app", "count": 3}]
    assert run_cli("notes", "project", "/w/clinic-app", "--startup", "yes").returncode == 0
    settings = json.loads((home / "settings.json").read_text(encoding="utf-8"))
    assert settings["projects"] == {"/w/clinic-app": True} and settings["quiet_notes"] == "on"
    first = json.loads(run_cli("notes", "read", "--limit", "2").stdout)
    assert [e["text"] for e in first["entries"]] == ["note 0", "note 1"] and first["more"] is True
    assert run_cli("notes", "done", "--through", first["through"]).returncode == 0
    rest = json.loads(run_cli("notes", "read").stdout)
    assert [e["text"] for e in rest["entries"]] == ["note 2"] and rest["more"] is False


def test_notes_project_no_marks_folder_false(home):
    run_cli("notes", "project", "/w/side", "--startup", "no")
    assert json.loads((home / "settings.json").read_text(encoding="utf-8"))["projects"] == {"/w/side": False}


def test_notes_read_rejects_bad_limit(home):
    r = run_cli("notes", "read", "--limit", "0")
    assert r.returncode != 0 and "Traceback" not in r.stderr


@pytest.mark.parametrize("bad", ["null", "latest", "<through>", "", "2026-11-23", "2026-11-23T09:00:00+00:00",
                                 "2026-11-23T09:00:00.123456+00:00-zzzzzz"])
def test_notes_done_rejects_a_through_that_is_not_an_id(home, bad):
    run_cli("notes", "on"); run_cli("notes", "project", "/w/clinic-app", "--startup", "yes")
    run_cli("hook", "prompt", input=json.dumps(PAYLOAD))
    r = run_cli("notes", "done", "--through", bad)
    assert r.returncode == 1 and "Traceback" not in r.stderr and "through" in r.stderr
    assert not (home / "notes" / "state.json").exists()
    assert len(json.loads(run_cli("notes", "read").stdout)["entries"]) == 1  # nothing was marked digested
