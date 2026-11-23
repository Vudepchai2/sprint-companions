"""The bin/companions launcher installs the pinned engine through uv and then runs it.

Every test uses a fake `uv` and a fake engine: nothing is downloaded or installed.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "plugin"
SHIM = ROOT / "bin" / "companions"
PIN = (ROOT / "engine-version.txt").read_text(encoding="utf-8").strip() if (ROOT / "engine-version.txt").exists() else "0.1.0"
DEFAULT_SPEC = f"git+https://github.com/Vudepchai2/sprint-companions@v{PIN}#subdirectory=engine"


GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"


def _is_git_bash(b: str) -> bool:
    try:
        r = subprocess.run([b, "-c", "echo $OSTYPE"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and r.stdout.strip().startswith(("msys", "cygwin"))


def _bash():
    """bash to run the launcher with: on Windows, Git Bash only (Claude Code runs hooks with it), never
    the WSL launcher in System32 that can come first on PATH."""
    if sys.platform != "win32":
        return shutil.which("bash")
    for b in (shutil.which("bash"), GIT_BASH):
        if b and os.path.isfile(b) and "system32" not in b.lower() and _is_git_bash(b):
            return b
    return None


BASH = _bash()


@pytest.fixture(autouse=True)
def _needs_bash():
    """Without bash the whole suite would skip, and CI would go green with it unrun. So
    COMPANIONS_REQUIRE_BASH=1 (set in CI) turns the skip into a failure."""
    if BASH is None:
        if os.environ.get("COMPANIONS_REQUIRE_BASH") == "1":
            pytest.fail("COMPANIONS_REQUIRE_BASH=1 but no bash (Git Bash on Windows) was found")
        pytest.skip("needs bash (Git Bash on Windows)")

# Like real uv: tools go to $UV_TOOL_BIN_DIR, else ~/.local/bin (the folder uv's installer puts on PATH).
# It prints the bin dir exactly as given, so on Windows the shim must convert a Windows path back.
FAKE_UV = r"""#!/bin/bash
set -eu
printf '%s\n' "$*" >> "$UV_LOG"
printf '%s|%s\n' "${1:-} ${2:-}" "${UV_TOOL_BIN_DIR-<unset>}" >> "$UV_ENV_LOG"
bin="${UV_TOOL_BIN_DIR:-$HOME/.local/bin}"
if [ "${1:-} ${2:-} ${3:-}" = "tool dir --bin" ]; then
  if [ -n "${FAKE_UV_DIR_FAIL:-}" ]; then echo "error: no tool dir" >&2; exit 2; fi
  printf '%s\n' "$bin"
  exit 0
fi
if [ "${1:-} ${2:-}" = "tool install" ]; then
  if command -v cygpath >/dev/null 2>&1; then bin="$(cygpath -u "$bin")"; fi
  mkdir -p "$bin"
  for last in "$@"; do :; done
  ver="${last##*@v}"
  printf '%s\n' "${ver%%#*}" > "$bin/fake-version"
  cp "$FAKE_ENGINE_SRC" "$bin/companions"
  chmod +x "$bin/companions"
  echo "Installed 1 executable: companions"
  exit 0
fi
echo "fake uv: unexpected $*" >&2
exit 9
"""

# Prints its version with a Windows line ending, as a Windows Python would through a pipe.
FAKE_ENGINE = r"""#!/bin/bash
here="${0%/*}"
if [ "${1:-}" = "version" ]; then
  v="$(<"$here/fake-version")"
  printf 'companions %s\r\n' "$v"
  exit 0
fi
if [ "${1:-}" = "hook" ] && [ "${2:-}" = "prompt" ]; then
  if [ -n "${FAKE_ENGINE_SLEEP:-}" ]; then sleep "$FAKE_ENGINE_SLEEP"; fi
  if [ -n "${STDIN_LOG:-}" ]; then cat > "$STDIN_LOG"; else cat > /dev/null; fi  # like the real engine
