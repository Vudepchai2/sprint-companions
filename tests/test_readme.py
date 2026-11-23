"""The README, the demo page and the art note: what a reviewer meets first."""
import re
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
DEMO = ROOT / "docs" / "demo.html"
ART = ROOT / "art" / "README.md"
CODES = ["tt", "ks", "mm", "mr"]
DISCLOSURE = {
    "tt": "I'm TT, an AI companion inspired by Tai Tran. I'm not him, and I don't speak for him.",
    "ks": "I'm KS, an AI companion inspired by Kasper Suomalainen. I'm not him, and I don't speak for him.",
    "mm": "I'm MM, an AI companion inspired by Mårten Mickos. I'm not him, and I don't speak for him.",
    "mr": "I'm MR, an AI companion inspired by Maija Renko. I'm not her, and I don't speak for her.",
}
NAMES = {"tt": "Tai Tran", "ks": "Kasper Suomalainen", "mm": "Mårten Mickos", "mr": "Maija Renko"}
NAME_WORDS = ["Tai", "Tran", "Kasper", "Suomalainen", "Marten", "Mickos", "Maija", "Renko"]
OPT_IN = ("Want the companions to keep up with your build sessions? They only keep what you type, "
          "on this machine. You can turn it off any time.")
STARTUP_Q = "Is `clinic-app` your startup? And `thesis-notes`?"
DRAFT_HEADER = "Draft: in your words, from your memory. Change anything that doesn't sound like you."
STATUSES = ("said", "corroborated", "confirmed", "conflicted")
COMPANION_TURNS = 16  # every companion turn in the demo, panel takes included


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).casefold()


def _outcome(code: str) -> str:
    text = _read(ROOT / "plugin" / "skills" / code / "persona.md")
    return text.split("## Outcome line\n", 1)[1].split("\n## ", 1)[0].strip()


def _section(text: str, heading: str) -> str:
    """The body of a `## heading` section, up to the next `## ` heading."""
    m = re.search(rf"^## {re.escape(heading)}[^\n]*\n", text, re.M)
    assert m, f"README has no '## {heading}' section"
    rest = text[m.end():]
    nxt = re.search(r"^## ", rest, re.M)
    return rest[:nxt.start()] if nxt else rest


def _without_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def test_readme_has_companions_and_disclosures():
    text = _read(README)
    for code in CODES:
        assert DISCLOSURE[code] in text, code
        assert _outcome(code) in text, code
        assert f"inspired by {NAMES[code]}" in text, code

    install = _section(text, "Install")
    for needle in ("/plugin marketplace add Vudepchai2/sprint-companions",
                   "/plugin install sprint-companions@sprint-companions",
                   "uv", "Git for Windows", "gh auth login", "gh auth setup-git"):
        assert needle in install, needle
    assert "private" in install.casefold()

    notes = _section(text, "Quiet notes")
    assert OPT_IN in notes
    assert STARTUP_Q in notes
    assert 'say "keep notes" to turn them on later' in notes  # the opt-in is asked once, then only on request

    assert "after a customer call" in text.casefold()

    privacy = _section(text, "Privacy")
    assert "~/SprintCompanions" in privacy and "COMPANIONS_HOME" in privacy
    assert "30 days" in privacy

    limits = _section(text, "Limits")
    assert "cofounders on separate laptops have separate memories" in limits.casefold()
    assert "voice" in limits.casefold() and "score" in limits.casefold()

    for heading in ("After a customer call", "/demo-brief", "/panel", "/my-memory", "Model"):
        _section(text, heading)
    assert DRAFT_HEADER in _section(text, "/demo-brief")
    assert "docs/demo.html" in text


def test_readme_has_no_ai_marten_link_or_todo():
    # The author decided: no AI Marten link in this README, not even a TODO.
    assert "AI Marten" not in _read(README)


@pytest.mark.parametrize("path", [README, DEMO], ids=lambda p: p.relative_to(ROOT).as_posix())
def test_quiet_notes_capture_is_described_honestly(path):
    """The hook keeps the whole typed prompt (secrets removed), so pasted code is kept too."""
    text = _without_comments(_read(path)).replace("&#39;", "'")
    flat = re.sub(r"<[^>]+>", "", text)
    assert "never keeps Claude's replies, tool output or code Claude writes" in flat
    assert re.search(r"type[sd]? or paste[sd]?", flat)
    assert "secrets removed" in flat
    # No claim that typed or pasted code is left out.
    for over_promise in (r"(?<![a-z])no code(?![a-z])", r"tool output (?:or|and) code(?! Claude writes)",
                         r"code (?:is|are) never kept", r"output and code are never"):
        assert not re.search(over_promise, flat, re.I), over_promise


