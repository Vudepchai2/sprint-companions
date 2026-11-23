import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAID = {"kind": "said", "ref": "sessions/a"}


def run(*args, cwd=ROOT, env=None, text=True, input=None):
    return subprocess.run([sys.executable, "-m", "companions", *map(str, args)], capture_output=True, text=text,
                          cwd=cwd, env={**os.environ, "PYTHONPATH": str(ROOT), **(env or {})}, input=input)


def _batch(tmp_path, items, name="batch.json"):
    f = tmp_path / name
    f.write_text(json.dumps({"source": SAID, "items": items}, ensure_ascii=False), encoding="utf-8")
    return f


def _bank(tmp_path, items=None, name="Ana"):
    r = run("memory", "init", name, "--root", tmp_path / "people")
    assert r.returncode == 0, r.stderr
    bank = Path(r.stdout.strip())
    if items:
        r = run("memory", "retain", bank, _batch(tmp_path, items))
        assert r.returncode == 0, r.stderr
    return bank


MOMENT = {"type": "moment", "title": "The night shift", "what_happened": "She fixed the line."}


def test_init_retain_brief_roundtrip(tmp_path):
    bank = _bank(tmp_path)
    assert (bank / "person.json").exists()
    r = run("memory", "retain", bank, _batch(tmp_path, [MOMENT]))
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["added"][0]["id"] == "m1"
    r = run("memory", "brief", bank)
    assert r.returncode == 0 and "The night shift" in r.stdout
    assert (bank / "pages" / "profile.md").exists()


def test_retain_bad_batch_exit_1_lists_errors(tmp_path):
    bank = _bank(tmp_path)
    r = run("memory", "retain", bank, _batch(tmp_path, [{"type": "bogus"}, {"type": "nope"}]))
    assert r.returncode == 1
    assert len(r.stderr.strip().splitlines()) == 2
    log = bank / "log.jsonl"
    assert not log.exists() or log.read_text(encoding="utf-8") == ""


def test_retain_accepts_bom_and_reports_bad_json(tmp_path):
    bank = _bank(tmp_path)
    f = tmp_path / "bom.json"
    f.write_text(json.dumps({"source": SAID, "items": [MOMENT]}), encoding="utf-8-sig")
    assert run("memory", "retain", bank, f).returncode == 0
    f.write_text("{nope", encoding="utf-8")
    r = run("memory", "retain", bank, f)
    assert r.returncode == 1 and "batch file is not valid JSON" in r.stderr