fi
out="ENGINE"
for a in "$@"; do out="$out [$a]"; done
printf '%s\n' "$out"
printf '%s\n' "$out" >> "$UV_LOG"
"""

# What the fake engine logs for one prompt: the launcher starts it in the background, reading the hook's stdin.
PROMPT_CALL = "ENGINE [hook] [prompt]"

OLD_ENGINE = "#!/bin/bash\necho 'companions 0.0.9'\necho OLD-ENGINE-RAN\n"


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    path.chmod(0o755)
    return path


def _same(a, b) -> bool:
    return os.path.normcase(os.path.normpath(str(a))) == os.path.normcase(os.path.normpath(str(b)))


class Rig:
    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.fakebin = tmp / "fakebin"
        self.empty = tmp / "empty"
        self.home = tmp / "home"
        self.toolbin = self.home / ".sprint-companions" / "engine-bin"  # the shim's default private bin
        self.local_bin = self.home / ".local" / "bin"  # where uv puts tools by default; on PATH
        self.data = tmp / "data"  # COMPANIONS_HOME: quiet notes are on unless a test says otherwise
        self.log = tmp / "uv.log"
        self.env_log = tmp / "uv-env.log"
        for d in (self.fakebin, self.empty, self.home, self.data):
            d.mkdir()
        self.notes("on")
        self.log.write_text("", encoding="utf-8")
        self.env_log.write_text("", encoding="utf-8")
        _write(self.fakebin / "uv", FAKE_UV)
        self.engine_src = _write(tmp / "engine-src", FAKE_ENGINE)
        # The shim runs from a copy in a uniquely named folder, so a runaway loop can be found and killed.
        self.marker = f"shimrig-{uuid.uuid4().hex[:12]}"
        plugin = tmp / self.marker
        _write(plugin / "bin" / "companions", SHIM.read_bytes().decode("utf-8"))
        shutil.copyfile(ROOT / "engine-version.txt", plugin / "engine-version.txt")
        self.shim = plugin / "bin" / "companions"

    def install_engine(self, version: str, name: str = "companions", where: Path | None = None) -> None:
        where = where or self.toolbin
        where.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.engine_src, where / name)
        (where / name).chmod(0o755)
        (where / "fake-version").write_bytes(f"{version}\n".encode())
        (where / ".engine-pin").write_bytes(f"{version}\n".encode())  # as the launcher leaves it

    def notes(self, state: str | None, where: Path | None = None, text: str | None = None) -> None:
        """Write settings.json with quiet_notes set to `state` (None: no settings file at all)."""
        path = (where or self.data) / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        if state is None:
            path.unlink(missing_ok=True)
        else:
            path.write_text(text or json.dumps({"quiet_notes": state}, indent=2), encoding="utf-8")

    def env(self, path_dirs=None, **extra) -> dict:
        drop = ("COMPANIONS_ENGINE_URL", "COMPANIONS_SHIM_ACTIVE", "COMPANIONS_ENGINE_BIN", "UV_TOOL_BIN_DIR",
                "COMPANIONS_HOME")
        env = {k: v for k, v in os.environ.items() if k not in drop}
        dirs = [self.fakebin] if path_dirs is None else path_dirs
        tail = [] if path_dirs is not None else [os.environ.get("PATH", "")]
        env["PATH"] = os.pathsep.join([str(d) for d in dirs] + tail)
        env.update(HOME=str(self.home), COMPANIONS_HOME=str(self.data), UV_LOG=str(self.log), UV_ENV_LOG=str(self.env_log),
                   FAKE_ENGINE_SRC=str(self.engine_src), STDIN_LOG=str(self.tmp / "engine-stdin.txt"), **extra)
        return env

    def run(self, *args, env=None, timeout=30, input=None, wait_engine=True):
        # Output goes to files, not pipes: a runaway grandchild holding a pipe can't block the test.
        out_f, err_f = self.tmp / "stdout.txt", self.tmp / "stderr.txt"
        in_f = self.tmp / "stdin.txt"
        in_f.write_bytes(input.encode("utf-8") if input is not None else b"")
        with open(out_f, "wb") as out, open(err_f, "wb") as err, open(in_f, "rb") as inp:
            proc = subprocess.Popen([BASH, str(self.shim), *args], env=env or self.env(), stdout=out, stderr=err,
                                    stdin=inp, start_new_session=(os.name != "nt"))
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                _kill_tree(proc, self.marker)
                pytest.fail(f"shim did not finish within {timeout} s (a fork loop?)")
        if wait_engine and args[:2] == ("hook", "prompt"):
            self.wait_for_engine()
        read = lambda f: f.read_bytes().decode("utf-8").replace("\r\n", "\n")  # noqa: E731
        return proc.returncode, read(out_f), read(err_f)

    def wait_for_engine(self, timeout: float | None = None) -> None:
        """The prompt path starts the engine in the background and returns at once, so wait for the
        engine's log line: up to 10 s when one is due (stamp at the pin, notes on), and otherwise 1.5 s,
        long enough for a wrongly started fake engine to show up."""
        if timeout is None:
            timeout = 10.0 if self.engine_due() else 1.5
        end = time.monotonic() + timeout
        while not self.calls() and time.monotonic() < end:
            time.sleep(0.05)

    def engine_due(self) -> bool:
        stamp = self.toolbin / ".engine-pin"
        try:
            on = json.loads((self.data / "settings.json").read_text(encoding="utf-8")).get("quiet_notes") == "on"
        except (OSError, ValueError, AttributeError):
            on = False
        return on and stamp.is_file() and stamp.read_text(encoding="utf-8").strip() == PIN

    def calls(self) -> list[str]:
        return self.log.read_text(encoding="utf-8").splitlines()

    def installs(self) -> list[str]:
        return [c for c in self.calls() if c.startswith("tool install")]

    def bin_dirs(self) -> list[tuple[str, str]]:
        """(uv subcommand, UV_TOOL_BIN_DIR as that call saw it) for every uv call."""
        return [tuple(line.split("|", 1)) for line in self.env_log.read_text(encoding="utf-8").splitlines()]


def _kill_tree(proc, marker: str) -> None:
    """Kill the shim and everything it started. On Windows a looping bash child is re-parented,
    so taskkill /T can miss it: also kill every bash whose command line holds the rig's marker."""
    ps = ("$quiet = 0; for ($i = 0; $i -lt 80 -and $quiet -lt 8; $i++) {"
          f" $p = Get-CimInstance Win32_Process -Filter \"Name='bash.exe'\" | Where-Object {{ $_.CommandLine -like '*{marker}*' }};"
          " if ($p) { $quiet = 0; $p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } }"
          " else { $quiet++ }; Start-Sleep -Milliseconds 250 }")
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, timeout=60)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        subprocess.run(["pkill", "-KILL", "-f", marker], capture_output=True)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def test_missing_bash_skips_or_fails_when_required(monkeypatch):
    monkeypatch.setattr(sys.modules[__name__], "BASH", None)
    monkeypatch.delenv("COMPANIONS_REQUIRE_BASH", raising=False)
    with pytest.raises(pytest.skip.Exception):
        _needs_bash.__wrapped__()
    monkeypatch.setenv("COMPANIONS_REQUIRE_BASH", "1")
    with pytest.raises(pytest.fail.Exception):
        _needs_bash.__wrapped__()


