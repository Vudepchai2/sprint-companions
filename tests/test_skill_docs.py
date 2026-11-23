import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin"
REFS = PLUGIN / "references"
CODES = ["tt", "ks", "mm", "mr"]

ROUTING = {
    "tt": 'Use when the sprinter asks "what if" about their startup (what if we gave it away, went bigger, changed '
          "the customer), wants ideas, a brainstorm or a bold alternative for their startup or demo-day story, or "
          "calls on TT by name. Also the first companion for a sprinter with no memory "
          "yet. Only when they ask for a view, never for coding tasks.",
    "ks": "Use when the sprinter asks for a view on product, business model, pricing, unit economics, revenue or the "
          "money side of their demo-day story, or calls on KS by name. A \"what if\" idea about the model, such as "
          "giving the product away, goes to TT first. Only when they ask for a view, never for "
          "coding tasks such as building a pricing page.",
    "mm": "Use when the sprinter asks about fundraising, investors, how much to raise, the pitch, ambition, or wants "
          "an honest check on their demo-day story, or calls on MM by name. Only when they ask for a view, never for "
          "coding tasks.",
    "mr": "Use when the sprinter asks about their team, cofounders, hiring, people questions, or what the research or "
          "evidence says, or calls on MR by name. Only when they ask for a view, never for coding tasks.",
}
BASE_HEADINGS = ["## Before you answer: catch up", "## First meeting", "## How deep to go",
                 "## The take", "## Never", "## Handing over"]
REAL_NAMES = ["Tai", "Tran", "Kasper", "Suomalainen", "Marten", "Mickos", "Maija", "Renko"]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _frontmatter(text: str) -> tuple[dict, str]:
    assert text.startswith("---\n"), "SKILL.md must start with frontmatter"
    head, body = text[4:].split("\n---\n", 1)
    fields = {}
    for line in head.splitlines():
        key, _, value = line.partition(": ")
        fields[key] = value
    return fields, body


def _section(text: str, heading: str) -> str:
    return text.split(heading + "\n", 1)[1].split("\n## ", 1)[0]


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).casefold()


@pytest.mark.parametrize("code", CODES)
def test_companion_frontmatter(code):
    fields, _ = _frontmatter(_read(PLUGIN / "skills" / code / "SKILL.md"))
    assert fields["name"] == code
    assert fields["description"] == ROUTING[code]
    # Write is for <bank>/batch.json: a heredoc batch is stopped for approval despite Bash(companions *).
    assert fields["allowed-tools"] == "Bash(companions *), Read, Write"


@pytest.mark.parametrize("code", CODES)
def test_companion_body_points_at_base_persona_memory(code):
    _, body = _frontmatter(_read(PLUGIN / "skills" / code / "SKILL.md"))
    for path in ("${CLAUDE_SKILL_DIR}/persona.md",
                 "${CLAUDE_SKILL_DIR}/../../references/base.md",
                 "${CLAUDE_SKILL_DIR}/../../references/memory.md",
                 "${CLAUDE_SKILL_DIR}/../../references/questions.md"):
        assert path in body
    assert "${CLAUDE_SESSION_ID}" in body


def test_base_has_required_sections():
    text = _read(REFS / "base.md")
    positions = [text.find("\n" + h + "\n") for h in BASE_HEADINGS]
    assert all(p >= 0 for p in positions), dict(zip(BASE_HEADINGS, positions))
    assert positions == sorted(positions)


def test_base_catch_up_asks_about_unknown_projects():
    catch_up = _section(_read(REFS / "base.md"), "## Before you answer: catch up")
    for needle in ("unknown_projects", "companions notes project", "companions bank --ensure",
                   "companions notes read", "companions notes done --through", '"kind":"build"',
                   '"by":"notes"', "companions memory brief", "companions memory gaps"):
        assert needle in catch_up


def test_base_invites_customer_call_habit():
    assert "after a customer call" in _read(REFS / "base.md")


def test_base_first_meeting_uses_the_exact_opt_in_question():
    first = _section(_read(REFS / "base.md"), "## First meeting")
    assert ("Want the companions to keep up with your build sessions? They only keep what you type, "
            "on this machine. You can turn it off any time.") in first
    assert "companions notes status" in first


