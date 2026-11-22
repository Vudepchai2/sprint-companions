import json
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / "plugin"
HOOKS = PLUGIN / "hooks" / "hooks.json"

EXPECTED = {"hooks": {
    "SessionStart": [{"hooks": [{"type": "command",
        "command": "\"${CLAUDE_PLUGIN_ROOT}/bin/companions\" hook session-start"}]}],
    "UserPromptSubmit": [{"hooks": [{"type": "command",
        "command": "\"${CLAUDE_PLUGIN_ROOT}/bin/companions\" hook prompt", "timeout": 10}]}],
}}


def test_hooks_json_parses_and_matches_exactly():
    assert json.loads(HOOKS.read_text(encoding="utf-8")) == EXPECTED


def test_hook_commands_point_at_the_launcher():
    data = json.loads(HOOKS.read_text(encoding="utf-8"))
    for groups in data["hooks"].values():
        for group in groups:
            for hook in group["hooks"]:
                assert hook["command"].startswith('"${CLAUDE_PLUGIN_ROOT}/bin/companions" hook ')
    assert (PLUGIN / "bin" / "companions").is_file()


def test_manifests_name_the_plugin():
    plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert (plugin["name"], plugin["version"], plugin["license"]) == ("sprint-companions", "0.1.0", "Apache-2.0")
    assert (PLUGIN / "engine-version.txt").read_text(encoding="utf-8").strip() == plugin["version"]
    market = json.loads((PLUGIN.parent / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert market["plugins"][0]["name"] == "sprint-companions" and market["plugins"][0]["source"] == "./plugin"