def test_retain_reads_the_batch_from_stdin(tmp_path):
    bank = _bank(tmp_path)
    claim = {"type": "claim", "about": "@m", "key": "monthly_price", "statement": "The clinic pays €200 a month.",
             "value": 200, "unit": "EUR per month", "quote": "first clinic signed, €200/month"}
    batch = {"source": {"kind": "build", "ref": "sessions/s1", "at": "2026-11-18", "by": "notes",
                        "project": "clinic-app"},
             "items": [{**MOMENT, "ref": "@m"}, claim]}
    r = run("memory", "retain", bank, "-", text=False,
            input=("﻿" + json.dumps(batch, ensure_ascii=False)).encode("utf-8"))
    assert r.returncode == 0, r.stderr.decode("utf-8")
    assert [a["id"] for a in json.loads(r.stdout.decode("utf-8"))["added"]] == ["m1", "c1"]
    events = [json.loads(line) for line in (bank / "log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert events[-1]["data"]["quote"] == "first clinic signed, €200/month"
    assert events[-1]["source"]["project"] == "clinic-app"
    r = run("memory", "retain", bank, "-", input="{nope")
    assert r.returncode == 1 and "batch is not valid JSON" in r.stderr


def test_brief_prints_unicode_on_any_console(tmp_path):
    title = "René’s call"
    bank = _bank(tmp_path, [{**MOMENT, "title": title}])
    r = run("memory", "brief", bank, env={"PYTHONIOENCODING": "cp1252"}, text=False)
    assert r.returncode == 0, r.stderr
    assert title.encode("utf-8") in r.stdout


def test_missing_bank_is_clean_error(tmp_path):
    r = run("memory", "brief", tmp_path / "nobody")
    assert r.returncode == 1 and "no memory bank" in r.stderr


def test_delete_requires_yes(tmp_path):
    bank = _bank(tmp_path, [MOMENT])
    r = run("memory", "delete", bank)
    assert r.returncode == 2
    assert f"Refusing to delete {bank} without --yes. This removes every memory for this person and cannot be undone." in r.stderr
    assert bank.exists()
    assert run("memory", "delete", bank, "--yes").returncode == 0
    assert not bank.exists()


def test_forget_retracts(tmp_path):
    bank = _bank(tmp_path, [MOMENT])
    n = len((bank / "log.jsonl").read_text(encoding="utf-8").splitlines())
    assert run("memory", "forget", bank, "m1").returncode == 2  # --reason required by argparse
    r = run("memory", "forget", bank, "m1", "--reason", "she asked")
    assert r.returncode == 0, r.stderr
    assert len((bank / "log.jsonl").read_text(encoding="utf-8").splitlines()) == n + 1
    r = run("memory", "recall", bank, "--type", "moment")
    assert json.loads(r.stdout) == []
    assert run("memory", "forget", bank, "m1", "--reason", "again").returncode == 1


def test_import_recall_gaps_pages(tmp_path):
    bank = _bank(tmp_path)
    doc = tmp_path / "cv.txt"
    doc.write_text("hello", encoding="utf-8")
    r = run("memory", "import", bank, doc)
    assert r.returncode == 0 and r.stdout.strip() == "s1 new"
    assert run("memory", "import", bank, doc).stdout.strip() == "s1 already imported"
    assert isinstance(json.loads(run("memory", "gaps", bank).stdout), list)
    assert run("memory", "pages", bank).returncode == 0


def test_default_people_root_honours_env(tmp_path, monkeypatch):
    from companions.home import people_dir

    monkeypatch.setenv("COMPANIONS_HOME", str(tmp_path / "h"))
    assert people_dir() == tmp_path / "h" / "people"


def _log_lines(bank):
    log = bank / "log.jsonl"
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def test_page_failure_after_retain_is_a_warning_and_the_report_prints(tmp_path):
    bank = _bank(tmp_path)
    (bank / "pages" / "profile.md.tmp").mkdir()  # makes writing that page fail
    r = run("memory", "retain", bank, _batch(tmp_path, [MOMENT]))
    assert r.returncode == 0 and "Traceback" not in r.stderr
    assert json.loads(r.stdout)["added"][0]["id"] == "m1"
    assert "pages were not updated" in r.stderr
    assert len(_log_lines(bank)) == 1


def test_retain_consumes_the_bank_batch_file(tmp_path):
    # Companions write each batch to <bank>/batch.json with Claude Code's Write tool, which won't
    # overwrite a file it hasn't read. The engine removes that one file once it has read it,
    # accepted or rejected, so the next batch is always a fresh file.
    bank = _bank(tmp_path)
    good = _batch(bank, [MOMENT])
    r = run("memory", "retain", bank, good)
    assert r.returncode == 0, r.stderr
    assert not good.exists()
    bad = _batch(bank, [{"type": "bogus"}])
    assert run("memory", "retain", bank, bad).returncode == 1
    assert not bad.exists()


def test_retain_keeps_any_other_batch_file(tmp_path):
    bank = _bank(tmp_path)
    elsewhere = _batch(tmp_path, [MOMENT])
    assert run("memory", "retain", bank, elsewhere).returncode == 0
    assert elsewhere.exists()
    other_name = _batch(bank, [MOMENT], name="mine.json")
    assert run("memory", "retain", bank, other_name).returncode == 0
    assert other_name.exists()


def test_demo_brief_with_a_missing_plan_file_fails_clean(tmp_path):
    bank = _bank(tmp_path)
    r = run("memory", "demo-brief", bank, tmp_path / "no-plan.json")
    assert r.returncode == 1 and "Traceback" not in r.stderr and "plan file" in r.stderr


def test_retain_with_an_unreadable_batch_fails_clean(tmp_path):
    bank = _bank(tmp_path)
    r = run("memory", "retain", bank, tmp_path / "missing.json")
    assert r.returncode == 1 and "Traceback" not in r.stderr and "batch file" in r.stderr
    (bank / "batch.json").mkdir()  # the bank's own batch path, but a folder: reading and removing both fail
    r = run("memory", "retain", bank, bank / "batch.json")
    assert r.returncode == 1 and "Traceback" not in r.stderr and "batch file" in r.stderr