def test_base_never_covers_scores_questions_coding_and_invention():
    never = _section(_read(REFS / "base.md"), "## Never").casefold()
    for needle in ("score", "more than one question", "coding", "invent", "citation", "decide"):
        assert needle in never


def test_memory_md_rules():
    text = _read(REFS / "memory.md")
    for needle in ('"kind": "build"', '"by"', "sessions/${CLAUDE_SESSION_ID}", '"format"',
                   "no records about named individuals"):
        assert needle in text
    assert "storycoach" not in text and "transcript" not in text.casefold()


def test_batches_go_through_the_bank_batch_file_never_the_command_line():
    # Claude Code stops a heredoc with JSON in it for approval ("brace with quote character"),
    # even under Bash(companions *), so batches are written to <bank>/batch.json with Write.
    for name in ("base.md", "memory.md"):
        text = _read(REFS / name)
        assert 'companions memory retain "<bank>" "<bank>/batch.json"' in text, name
        assert "<<'EOF'" not in text and "retain \"<bank>\" -" not in text, name


def test_base_bans_shell_variables_and_powershell():
    catch_up = _section(_read(REFS / "base.md"), "## Before you answer: catch up")
    assert "Never set a shell variable" in catch_up
    assert "never PowerShell" in catch_up


def test_opt_in_is_asked_while_unset_and_marked_once_really_asked():
    first = _section(_read(REFS / "base.md"), "## First meeting")
    # The session-start note marks nothing: the question stays open while notes are `unset`, and the
    # companion that really puts it runs `companions notes asked` in that turn, so no one asks twice.
    assert "only if `companions notes status` printed `unset` at catch-up" in first
    assert "run `companions notes asked`" in first
    assert first.index("run `companions notes asked`") < first.index("never ask it again")
    assert "`asked`, `on` or `off`" in first
    assert "session-start note" not in first


def test_my_memory_switching_notes_answers_the_opt_in():
    text = _read(PLUGIN / "skills" / "my-memory" / "SKILL.md")
    assert "companions notes on" in text and "companions notes off" in text
    assert "answers the opt-in question too" in text


def test_catch_up_is_gated_on_notes_being_on_and_notes_the_session_before_done():
    catch_up = _section(_read(REFS / "base.md"), "## Before you answer: catch up")
    assert catch_up.index("companions notes status") < catch_up.index("companions notes read")
    assert '"project":"<project>"' in catch_up
    assert "whenever `through` isn't null" in catch_up
    assert catch_up.index("Note the `session`") < catch_up.index("companions notes done")


def test_one_fallback_ref_form_in_both_files():
    for name in ("base.md", "memory.md"):
        text = _read(REFS / name)
        assert "sessions/day-" in text, name
        assert "-<code>`" not in text and "notes-<date>" not in text, name


def test_memory_md_worked_example_runs_through_the_engine(tmp_path):
    text = _read(REFS / "memory.md")
    batches = re.findall(r"```json\n(.*?)\n```\n", text, re.S)
    batches = [b for b in batches if '"items": [ ... ]' not in b]
    assert len(batches) == 5
    env = {**os.environ, "PYTHONPATH": str(ROOT / "engine"), "COMPANIONS_HOME": str(tmp_path)}

    def cli(*args, input=None):
        r = subprocess.run([sys.executable, "-m", "companions", *args], capture_output=True, env=env,
                           input=input)
        assert r.returncode == 0, r.stderr.decode("utf-8")
        return r.stdout.decode("utf-8")

    bank = cli("bank", "--ensure", "--name", "Example").strip()
    reports = [json.loads(cli("memory", "retain", bank, "-",
                              input=b.replace("${CLAUDE_SESSION_ID}", "live1").encode("utf-8")))
               for b in batches]
    assert reports[1]["conflicts"][0]["id"] == "x1"
    assert reports[1]["conflicts"][0]["claims"] == ["c1", "c2"]
    first = (Path(bank) / "log.jsonl").read_text(encoding="utf-8").splitlines()[0]
    assert json.loads(first)["source"]["project"] == "clinic-app"


def test_questions_md_has_openers_angles_and_every_gap_section():
    text = _read(REFS / "questions.md")
    assert len(re.findall(r"^- ", _section(text, "## Openers"), re.M)) >= 5
    assert len(re.findall(r"^- ", _section(text, "## Angles"), re.M)) >= 3
    sys.path.insert(0, str(ROOT / "engine"))
    try:
        from companions.memory.recall import GAP_SECTIONS
    finally:
        sys.path.remove(str(ROOT / "engine"))
    for name in set(GAP_SECTIONS.values()):
        assert f"\n## {name}\n" in text, name