@pytest.fixture
def rig(tmp_path):
    assert SHIM.is_file(), f"missing {SHIM}"
    return Rig(tmp_path)


def test_shim_installs_when_missing(rig):
    code, out, err = rig.run("analyse", "my session", "--latest")
    assert code == 0, err
    calls = rig.calls()
    assert f"tool install --force --python 3.12 {DEFAULT_SPEC}" in calls
    assert calls[-1] == "ENGINE [analyse] [my session] [--latest]"
    assert out == "ENGINE [analyse] [my session] [--latest]\n"  # uv's own output goes to stderr
    assert "Installed 1 executable" in err


def test_shim_installs_into_a_private_bin(rig):
    code, _, err = rig.run("status")
    assert code == 0, err
    seen = rig.bin_dirs()
    assert [cmd for cmd, _ in seen] == ["tool dir", "tool install"]
    for _, d in seen:  # set for both calls, as a Windows path on Windows, never uv's PATH folder
        assert _same(d, rig.toolbin) and not _same(d, rig.local_bin)
    assert (rig.toolbin / "companions").is_file()
    assert not rig.local_bin.exists()


def test_shim_honours_engine_bin_override(rig):
    custom = rig.tmp / "custom bin"
    code, out, err = rig.run("status", env=rig.env(COMPANIONS_ENGINE_BIN=str(custom)))
    assert code == 0, err
    assert rig.bin_dirs() and all(_same(d, custom) for _, d in rig.bin_dirs())
    assert (custom / "companions").is_file() and out == "ENGINE [status]\n"