@pytest.mark.parametrize("path", [README, DEMO, ART], ids=lambda p: p.relative_to(ROOT).as_posix())
def test_wording_and_real_names(path):
    text = _read(path)
    assert "coach" not in text.casefold()
    assert "\r" not in text
    # A real name appears only as "inspired by": every line that names one says so.
    names = {_fold(w) for w in NAME_WORDS}
    for n, line in enumerate(_without_comments(text).splitlines(), 1):
        if names & set(re.findall(r"[a-z]+", _fold(line))):
            assert "inspired by" in line, f"{path.name}:{n} names a real person outside 'inspired by'"


def test_demo_page_is_self_contained():
    html = _read(DEMO)
    assert html.lstrip().lower().startswith("<!doctype html>")
    assert '<meta name="viewport"' in html
    assert "prefers-color-scheme: dark" in html
    assert "<script" not in html.lower()
    assert not re.search(r"<link\b", html, re.I)
    assert "@import" not in html
    assert not re.search(r"""(src|href)\s*=\s*["']?(https?:)?//""", html, re.I)
    assert "url(" not in html


def test_demo_page_follows_the_product_rules():
    html = _read(DEMO)
    plain = html.replace("&#39;", "'").replace("&quot;", '"')
    for code in CODES:
        assert DISCLOSURE[code] in plain, code
        assert _outcome(code) in plain, code
        assert f"inspired by {NAMES[code]}" in plain, code
    assert OPT_IN in plain
    assert DRAFT_HEADER in plain
    assert "(caught up on your last 4 build sessions)" in plain
    assert "Your call. Want to go deeper with one of them?" in plain
    # Each status appears as a status, as the engine prints it ("· said ·", "· conflicted") or as
    # the panel shows it ("(corroborated)"), not just as an ordinary word.
    for status in STATUSES:
        assert re.search(rf"(?:·\s*|\(){status}(?=\s*·|\)|\s*<)", plain), status
    proof = plain.split("<h4>Proof</h4>", 1)[1].split("</ul>", 1)[0]
    order = [re.search(rf"· {s} ·", proof).start() for s in ("confirmed", "corroborated", "said")]
    assert order == sorted(order), "proof lists confirmed, then corroborated, then said"
    # Five moments, in the spec's order.
    moments = re.findall(r'<section class="moment" id="([a-z-]+)"', html)
    assert moments == ["catch-up", "routed", "memory-catch", "panel", "brief"]
    # The page says the transcripts are illustrative, with a fictional sprinter.
    assert "fictional" in plain.casefold()


def test_demo_companion_turns_ask_one_question():
    """Each companion turn in the demo asks at most one question."""
    html = _read(DEMO)
    starts = [m.end() for m in re.finditer(r'<div class="turn companion[^"]*"[^>]*>', html)]
    assert len(starts) == COMPANION_TURNS
    turns = []
    for n, (start, nxt) in enumerate(zip(starts, starts[1:] + [len(html)]), 1):
        m = re.search(r"</div>\s*<!-- /turn -->", html[start:nxt])
        assert m, f"companion turn {n} has no <!-- /turn --> marker"
        turns.append(html[start:start + m.start()])
    for t in turns:
        # The startup-folder question is one question over several folders: "Is `a` your startup? And `b`?"
        body = re.sub(r"\?(\s*And <code>[^<]+</code>\?)+", "?", t)
        body = re.sub(r"<[^>]+>", "", body)
        body = re.sub(r"&ldquo;.*?&rdquo;|“.*?”", "", body, flags=re.S)  # quoted words don't count
        assert body.count("?") <= 1, body.strip()[:120]


def test_art_note_says_placeholders():
    text = _read(ART)
    assert "placeholder" in text.casefold()
    assert "original" in text.casefold()


def test_privacy_says_which_folders_are_kept_and_which_are_read():
    """The prompt hook keeps prompts from every folder; only confirmed startup folders are ever read."""
    privacy = _section(_read(README), "Privacy")
    assert "from every folder you work in" in privacy
    assert "only notes from folders you've confirmed as the startup are ever read into your memory" in privacy
    assert "only from folders you've confirmed as the startup" not in privacy
    assert "deleted after 30 days" in privacy


def test_allow_rules_say_deleting_is_always_asked_first():
    install = _section(_read(README), "Install")
    rules = install[install.index("**Fewer permission prompts"):install.index("**First run.**")]
    assert "companions always ask you in the chat before deleting" in rules
