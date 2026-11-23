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


def test_session_start_asks_once(home):
    r = run_cli("hook", "session-start", input="{}")
    assert r.returncode == 0 and r.stderr == ""
    out = json.loads(r.stdout)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert OPT_IN_QUESTION in ctx and "companions notes on" in ctx
    # On Windows, Claude Code also has a PowerShell tool, which can't run the bash launcher.
    assert "with the Bash tool" in ctx
    assert run_cli("notes", "status").stdout.strip() == "asked"
    assert run_cli("hook", "session-start", input="{}").stdout == ""


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


# The launcher hands the prompt hook its payload in a file under notes/pending, then returns at once
# (a Python start costs 0.3-1.5 s on Windows). That file is the only raw copy of the prompt: the
# engine deletes it as soon as it has read it, and sweeps up any older one a dead engine left.

def _pending(home, name="1-2.json", body=None, age=0.0):
    import os, time
    d = home / "notes" / "pending"
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(json.dumps(PAYLOAD) if body is None else body, encoding="utf-8")
    if age:
        t = time.time() - age
        os.utime(p, (t, t))
    return p


def test_prompt_hook_reads_and_deletes_its_payload_file(home):
    run_cli("notes", "on"); run_cli("notes", "project", "/w/clinic-app", "--startup", "yes")
    p = _pending(home, body=json.dumps({**PAYLOAD, "prompt": "key sk-" + "x" * 30}))
    r = run_cli("hook", "prompt", "--payload", p)
    assert r.returncode == 0 and r.stdout == "" and r.stderr == ""
    assert not p.exists()
    e = json.loads(run_cli("notes", "read").stdout)["entries"][0]
    assert e["text"] == "key [removed]"


@pytest.mark.parametrize("state", [None, "off", "asked"])
def test_prompt_hook_deletes_its_payload_file_even_when_notes_are_off(home, state):
    if state is not None:
        (home / "settings.json").write_text(json.dumps({"quiet_notes": state}), encoding="utf-8")
    p = _pending(home)
    assert run_cli("hook", "prompt", "--payload", p).returncode == 0
    assert not p.exists() and inbox_is_empty(home)


@pytest.mark.parametrize("body", ["", "not json", "[]", "﻿{"])
def test_prompt_hook_deletes_a_bad_payload_file(home, body):
    run_cli("notes", "on")
    p = _pending(home, body=body)
    r = run_cli("hook", "prompt", "--payload", p)
    assert r.returncode == 0 and r.stdout == "" and r.stderr == ""
    assert not p.exists() and inbox_is_empty(home)


def test_prompt_hook_never_deletes_a_file_outside_pending(home, tmp_path_factory):
    run_cli("notes", "on")
    other = tmp_path_factory.mktemp("elsewhere") / "keep.json"
    other.write_text(json.dumps(PAYLOAD), encoding="utf-8")
    beside = home / "notes" / "keep.json"
    beside.parent.mkdir(parents=True, exist_ok=True)
    beside.write_text(json.dumps(PAYLOAD), encoding="utf-8")
    for p in (other, beside):
        r = run_cli("hook", "prompt", "--payload", p)
        assert r.returncode == 0 and r.stdout == "" and r.stderr == ""
        assert p.exists()
    assert inbox_is_empty(home)  # a payload from anywhere else isn't taken either


def test_prompt_hook_survives_a_missing_payload_file(home):
    run_cli("notes", "on")
    r = run_cli("hook", "prompt", "--payload", home / "notes" / "pending" / "gone.json")
    assert r.returncode == 0 and r.stdout == "" and r.stderr == ""
    assert inbox_is_empty(home)


@pytest.mark.parametrize("event", ["prompt", "session-start"])
def test_hooks_sweep_stale_payload_files(home, event):
    run_cli("notes", "on")
    stale = _pending(home, "old.json", age=600)
    fresh = _pending(home, "new.json", age=30)  # another prompt's engine may still be on its way to it
    r = run_cli("hook", event, input=json.dumps(PAYLOAD))
    assert r.returncode == 0 and r.stderr == ""
    assert not stale.exists() and fresh.exists()


def test_session_start_sweeps_even_when_notes_are_off(home):
    run_cli("notes", "off")
    stale = _pending(home, "old.json", age=600)
    assert run_cli("hook", "session-start").returncode == 0
    assert not stale.exists()