def test_pin_holds_when_an_old_engine_is_earlier_on_path(rig):
    """Claude Code puts plugin bin/ folders after the user's PATH, where uv's installer adds ~/.local/bin.
    An old engine there is never run, upgraded or overwritten; the shim keeps the pin through its private bin."""
    old = _write(rig.local_bin / "companions", OLD_ENGINE)
    env = rig.env(path_dirs=[rig.local_bin, rig.shim.parent, rig.fakebin, os.environ.get("PATH", "")])
    code, out, err = rig.run("version", env=env)
    assert code == 0, err
    assert out.replace("\r", "") == f"companions {PIN}\n" and "OLD-ENGINE-RAN" not in out + err
    assert (rig.toolbin / "companions").is_file()
    assert old.read_text(encoding="utf-8") == OLD_ENGINE
    code, out, err = rig.run("status", env=env)  # a later session: still the pinned engine, no reinstall
    assert code == 0 and out == "ENGINE [status]\n"
    assert len(rig.installs()) == 1


def test_shim_reports_a_failing_uv_tool_dir(rig):
    code, out, err = rig.run("status", env=rig.env(FAKE_UV_DIR_FAIL="1"))
    assert code == 6 and out == ""
    assert "couldn't find uv's tool folder" in err
    assert rig.installs() == []


def test_shim_refuses_when_the_engine_bin_holds_itself(rig):
    code, out, err = rig.run("status", env=rig.env(COMPANIONS_ENGINE_BIN=str(rig.shim.parent)))
    assert code == 7 and out == ""
    assert "this plugin's own launcher" in err
    assert rig.installs() == []


def test_shim_skips_install_when_version_matches(rig):
    rig.install_engine(PIN)
    code, out, err = rig.run("status")
    assert code == 0, err
    assert rig.installs() == []
    assert out == "ENGINE [status]\n"


def test_shim_reinstalls_on_version_mismatch(rig):
    rig.install_engine("0.0.9")
    code, out, err = rig.run("version")
    assert code == 0, err
    assert f"tool install --force --python 3.12 {DEFAULT_SPEC}" in rig.calls()
    assert out.replace("\r", "") == f"companions {PIN}\n"


def test_shim_engine_url_override(rig):
    rig.install_engine("0.0.9")
    code, _, err = rig.run("status", env=rig.env(COMPANIONS_ENGINE_URL="file:///somewhere/repo"))
    assert code == 0, err
    # The override names a repo, like the default URL, so the engine's subfolder is added too:
    # the repo root has no pyproject.toml, and uv refuses it.
    assert f"tool install --force --python 3.12 git+file:///somewhere/repo@v{PIN}#subdirectory=engine" in rig.calls()


def test_shim_prefers_the_exe(rig):
    rig.install_engine(PIN, name="companions.exe")
    _write(rig.toolbin / "companions", "#!/bin/bash\necho WRONG\n")
    code, out, err = rig.run("status")
    assert code == 0, err
    assert out == "ENGINE [status]\n"


def test_shim_finds_uv_in_home_local_bin(rig):
    rig.install_engine(PIN)
    _write(rig.local_bin / "uv", FAKE_UV)
    dirs = [rig.empty]
    cygpath = shutil.which("cygpath")
    if cygpath:
        dirs.append(Path(cygpath).parent)
    code, out, err = rig.run("status", env=rig.env(path_dirs=dirs))
    assert code == 0, err
    assert out == "ENGINE [status]\n"
    assert "tool dir --bin" in rig.calls()