def test_no_real_names_outside_persona_files():
    allowed = {PLUGIN / "skills" / code / "persona.md" for code in CODES}
    pattern = re.compile(r"\b(" + "|".join(_fold(n) for n in REAL_NAMES) + r")\b")
    hits = []
    for path in PLUGIN.rglob("*"):
        if not path.is_file() or path in allowed:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if pattern.search(_fold(line)):
                hits.append(f"{path.relative_to(PLUGIN)}:{n}: {line.strip()}")
    assert hits == []


def test_no_real_names_check_folds_accents():
    pattern = re.compile(r"\b(" + "|".join(_fold(n) for n in REAL_NAMES) + r")\b")
    assert pattern.search(_fold("inspired by Mårten"))
    assert pattern.search(_fold("MARTEN said"))


def test_skill_docs_use_lf():
    for path in [*REFS.glob("*.md"), *(PLUGIN / "skills").glob("*/SKILL.md")]:
        assert b"\r\n" not in path.read_bytes(), path


UTILITY = {
    "my-memory": ("Use when the sprinter asks what the companions or you know or remember about them (\"what do you "
               "remember about me?\"), wants to see, correct or delete their memory, or wants to turn quiet notes on "
               "or off. This is their sprint memory, kept by the companions: use it rather than answering from Claude "
               "Code's own memory files.",
               "Bash(companions *), Read, Write"),
    "demo-brief": ("Use when the sprinter wants to prepare for demo day or another pitch: a draft script, the story, "
              "proof points, or who will be in the audience, or calls /demo-brief.",
              "Bash(companions *), Read, Write"),
    "panel": ("Use when the sprinter asks what the other companions, everyone, or the panel thinks about a "
              "question, or calls /panel.",
              "Bash(companions *), Read, Write, Agent"),
}


def _utility_body(name: str) -> str:
    return _frontmatter(_read(PLUGIN / "skills" / name / "SKILL.md"))[1]


@pytest.mark.parametrize("name", sorted(UTILITY))
def test_utility_frontmatter(name):
    fields, body = _frontmatter(_read(PLUGIN / "skills" / name / "SKILL.md"))
    description, tools = UTILITY[name]
    assert fields["name"] == name
    assert fields["description"] == description
    assert fields["allowed-tools"] == tools
    assert "${CLAUDE_SKILL_DIR}/../../references/base.md" in body
    assert "${CLAUDE_SKILL_DIR}/../../references/memory.md" in body
    assert "coach" not in body.casefold()


def test_memory_contract():
    body = _utility_body("my-memory")
    for needle in ("12 lines", "Your sprint so far", "companions memory brief", "companions memory gaps",
                   "pages/", "companions memory forget", "companions memory delete", "companions notes off",
                   "companions notes project", "companions memory recall", "the same `about` and the same `key`"):
        assert needle in body, needle
    said_twice = body.split("**Said more than once:**", 1)[1].split("**Conflicts:**", 1)[0]
    assert "`corroborated`" in said_twice and "only those" in said_twice


def test_panel_contract():
    body = _utility_body("panel")
    for needle in ("2–4 lines", "Where they disagree:", "From your memory:",
                   "Your call. Want to go deeper with one of them?", "companions memory brief",
                   "Never decide.", 'companions memory recall "<bank>" --query', "recall excerpt",
                   "Strip any question it ends with"):
        assert needle in body, needle
    for code in CODES:
        assert f"${{CLAUDE_SKILL_DIR}}/../{code}/persona.md" in body, code
    block = re.search(r"```\n(\s*Panel · .*?Your call\. Want to go deeper with one of them\?)\n", body, re.S).group(1)
    rows = [line.split()[0] for line in block.splitlines()[1:5]]
    assert rows == [code.upper() for code in CODES]


