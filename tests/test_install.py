"""The one-line installers: install.sh (macOS, Linux, Git Bash) and install.ps1 (Windows PowerShell).

install.sh runs here against a fake `claude` and a fake `uv` (which hands `uv run python` to this
Python), in a scratch HOME and Claude config folder: nothing is downloaded or installed.
install.ps1 is checked for syntax and for the rules that keep it safe inside `irm | iex`.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from test_launcher import BASH

REPO = Path(__file__).resolve().parents[1]
INSTALL_SH = REPO / "install.sh"
INSTALL_PS1 = REPO / "install.ps1"
RULES = ["Skill(sprint-companions:*)", "Bash(companions *)"]
# Wherever this machine keeps git: Git\cmd on a GitHub Windows runner, /usr/bin on macOS and Linux.
GIT = shutil.which("git") or "/usr/bin/git"

FAKE_CLAUDE = r"""#!/bin/bash
s="$FAKE_STATE"
echo "$*" >> "$s/log"
case "$*" in
  "--version") echo "9.9.9 (Claude Code)" ;;
  "plugin marketplace list") echo "Configured marketplaces:"; [ -f "$s/mkt" ] && echo "  sprint-companions" ;;
  "plugin marketplace add Vudepchai2/sprint-companions") touch "$s/mkt" ;;
  "plugin list") [ -f "$s/plugin" ] && echo "sprint-companions@sprint-companions" ;;
  "plugin list --json")
    if [ -f "$s/plugin" ]; then printf '[{"id":"sprint-companions@sprint-companions","installPath":"%s"}]\n' "$FAKE_PLUGIN_DIR"
    else echo "[]"; fi ;;
  "plugin install sprint-companions@sprint-companions --scope user") touch "$s/plugin" ;;
esac
exit 0
"""

FAKE_UV = r"""#!/bin/bash
case "${1:-}" in
  --version) echo "uv 0.0.0" ;;
  run) while [ "$#" -gt 0 ] && [ "$1" != python ]; do shift; done; shift; exec "$REAL_PY" "$@" ;;