def test_shim_finds_uv_in_xdg_bin_home(rig):
    rig.install_engine(PIN)
    xdg = rig.tmp / "xdg-bin"
    _write(xdg / "uv", FAKE_UV)
    dirs = [rig.empty]
    xdg_value = str(xdg)
    cygpath = shutil.which("cygpath")
    if cygpath:
        dirs.append(Path(cygpath).parent)
        xdg_value = subprocess.run([cygpath, "-u", str(xdg)], capture_output=True, text=True).stdout.strip()
    code, out, err = rig.run("status", env=rig.env(path_dirs=dirs, XDG_BIN_HOME=xdg_value))
    assert code == 0, err
    assert out == "ENGINE [status]" + chr(10)
    assert "tool dir --bin" in rig.calls()


def test_shim_prints_uv_install_line_when_uv_missing(rig):
    code, out, err = rig.run("status", env=rig.env(path_dirs=[rig.empty]))
    assert code == 3
    text = out + err
    if sys.platform == "win32":
        assert 'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"' in text
    else:
        assert "curl -LsSf https://astral.sh/uv/install.sh | sh" in text
    assert rig.calls() == []


def test_shim_never_recurses(rig):
    rig.install_engine(PIN)
    env = rig.env(path_dirs=[rig.shim.parent, rig.fakebin, os.environ.get("PATH", "")])
    code, out, err = rig.run("hello", "world", env=env, timeout=20)
    assert code == 0, err
    assert out == "ENGINE [hello] [world]\n"


def test_shim_stops_when_reentered(rig):
    rig.install_engine(PIN)
    code, out, _ = rig.run("status", env=rig.env(COMPANIONS_SHIM_ACTIVE="1"))
    assert code == 5 and out == ""
    assert rig.calls() == []


def test_shim_is_committed_executable_with_lf():
    assert b"\r\n" not in SHIM.read_bytes()
    ls = subprocess.run(["git", "ls-files", "-s", str(SHIM)], capture_output=True, text=True, cwd=SHIM.parent)
    if ls.returncode != 0 or not ls.stdout:
        pytest.skip("not in a git checkout")
    assert ls.stdout.split()[0] == "100755"


# --- the hook fast path: a prompt hook never installs, never prints, never blocks ---

STDOUT_EXIT2_ENGINE = r"""#!/bin/bash
here="${0%/*}"
if [ "${1:-}" = "version" ]; then
  v="$(<"$here/fake-version")"
  printf 'companions %s\r\n' "$v"
  exit 0
fi
echo "Traceback: would become prompt context"
echo "usage: companions" >&2
echo "EXIT2-ENGINE" >> "$UV_LOG"
exit 2
"""


def test_hook_prompt_never_installs_and_exits_0_when_engine_missing(rig):
    code, out, err = rig.run("hook", "prompt")
    assert code == 0
    assert rig.calls() == []
    assert out == "" and err == ""


def test_hook_prompt_exits_0_when_uv_missing(rig):
    # With the engine installed, a missing uv alone keeps the launcher silent with exit 0.
    # The launcher stops at the uv check, so the engine does not run (its log line is absent).
    rig.install_engine(PIN)
    code, out, err = rig.run("hook", "prompt", env=rig.env(path_dirs=[rig.empty]))
    assert code == 0
    assert out == "" and err == ""
    assert rig.calls() == []


def test_hook_prompt_exits_0_when_engine_version_differs(rig):
    rig.install_engine("0.0.9")
    code, out, err = rig.run("hook", "prompt")
    assert code == 0
    assert rig.installs() == []
    assert out == "" and err == ""


