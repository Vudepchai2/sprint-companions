#!/usr/bin/env bash
# Sprint companions installer for macOS and Linux (and Git Bash on Windows).
#
#   curl -fsSL https://raw.githubusercontent.com/Vudepchai2/sprint-companions/main/install.sh | bash
#
# It checks what you need, installs the plugin into Claude Code, installs the companions engine,
# and (after asking) adds three permission rules so the companions don't ask every time.
# It is safe to run again: every step skips itself when it's already done.
# Add --yes to answer yes to every question:  ... | bash -s -- --yes
set -euo pipefail

REPO="Vudepchai2/sprint-companions"
PLUGIN="sprint-companions@sprint-companions"
YES=0
for arg in "$@"; do
  case "$arg" in
    -y|--yes) YES=1 ;;
    -h|--help) sed -n '2,10p' "$0" 2>/dev/null | sed 's/^# \{0,1\}//'; exit 0 ;;
  esac
done

if [ -t 1 ]; then B=$'\033[1m'; G=$'\033[32m'; R=$'\033[31m'; N=$'\033[0m'; else B=""; G=""; R=""; N=""; fi
step() { printf '\n%s%s%s\n' "$B" "$*" "$N"; }
ok()   { printf '  %s✓%s %s\n' "$G" "$N" "$*"; }
info() { printf '  %s\n' "$*"; }
fail() { printf '\n  %s✗%s %s\n' "$R" "$N" "$1" >&2; shift; for l in "$@"; do printf '    %s\n' "$l" >&2; done; exit 1; }

# ask "question": yes on Enter. Reads the keyboard even when this script itself arrives on stdin
# (curl | bash). With no keyboard at all and no --yes, the answer is no.
ask() {
  if [ "$YES" = 1 ]; then printf '  %s [Y/n] y\n' "$1"; return 0; fi
  local a=""
  if { : </dev/tty; } 2>/dev/null; then
    printf '  %s [Y/n] ' "$1"; IFS= read -r a </dev/tty || a="n"
  else
    printf '  %s [Y/n] (no keyboard: no; rerun with --yes)\n' "$1"; return 1
  fi
  case "$a" in ""|y|Y|yes|Yes|YES) return 0 ;; *) return 1 ;; esac
}

# Everything runs inside main, so bash has read the whole script before any step starts:
# with curl | bash, a command that reads stdin can't swallow the rest of the script.
main() {
printf '%sSprint companions installer%s\n' "$B" "$N"
info "TT, KS, MM and MR: four AI companions for your demo-day story, inside Claude Code."

step "1/5  Claude Code"
command -v claude >/dev/null 2>&1 || fail "Claude Code isn't installed (no 'claude' command found)." \
  "Install it from https://claude.com/claude-code, open it once, then run this installer again."
ok "found $(claude --version 2>/dev/null | head -n1)"

step "2/5  Git"
if command -v git >/dev/null 2>&1; then
  ok "found $(git --version)"
else
  case "$(uname -s)" in
    Darwin) fail "Git isn't installed." "Run: xcode-select --install   (accept the prompt), then run this installer again." ;;
    *) fail "Git isn't installed." "Install it with your package manager (for example: sudo apt install git), then run this installer again." ;;
  esac
fi

step "3/5  uv (installs the companions engine and its Python)"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
if command -v uv >/dev/null 2>&1; then
  ok "found $(uv --version)"
else
  info "uv is a small installer for Python tools from astral.sh. It needs no admin rights."
  ask "Install uv now?" || fail "uv is needed." "Install it yourself with: curl -LsSf https://astral.sh/uv/install.sh | sh" "Then run this installer again."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  command -v uv >/dev/null 2>&1 || fail "uv installed, but this terminal can't find it yet." "Open a new terminal and run this installer again."
  ok "installed $(uv --version)"
fi

step "4/5  The plugin"
if claude plugin marketplace list 2>/dev/null | grep -q "sprint-companions"; then
  claude plugin marketplace update sprint-companions >/dev/null 2>&1 || true
  ok "marketplace already added (refreshed)"