def test_brief_contract():
    body = _utility_body("demo-brief")
    for needle in ("companions memory demo-brief", '"occasion"', '"script"', '"cites"', '"proof"',
                   '"before_stage"', '"fields": {"format"', "150 words per minute", "brief-plan.json",
                   "Read it aloud and tell me which line felt wrong", "fewer than 3",
                   "never run `demo-brief` with an empty script", "isn't rewording a number",
                   "Read it first", "`Brief · Demo day` until the occasion is known"):
        assert needle in body, needle
    assert "every number in a line must come from a cited record" in body.casefold()


def test_brief_example_plan_runs_through_the_engine(tmp_path):
    """The plan shape the brief skill shows is accepted, and an uncited number is rejected."""
    body = _utility_body("demo-brief")
    plan_text = re.search(r"```json\n(.*?)\n```", body, re.S).group(1)
    env = {**os.environ, "PYTHONPATH": str(ROOT / "engine"), "COMPANIONS_HOME": str(tmp_path)}

    def cli(*args, input=None, ok=True):
        r = subprocess.run([sys.executable, "-m", "companions", *args], capture_output=True, env=env,
                           input=input)
        assert (r.returncode == 0) == ok, r.stderr.decode("utf-8")
        return r.stdout.decode("utf-8"), r.stderr.decode("utf-8")

    bank = cli("bank", "--ensure", "--name", "Example")[0].strip()
    batch = {
        "source": {"kind": "said", "ref": "sessions/live1", "at": "2026-11-23", "by": "mm"},
        "items": [
            {"type": "moment", "ref": "@signed", "title": "First clinic signed",
             "what_happened": "The first clinic signed up, at €200 a month.",
             "quotes": ["first clinic signed, €200/month"]},
            {"type": "claim", "about": "@signed", "key": "monthly_price",
             "statement": "The first clinic pays €200 a month.", "value": 200, "unit": "EUR per month",
             "quote": "first clinic signed, €200/month"},
            {"type": "occasion", "name": "Demo day", "format": "3-minute pitch with slides, no Q&A",
             "audience": "seed investors and corporates, they care about paying customers"},
        ],
    }
    cli("memory", "retain", bank, "-", input=json.dumps(batch).encode("utf-8"))
    plan = json.loads(plan_text)
    plan_file = Path(bank) / "brief-plan.json"
    plan_file.write_text(json.dumps(plan), encoding="utf-8")
    out, _ = cli("memory", "demo-brief", bank, str(plan_file))
    page = Path(out.strip())
    assert page == Path(bank) / "pages" / f"brief-{plan['occasion']}.md"
    assert ("Draft: in your words, from your memory. Change anything that doesn't sound like you."
            in page.read_text(encoding="utf-8"))
    page.unlink()
    plan["script"][0]["line"] += " We have 40 clinics waiting."
    plan_file.write_text(json.dumps(plan), encoding="utf-8")
    _, err = cli("memory", "demo-brief", bank, str(plan_file), ok=False)
    assert "beat 1: the number 40 is not in any record it cites" in err
    assert not page.exists()


@pytest.mark.parametrize("name", sorted(UTILITY))
def test_utility_skills_use_the_session_ref(name):
    assert "sessions/${CLAUDE_SESSION_ID}" in _utility_body(name)


@pytest.mark.parametrize("name", ["my-memory", "demo-brief"])
def test_fallback_by_gives_the_disclosure_before_the_first_retain(name):
    body = _utility_body(name)
    fallback = body.index("or `mm` if none has spoken")
    disclosure = body.index("give the disclosure line from its persona file")
    assert fallback < disclosure < fallback + 600
    assert "${CLAUDE_SKILL_DIR}/../<code>/persona.md" in body


# Claude Code's own slash commands win over a plugin skill of the same name: in Claude Code
# 2.1.312, `/memory` and `/brief` answered "isn't available in this environment" and never
# reached the plugin. Every skill needs a name of its own.
BUILT_IN_COMMANDS = {"memory", "brief", "help", "clear", "compact", "config", "context", "cost", "doctor",
                     "init", "login", "logout", "mcp", "model", "permissions", "plugin", "resume", "review",
                     "status", "agents", "hooks", "export", "usage", "plan", "skills", "statusline"}


def test_no_skill_shadows_a_claude_code_command():
    names = {p.parent.name for p in (PLUGIN / "skills").glob("*/SKILL.md")}
    assert names == {"tt", "ks", "mm", "mr", "panel", "my-memory", "demo-brief"}
    assert not names & BUILT_IN_COMMANDS