esac
"""

FAKE_LAUNCHER = "#!/bin/bash\n[ \"${1:-}\" = version ] && echo 'companions 0.1.0'\n"


def _write(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))
    path.chmod(0o755)


@pytest.fixture
def rig(tmp_path):
    if BASH is None:
        if os.environ.get("COMPANIONS_REQUIRE_BASH") == "1":
            pytest.fail("COMPANIONS_REQUIRE_BASH=1 but no bash (Git Bash on Windows) was found")
        pytest.skip("needs bash (Git Bash on Windows)")
    stubs, state, home, cfg, plugin = (tmp_path / n for n in ("stubs", "state", "home", "cfg", "plugin"))
    for d in (stubs, state, home, cfg, plugin / "bin"):
        d.mkdir(parents=True)
    _write(stubs / "claude", FAKE_CLAUDE)
    _write(stubs / "uv", FAKE_UV)
    _write(plugin / "bin" / "companions", FAKE_LAUNCHER)

    class Rig:
        settings = cfg / "settings.json"
        log = state / "log"

        def run(self, *args, claude=True, companions_home=None):
            if not claude:
                (stubs / "claude").unlink(missing_ok=True)
            env = dict(os.environ, HOME=str(home), CLAUDE_CONFIG_DIR=str(cfg), FAKE_STATE=str(state),
                       FAKE_PLUGIN_DIR=plugin.as_posix(), REAL_PY=Path(sys.executable).as_posix(),
                       STUBS=str(stubs), INSTALLER=str(INSTALL_SH), GIT_BIN=os.path.dirname(GIT))
            env.pop("COMPANIONS_HOME", None)
            if companions_home:
                env["COMPANIONS_HOME"] = companions_home
            # A PATH with the fakes first and only the system's own tools after them, so a real
            # claude or uv on this machine is never reached.
            script = ('p() { if command -v cygpath >/dev/null 2>&1; then cygpath -u "$1"; else printf %s "$1"; fi; }; '
                      'export PATH="$(p "$STUBS"):$(p "$GIT_BIN"):/usr/bin:/bin"; '
                      'exec bash "$(p "$INSTALLER")" "$@"')
            return subprocess.run([BASH, "-c", script, "install", *args], env=env, capture_output=True,
                                  text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=120)

    return Rig()


def test_installs_the_plugin_and_merges_the_rules_into_existing_settings(rig):
    rig.settings.write_text(json.dumps({"theme": "dark", "permissions": {"allow": ["Bash(git status)"]}}),
                            encoding="utf-8")
    r = rig.run("--yes")
    assert r.returncode == 0, r.stdout + r.stderr
    log = rig.log.read_text(encoding="utf-8")
    assert "plugin marketplace add Vudepchai2/sprint-companions" in log
    assert "plugin install sprint-companions@sprint-companions --scope user" in log
    assert "engine ready: companions 0.1.0" in r.stdout
    data = json.loads(rig.settings.read_text(encoding="utf-8"))
    assert data["theme"] == "dark"
    assert data["permissions"]["allow"] == ["Bash(git status)", *RULES, "Edit(~/SprintCompanions/**)"]
    assert "Sprint companions is ready" in r.stdout and "/tt" in r.stdout


def test_running_it_again_updates_instead_of_reinstalling_and_adds_no_duplicate_rules(rig):
    assert rig.run("--yes").returncode == 0
    rig.log.write_text("", encoding="utf-8")
    r = rig.run("--yes")
    assert r.returncode == 0, r.stdout + r.stderr
    log = rig.log.read_text(encoding="utf-8")
    assert "marketplace add" not in log and "plugin install" not in log
    assert "plugin marketplace update sprint-companions" in log
    assert "plugin update sprint-companions@sprint-companions" in log
    assert "rules already there" in r.stdout
    allow = json.loads(rig.settings.read_text(encoding="utf-8"))["permissions"]["allow"]
    assert len(allow) == len(set(allow)) == 3


def test_without_claude_code_it_stops_and_points_to_the_install_page(rig):
    r = rig.run("--yes", claude=False)
    assert r.returncode == 1
    assert "claude.com/claude-code" in r.stderr
    assert not rig.settings.exists()


def test_a_settings_file_that_isnt_json_is_left_alone(rig):
    rig.settings.write_text("{not json", encoding="utf-8")
    r = rig.run("--yes")
    assert r.returncode == 0, r.stdout + r.stderr
    assert rig.settings.read_text(encoding="utf-8") == "{not json"
    assert "left it alone" in r.stdout and "/permissions" in r.stdout


def test_the_memory_rule_follows_companions_home(rig):
    r = rig.run("--yes", companions_home="/data/sprint")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Edit(/data/sprint/**)" in json.loads(rig.settings.read_text(encoding="utf-8"))["permissions"]["allow"]


def test_install_sh_runs_everything_from_main_so_curl_pipe_bash_is_safe():
    text = INSTALL_SH.read_text(encoding="utf-8")
    assert text.rstrip().endswith('main "$@"')
    assert "</dev/tty" in text  # questions read the keyboard, not the piped script


def test_install_ps1_never_exits_the_users_window_and_is_plain_ascii():
    text = INSTALL_PS1.read_text(encoding="utf-8")
    assert not re.search(r"(?im)^\s*exit\b", text)  # irm | iex runs in the user's own window
    assert text.isascii()  # Windows PowerShell 5.1 may decode a downloaded script as ANSI
    assert "SPRINT_COMPANIONS_YES" in text and "Read-Host" in text


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell")
def test_install_ps1_parses_in_windows_powershell():
    cmd = ("$e = $null; [System.Management.Automation.Language.Parser]::ParseFile("
           f"'{INSTALL_PS1}', [ref]$null, [ref]$e) | Out-Null; $e.Count")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and r.stdout.strip() == "0", r.stdout + r.stderr
