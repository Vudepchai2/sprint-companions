from pathlib import Path

from conftest import run_cli


def test_bank_without_ensure_fails_with_hint(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPANIONS_HOME", str(tmp_path))
    r = run_cli("bank")
    assert r.returncode == 1 and 'companions bank --ensure --name' in r.stderr


def test_bank_ensure_creates_once_and_reuses(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPANIONS_HOME", str(tmp_path))
    first = run_cli("bank", "--ensure", "--name", "Ana").stdout.strip()
    second = run_cli("bank", "--ensure", "--name", "Other").stdout.strip()
    assert first == second == str(tmp_path / "people" / "ana")
    assert (Path(first) / "person.json").exists()


def test_bank_ensure_saves_slug_in_settings(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("COMPANIONS_HOME", str(tmp_path))
    run_cli("bank", "--ensure", "--name", "Ana")
    assert json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))["bank"] == "ana"


def test_bank_ensure_adopts_existing_folder_without_setting(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("COMPANIONS_HOME", str(tmp_path))
    first = run_cli("bank", "--ensure", "--name", "Ana").stdout.strip()
    (tmp_path / "settings.json").unlink()
    r = run_cli("bank", "--ensure", "--name", "Ana")
    assert r.returncode == 0 and r.stdout.strip() == first
    assert json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))["bank"] == "ana"