def test_hook_prompt_never_calls_uv(rig):
    code, out, err = rig.run("hook", "prompt", env=rig.env(FAKE_UV_DIR_FAIL="1"))
    assert code == 0 and out == "" and err == ""
    assert rig.calls() == []
    rig.install_engine(PIN)
    code, out, err = rig.run("hook", "prompt", env=rig.env(FAKE_UV_DIR_FAIL="1"))
    assert code == 0 and out == "" and err == ""
    assert rig.installs() == [] and "tool dir --bin" not in rig.calls()
    assert rig.calls() == [PROMPT_CALL]  # only the fake engine logged; uv was never called


def test_hook_prompt_silent_when_engine_version_file_missing(rig):
    (rig.shim.parent.parent / "engine-version.txt").unlink()
    code, out, err = rig.run("hook", "prompt")
    assert code == 0 and out == "" and err == ""
    assert rig.calls() == []


def test_hook_prompt_silent_when_home_unset(rig):
    env = rig.env()
    env.pop("HOME")
    env.pop("COMPANIONS_ENGINE_BIN", None)
    code, out, err = rig.run("hook", "prompt", env=env)
    assert code == 0 and out == "" and err == ""


def test_hook_prompt_passes_stdin_to_the_engine(rig):
    rig.install_engine(PIN)
    payload = '{"prompt": "hello", "session_id": "abc"}'
    code, out, err = rig.run("hook", "prompt", input=payload)
    assert code == 0 and out == "" and err == ""
    assert (rig.tmp / "engine-stdin.txt").read_text(encoding="utf-8") == payload


def test_hook_session_start_keeps_engine_json_when_engine_exits_nonzero(rig):
    rig.install_engine(PIN)
    script = chr(10).join([
        "#!/bin/bash",
        'here="${0%/*}"',
        'if [ "${1:-}" = "version" ]; then echo "companions $(<"$here/fake-version")"; exit 0; fi',
        "echo '{\"hookSpecificOutput\": {}}'",
        "exit 1",
        "",
    ])
    _write(rig.toolbin / "companions", script)
    code, out, err = rig.run("hook", "session-start")
    assert code == 0
    assert out == '{"hookSpecificOutput": {}}' + chr(10)


def test_hook_prompt_exits_0_when_reentered(rig):
    rig.install_engine(PIN)
    code, out, err = rig.run("hook", "prompt", env=rig.env(COMPANIONS_SHIM_ACTIVE="1"))
    assert code == 0 and out == "" and err == ""
    assert rig.calls() == []


def test_hook_prompt_runs_engine_when_installed_at_pin(rig):
    rig.install_engine(PIN)
    code, out, err = rig.run("hook", "prompt")
    assert code == 0, err
    assert rig.installs() == []
    assert PROMPT_CALL in rig.calls()  # the engine ran; its stdout is discarded
    assert out == ""


def test_hook_prompt_discards_engine_output_and_exit_code(rig):
    rig.install_engine(PIN)
    _write(rig.toolbin / "companions", STDOUT_EXIT2_ENGINE)
    code, out, err = rig.run("hook", "prompt")
    assert code == 0
    assert out == "" and err == ""


def test_hook_session_start_installs_when_missing(rig):
    code, out, err = rig.run("hook", "session-start")
    assert code == 0, err
    assert len(rig.installs()) == 1
    assert rig.calls()[-1] == "ENGINE [hook] [session-start]"
    assert out == "ENGINE [hook] [session-start]\n"  # the engine's stdout is the hook output


def test_hook_session_start_exits_0_with_stderr_message_when_uv_missing(rig):
    code, out, err = rig.run("hook", "session-start", env=rig.env(path_dirs=[rig.empty]))
    assert code == 0 and out == ""
    assert "uv" in err


def test_hook_session_start_exits_0_when_install_fails(rig):
    broken = rig.tmp / "brokenbin"
    _write(broken / "uv", "#!/bin/bash\n"
           'if [ "${1:-} ${2:-} ${3:-}" = "tool dir --bin" ]; then echo "$UV_TOOL_BIN_DIR"; exit 0; fi\n'
           "echo boom; exit 1\n")
    code, out, err = rig.run("hook", "session-start", env=rig.env(path_dirs=[broken, os.environ.get("PATH", "")]))
    assert code == 0 and out == ""
    assert "couldn't install" in err


