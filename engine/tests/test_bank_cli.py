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
