import json
import re
from datetime import date, datetime, timedelta, timezone

from companions.notes import inbox, set_project

T0 = datetime(2026, 11, 23, 9, 0, 0, 123456, tzinfo=timezone.utc)


def add(text, cwd="/w/app", at=T0, session="s1"):
    inbox.append({"session": session, "cwd": cwd, "text": text}, now=at)


def ids(home):
    """Every id in the inbox, oldest first."""
    out = []
    for p in sorted((home / "notes" / "inbox").glob("*.jsonl")):
        out += [json.loads(line)["id"] for line in p.read_text(encoding="utf-8").splitlines()]
    return sorted(out)


def texts(result):
    return [e["text"] for e in result["entries"]]


def test_append_then_read_oldest_first(home):
    set_project("/w/app", True)
    add("one", at=T0)
    add("two", at=T0 + timedelta(seconds=1))
    add("three", at=T0 + timedelta(days=1))
    day1 = home / "notes" / "inbox" / "2026-11-23.jsonl"
    assert day1.exists() and (home / "notes" / "inbox" / "2026-11-24.jsonl").exists()
    assert b"\r\n" not in day1.read_bytes()
    first = json.loads(day1.read_text(encoding="utf-8").splitlines()[0])
    assert set(first) == {"id", "at", "session", "cwd", "text"}
    assert first["at"] == "2026-11-23T09:00:00.123456+00:00"
    assert re.fullmatch(re.escape(first["at"]) + r"-[0-9a-f]{6}", first["id"])
    assert (first["session"], first["cwd"], first["text"]) == ("s1", "/w/app", "one")
    r = inbox.read()
    assert texts(r) == ["one", "two", "three"]
    assert r["more"] is False and r["unknown_projects"] == []
    assert r["through"] == r["entries"][-1]["id"]


def test_unknown_project_blocks_read_and_is_listed_with_count(home):
    set_project("/w/app", True)
    add("app note", cwd="/w/app", at=T0)
    add("other 1", cwd="/w/other", at=T0 + timedelta(seconds=1))
    add("third", cwd="/w/third", at=T0 + timedelta(seconds=2))
    add("other 2", cwd="/w/other", at=T0 + timedelta(seconds=3))
    r = inbox.read()
    assert r == {"entries": [], "more": False, "through": None,
                 "unknown_projects": [{"cwd": "/w/other", "count": 2}, {"cwd": "/w/third", "count": 1}]}
    set_project("/w/other", True)
    set_project("/w/third", False)
    assert texts(inbox.read()) == ["app note", "other 1", "other 2"]


def test_non_startup_project_entries_never_returned_but_covered_by_through(home):
    set_project("/w/app", True)
    set_project("/w/side", False)
    add("a", cwd="/w/app", at=T0)
    add("side x", cwd="/w/side", at=T0 + timedelta(seconds=1))
    add("b", cwd="/w/app", at=T0 + timedelta(seconds=2))
    add("side y", cwd="/w/side", at=T0 + timedelta(seconds=3))
    r = inbox.read()
    assert texts(r) == ["a", "b"]
    assert all(e["cwd"] == "/w/app" for e in r["entries"])
    assert r["through"] == ids(home)[-1]
    inbox.done(r["through"])
    assert inbox.read() == {"entries": [], "more": False, "through": None, "unknown_projects": []}


def test_done_hides_digested_and_never_moves_backwards(home):
    set_project("/w/app", True)
    for i in range(3):
        add(f"n{i}", at=T0 + timedelta(seconds=i))
    i1, i2, _ = ids(home)
    inbox.done(i2)
    assert texts(inbox.read()) == ["n2"]
    inbox.done(i1)
    assert texts(inbox.read()) == ["n2"]
    state = json.loads((home / "notes" / "state.json").read_text(encoding="utf-8"))
    assert state == {"digested_through": i2}


def test_read_limit_sets_more(home):
    set_project("/w/app", True)
    for i in range(5):
        add(f"n{i}", at=T0 + timedelta(seconds=i))
    seen = []
    for expect_more in (True, True, False):
        r = inbox.read(limit=2)
        assert r["more"] is expect_more
        seen += texts(r)
        inbox.done(r["through"])
    assert seen == ["n0", "n1", "n2", "n3", "n4"]
    assert inbox.read(limit=2)["through"] is None


