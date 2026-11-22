import os
from pathlib import Path

from companions import home
from conftest import run_cli


def test_default_home_is_sprintcompanions_in_user_home(monkeypatch):
    monkeypatch.delenv("COMPANIONS_HOME", raising=False)
    assert home.data_home() == Path.home() / "SprintCompanions"


def test_env_overrides_home(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPANIONS_HOME", str(tmp_path / "h"))
    assert home.data_home() == tmp_path / "h"
    assert home.people_dir() == tmp_path / "h" / "people"
    assert home.notes_dir() == tmp_path / "h" / "notes"
    assert home.settings_path() == tmp_path / "h" / "settings.json"
    assert not (tmp_path / "h").exists()  # the getters create nothing


def test_ensure_home_creates_folders_and_readme(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPANIONS_HOME", str(tmp_path / "h"))
    assert home.ensure_home() == tmp_path / "h"
    for name in ("people", "notes"):
        assert (tmp_path / "h" / name).is_dir()
    assert not (tmp_path / "h" / "sessions").exists()
    readme = (tmp_path / "h" / "README.txt").read_text(encoding="utf-8")
    assert readme.rstrip().endswith("Nothing in this folder is uploaded.")
    (tmp_path / "h" / "README.txt").write_text("mine", encoding="utf-8")
    home.ensure_home()
    assert (tmp_path / "h" / "README.txt").read_text(encoding="utf-8") == "mine"


def test_settings_roundtrip_keeps_other_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPANIONS_HOME", str(tmp_path / "h"))
    assert home.read_settings() == {}
    home.update_settings(a=1)
    assert home.update_settings(b=2) == {"a": 1, "b": 2}
    assert home.read_settings() == {"a": 1, "b": 2}


def test_version_command():
    r = run_cli("version")
    assert r.returncode == 0 and r.stdout.strip() == "companions 0.1.0"