# The prompt path runs on every prompt. Each Python start costs 0.3-1.5 s on Windows, so the
# launcher checks the pin from a stamp file and quiet notes from settings.json in bash, and starts
# the engine only when notes are on.

def test_hook_prompt_trusts_the_stamp_and_skips_the_version_check(rig):
    rig.install_engine(PIN)
    (rig.toolbin / "fake-version").write_bytes(b"0.0.9\n")  # a `version` call would now say 0.0.9
    code, out, err = rig.run("hook", "prompt")
    assert code == 0 and out == "" and err == ""
    assert rig.calls() == [PROMPT_CALL]


def test_hook_prompt_does_nothing_without_a_matching_stamp(rig):
    rig.install_engine(PIN)
    (rig.toolbin / ".engine-pin").unlink()
    code, out, err = rig.run("hook", "prompt")
    assert code == 0 and out == "" and err == ""
    assert rig.calls() == []
    (rig.toolbin / ".engine-pin").write_bytes(b"0.0.9\n")
    assert rig.run("hook", "prompt")[0] == 0
    assert rig.calls() == []


@pytest.mark.parametrize("state", ["off", "asked", "unset", None, "damaged"])
def test_hook_prompt_starts_no_engine_unless_notes_are_on(rig, state):
    rig.install_engine(PIN)
    if state == "damaged":
        rig.notes("on", text='{"quiet_notes": "o')
    else:
        rig.notes(state)
    code, out, err = rig.run("hook", "prompt")
    assert code == 0 and out == "" and err == ""
    assert rig.calls() == []


def test_hook_prompt_reads_compact_settings_too(rig):
    rig.install_engine(PIN)
    rig.notes("on", text='{"bank":"me","quiet_notes":"on"}')
    assert rig.run("hook", "prompt")[0] == 0
    assert rig.calls() == [PROMPT_CALL]


def test_hook_prompt_finds_settings_in_the_default_data_folder(rig):
    rig.install_engine(PIN)
    rig.notes(None)
    rig.notes("on", where=rig.home / "SprintCompanions")
    env = rig.env()
    env.pop("COMPANIONS_HOME")
    env["USERPROFILE"] = str(rig.home)  # Python's Path.home() on Windows
    assert rig.run("hook", "prompt", env=env, wait_engine=False)[0] == 0
    rig.wait_for_engine(timeout=10)
    assert rig.calls() == [PROMPT_CALL]


def test_install_writes_the_stamp(rig):
    code, _, err = rig.run("status")
    assert code == 0, err
    assert (rig.toolbin / ".engine-pin").read_text(encoding="utf-8").strip() == PIN


def test_a_matching_engine_gets_its_stamp_back(rig):
    rig.install_engine(PIN)
    (rig.toolbin / ".engine-pin").unlink()
    code, _, err = rig.run("hook", "session-start")
    assert code == 0, err
    assert rig.installs() == []
    assert (rig.toolbin / ".engine-pin").read_text(encoding="utf-8").strip() == PIN


# The prompt path hands the payload to a background engine on the hook's own stdin, so the sprinter
# waits for bash, never for a Python start, and the raw prompt never touches disk before the secret
# filter has run.

def _tree(folder: Path) -> list[str]:
    return sorted(str(p.relative_to(folder)) for p in folder.rglob("*")) if folder.exists() else []


def test_hook_prompt_returns_before_the_engine_finishes(rig):
    rig.install_engine(PIN)
    # Pipes, as Claude Code reads a hook: a background engine holding them would block the return.
    payload = b'{"prompt": "hi"}'
    start = time.monotonic()
    r = subprocess.run([BASH, str(rig.shim), "hook", "prompt"], input=payload, capture_output=True,
                       env=rig.env(FAKE_ENGINE_SLEEP="5"), timeout=30)
    took = time.monotonic() - start
    assert r.returncode == 0 and r.stdout == b"" and r.stderr == b""
    assert took < 3, f"the hook waited {took:.1f} s for the engine"
    assert rig.calls() == []  # still asleep
    rig.wait_for_engine(timeout=15)
    assert rig.calls() == [PROMPT_CALL]
    assert (rig.tmp / "engine-stdin.txt").read_bytes() == payload  # it read the hook's stdin after the hook returned