def test_prune_deletes_old_and_fully_digested_but_never_today(home):
    today = date(2026, 11, 23)
    box = home / "notes" / "inbox"

    def on(d, h=9):
        return datetime(d.year, d.month, d.day, h, tzinfo=timezone.utc)

    add("31 days old", at=on(today - timedelta(days=31)))
    add("30 days old", at=on(today - timedelta(days=30)))
    add("yesterday a", at=on(today - timedelta(days=1), 9))
    add("yesterday b", at=on(today - timedelta(days=1), 10))
    add("today", at=on(today))
    (box / "notes.txt").write_text("not an inbox file", encoding="utf-8")

    assert inbox.prune(today) == 1
    assert not (box / "2026-10-23.jsonl").exists() and (box / "2026-10-24.jsonl").exists()

    _, yesterday_a, _, today_id = ids(home)
    inbox.done(yesterday_a)
    assert inbox.prune(today) == 1
    assert not (box / "2026-10-24.jsonl").exists() and (box / "2026-11-22.jsonl").exists()

    inbox.done(today_id)
    assert inbox.prune(today) == 1
    # .lock is the writers' lock (no notes in it); prune leaves it and anything else it didn't write
    assert sorted(p.name for p in box.iterdir()) == [".lock", "2026-11-23.jsonl", "notes.txt"]


def test_text_is_capped_at_4000_chars(home):
    set_project("/w/app", True)
    add("x" * 5000, at=T0)
    add("y" * 4000, at=T0 + timedelta(seconds=1))
    long, exact = texts(inbox.read())
    assert long == "x" * 4000 + " [cut]"
    assert exact == "y" * 4000


def test_damaged_state_file_is_treated_as_nothing_digested(home):
    set_project("/w/app", True)
    add("one", at=T0)
    add("two", at=T0 + timedelta(seconds=1))
    inbox.done(ids(home)[-1])
    assert texts(inbox.read()) == []
    (home / "notes" / "state.json").write_text("{not json", encoding="utf-8")
    assert texts(inbox.read()) == ["one", "two"]
    inbox.done(ids(home)[0])
    assert texts(inbox.read()) == ["two"]


def test_read_skips_damaged_lines(home):
    set_project("/w/app", True)
    add("good", at=T0)
    with (home / "notes" / "inbox" / "2026-11-23.jsonl").open("a", encoding="utf-8", newline="\n") as f:
        f.write('{"id": "half a line\n[]\n{"id": 5}\n')
    assert texts(inbox.read()) == ["good"]


def test_read_with_no_inbox_is_empty(home):
    assert inbox.read() == {"entries": [], "more": False, "through": None, "unknown_projects": []}


def test_append_keeps_every_note_when_engines_write_at_once(tmp_path):
    """The prompt hook runs the engine in the background, so two prompts' engines (or two Claude Code
    sessions') can append at the same moment. On Windows an append is a seek to the end and a write,
    not one step, so without a lock one note can overwrite the other."""
    import os
    import subprocess
    import sys
    from pathlib import Path
    code = ("import sys, time\n"
            "from companions.notes import inbox\n"
            "t = float(sys.argv[1])\n"
            "while time.time() < t: pass\n"
            "for i in range(20): inbox.append({'session': 's', 'cwd': '/w', 'text': sys.argv[2] + '-' + str(i)})\n")
    env = {**os.environ, "COMPANIONS_HOME": str(tmp_path),
           "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    import time
    start = time.time() + 3  # every process starts writing at the same moment
    procs = [subprocess.Popen([sys.executable, "-c", code, str(start), f"w{n}"], env=env) for n in range(6)]
    assert all(p.wait(timeout=60) == 0 for p in procs)
    lines = [line for f in (tmp_path / "notes" / "inbox").glob("*.jsonl")
             for line in f.read_text(encoding="utf-8").splitlines()]
    texts = sorted(json.loads(line)["text"] for line in lines)
    assert texts == sorted(f"w{n}-{i}" for n in range(6) for i in range(20))