else
  claude plugin marketplace add "$REPO" || fail "Couldn't add the marketplace." "Check your internet connection and try again."
  ok "marketplace added"
fi
if claude plugin list 2>/dev/null | grep -q "$PLUGIN"; then
  claude plugin update "$PLUGIN" >/dev/null 2>&1 || true
  claude plugin enable "$PLUGIN" >/dev/null 2>&1 || true
  ok "plugin already installed (updated)"
else
  claude plugin install "$PLUGIN" --scope user || fail "Couldn't install the plugin." "Try again, or in Claude Code type: /plugin install $PLUGIN"
  ok "plugin installed"
fi

# Where Claude Code put the plugin: its launcher installs and runs the engine.
PLUGIN_DIR="$(claude plugin list --json 2>/dev/null | uv run --no-project --quiet --python 3.12 python -c '
import json, sys
try:
    data = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
items = data if isinstance(data, list) else data.get("plugins", [])
paths = [p.get("installPath", "") for p in items if p.get("id") == "sprint-companions@sprint-companions"]
print(paths[0] if paths else "")
' || true)"
[ -n "$PLUGIN_DIR" ] || fail "The plugin is installed, but I couldn't find its folder." "Start Claude Code: the engine installs itself at the first companion call."
if command -v cygpath >/dev/null 2>&1; then PLUGIN_DIR="$(cygpath -u "$PLUGIN_DIR")"; fi

info "Installing the companions engine (once; this can take a minute)..."
ENGINE_VERSION="$(bash "$PLUGIN_DIR/bin/companions" version 2>/dev/null </dev/null)" \
  || fail "The engine didn't install." "Check your internet connection, then run this installer again."
ok "engine ready: $ENGINE_VERSION"

step "5/5  Fewer permission prompts"
CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
SETTINGS="$CONFIG_DIR/settings.json"
if [ -n "${COMPANIONS_HOME:-}" ]; then MEM_RULE="Edit(${COMPANIONS_HOME}/**)"; else MEM_RULE="Edit(~/SprintCompanions/**)"; fi
info "Without these, Claude Code asks before each companion command. The rules let it:"
info "  Skill(sprint-companions:*)   call a companion when you ask for one"
info "  Bash(companions *)           run the companions engine"
info "  $MEM_RULE   save to your memory folder, and nowhere else"
info "They go into $SETTINGS. The companions still ask in the chat before deleting anything."
if ask "Add these three rules?"; then
  mkdir -p "$CONFIG_DIR"
  RESULT="$(uv run --no-project --quiet --python 3.12 python - "$SETTINGS" "Skill(sprint-companions:*)" "Bash(companions *)" "$MEM_RULE" <<'PY'
import json, os, sys
path, rules = sys.argv[1], sys.argv[2:]
data = {}
if os.path.exists(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            text = f.read()
        data = json.loads(text) if text.strip() else {}
    except ValueError:
        print("unreadable"); sys.exit(0)
if not isinstance(data, dict):
    print("unreadable"); sys.exit(0)
perms = data.setdefault("permissions", {})
if not isinstance(perms, dict):
    print("unreadable"); sys.exit(0)
allow = perms.setdefault("allow", [])
if not isinstance(allow, list):
    print("unreadable"); sys.exit(0)
added = [r for r in rules if r not in allow]
allow.extend(added)
if added:
    tmp = path + ".sprint-companions.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)
print(len(added))
PY
)" || RESULT="unreadable"
  case "$RESULT" in
    unreadable) info "Your settings file couldn't be read as JSON, so I left it alone."
                info "Add the rules yourself in Claude Code: type /permissions, choose Allow, and add them." ;;
    0) ok "rules already there" ;;
    *) ok "added $RESULT rule(s)" ;;
  esac
else
  info "Skipped. You can add them later in Claude Code: /permissions, then Allow."
fi

printf '\n%s✓ Sprint companions is ready.%s\n' "$G$B" "$N"
info "Open Claude Code in your startup's folder and type:  /tt"
}

main "$@"
