"""The bin/companions launcher installs the pinned engine through uv and then runs it.

Every test uses a fake `uv` and a fake engine: nothing is downloaded or installed.
"""
import os
import shutil
import signal
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "plugin"
SHIM = ROOT / "bin" / "companions"
PIN = (ROOT / "engine-version.txt").read_text(encoding="utf-8").strip() if (ROOT / "engine-version.txt").exists() else "0.1.0"
DEFAULT_SPEC = f"git+https://github.com/Vudepchai2/sprint-companions@v{PIN}#subdirectory=engine"


def _bash():
    b = shutil.which("bash")
    if b and sys.platform == "win32" and "system32" in b.lower():
        return None  # the WSL launcher, not Git Bash
    return b


BASH = _bash()
pytestmark = pytest.mark.skipif(BASH is None, reason="needs bash (Git Bash on Windows)")

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
out="ENGINE"
for a in "$@"; do out="$out [$a]"; done
printf '%s\n' "$out"
printf '%s\n' "$out" >> "$UV_LOG"
"""

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
        self.log = tmp / "uv.log"
        self.env_log = tmp / "uv-env.log"
        for d in (self.fakebin, self.empty, self.home):
            d.mkdir()
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

    def env(self, path_dirs=None, **extra) -> dict:
        drop = ("COMPANIONS_ENGINE_URL", "COMPANIONS_SHIM_ACTIVE", "COMPANIONS_ENGINE_BIN", "UV_TOOL_BIN_DIR")
        env = {k: v for k, v in os.environ.items() if k not in drop}
        dirs = [self.fakebin] if path_dirs is None else path_dirs
        tail = [] if path_dirs is not None else [os.environ.get("PATH", "")]
        env["PATH"] = os.pathsep.join([str(d) for d in dirs] + tail)
        env.update(HOME=str(self.home), UV_LOG=str(self.log), UV_ENV_LOG=str(self.env_log),
                   FAKE_ENGINE_SRC=str(self.engine_src), **extra)
        return env

    def run(self, *args, env=None, timeout=30):
        # Output goes to files, not pipes: a runaway grandchild holding a pipe can't block the test.
        out_f, err_f = self.tmp / "stdout.txt", self.tmp / "stderr.txt"
        with open(out_f, "wb") as out, open(err_f, "wb") as err:
            proc = subprocess.Popen([BASH, str(self.shim), *args], env=env or self.env(), stdout=out, stderr=err,
                                    stdin=subprocess.DEVNULL, start_new_session=(os.name != "nt"))
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                _kill_tree(proc, self.marker)
                pytest.fail(f"shim did not finish within {timeout} s (a fork loop?)")
        read = lambda f: f.read_bytes().decode("utf-8").replace("\r\n", "\n")  # noqa: E731
        return proc.returncode, read(out_f), read(err_f)

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
    code, _, err = rig.run("status", env=rig.env(COMPANIONS_ENGINE_URL="file:///somewhere/engine"))
    assert code == 0, err
    assert f"tool install --force --python 3.12 git+file:///somewhere/engine@v{PIN}" in rig.calls()


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
exit 2
"""


def test_hook_prompt_never_installs_and_exits_0_when_engine_missing(rig):
    code, out, err = rig.run("hook", "prompt")
    assert code == 0
    assert rig.calls() == []
    assert out == "" and err == ""


def test_hook_prompt_exits_0_when_uv_missing(rig):
    code, out, err = rig.run("hook", "prompt", env=rig.env(path_dirs=[rig.empty]))
    assert code == 0
    assert out == "" and err == ""


def test_hook_prompt_exits_0_when_engine_version_differs(rig):
    rig.install_engine("0.0.9")
    code, out, err = rig.run("hook", "prompt")
    assert code == 0
    assert rig.installs() == []
    assert out == "" and err == ""


def test_hook_prompt_exits_0_when_uv_tool_dir_fails(rig):
    code, out, err = rig.run("hook", "prompt", env=rig.env(FAKE_UV_DIR_FAIL="1"))
    assert code == 0 and out == "" and err == ""
    assert rig.installs() == []


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
    assert "ENGINE [hook] [prompt]" in rig.calls()  # the engine ran; its stdout is discarded
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