def test_hook_prompt_reads_its_whole_stdin_before_it_returns(rig):
    """Claude Code drops whatever it hasn't written to a hook's stdin once the hook exits, and a pipe holds
    only about 64 KB. So the launcher takes the whole payload before it returns, even while the engine
    hasn't started reading yet; otherwise a long paste reaches the engine cut short and its note is lost."""
    import threading
    rig.install_engine(PIN)
    payload = json.dumps({"prompt": "a long paste " + "y" * 300_000}).encode("utf-8")
    proc = subprocess.Popen([BASH, str(rig.shim), "hook", "prompt"], stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=rig.env(FAKE_ENGINE_SLEEP="5"))
    written = threading.Event()

    def feed():
        try:
            proc.stdin.write(payload)
            proc.stdin.close()
            written.set()
        except OSError:
            pass

    threading.Thread(target=feed, daemon=True).start()
    assert proc.wait(timeout=30) == 0
    assert written.wait(1), "the hook returned before it had read all of its stdin"
    rig.wait_for_engine(timeout=20)
    assert rig.calls() == [PROMPT_CALL]
    assert (rig.tmp / "engine-stdin.txt").read_bytes() == payload


def test_hook_prompt_hands_the_payload_to_the_engine_on_stdin_and_writes_nothing(rig):
    rig.install_engine(PIN)
    before = _tree(rig.data)
    payload = json.dumps({"prompt": "first clinic signed, €200/month " + "x" * 50000, "session_id": "abc"},
                         ensure_ascii=False)
    code, out, err = rig.run("hook", "prompt", input=payload)
    assert code == 0 and out == "" and err == ""
    assert rig.calls() == [PROMPT_CALL]
    assert (rig.tmp / "engine-stdin.txt").read_bytes() == payload.encode("utf-8")  # byte for byte
    assert _tree(rig.data) == before  # the launcher keeps no copy of the prompt anywhere


def test_hook_prompt_is_silent_and_exits_0_when_the_engine_cant_start(rig):
    rig.install_engine(PIN)
    (rig.toolbin / "companions").write_bytes(b"\x7fELF not a program")
    (rig.toolbin / "companions").chmod(0o755)
    code, out, err = rig.run("hook", "prompt", input='{"prompt": "hi"}', wait_engine=False)
    assert code == 0 and out == "" and err == ""


def test_hook_prompt_with_the_real_engine_keeps_the_note_and_no_raw_copy(rig):
    """End to end: the real engine, started in the background, reads the hook's stdin and keeps the note
    with the secret removed. The raw key is in no file under the data folder."""
    py = Path(sys.executable).as_posix()
    engine_dir = (ROOT.parent / "engine").as_posix()
    rig.install_engine(PIN)
    _write(rig.toolbin / "companions", f'#!/bin/bash\nPYTHONPATH="{engine_dir}" "{py}" -m companions "$@"\n'
                                       'echo REAL-ENGINE-DONE >> "$UV_LOG"\n')
    key = "sk-" + "x" * 30
    payload = json.dumps({"prompt": f"use this key: {key}", "cwd": "/w/clinic-app", "session_id": "abc"})
    code, out, err = rig.run("hook", "prompt", input=payload, wait_engine=False)
    assert code == 0 and out == "" and err == ""
    end = time.monotonic() + 30
    while "REAL-ENGINE-DONE" not in rig.calls() and time.monotonic() < end:
        time.sleep(0.1)
    notes = [json.loads(line) for f in sorted((rig.data / "notes" / "inbox").glob("*.jsonl"))
             for line in f.read_text(encoding="utf-8").splitlines()]
    assert [n["text"] for n in notes] == ["use this key: [removed]"]
    for f in rig.data.rglob("*"):
        assert not f.is_file() or key.encode() not in f.read_bytes(), f
