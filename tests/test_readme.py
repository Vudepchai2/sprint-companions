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

    assert "after a customer call" in text.casefold()

    privacy = _section(text, "Privacy")
    assert "~/SprintCompanions" in privacy and "COMPANIONS_HOME" in privacy
    assert "30 days" in privacy

    limits = _section(text, "Limits")
    assert "cofounders on separate laptops have separate memories" in limits.casefold()
    assert "voice" in limits.casefold() and "score" in limits.casefold()

    for heading in ("After a customer call", "/brief", "/panel", "/memory", "Model"):
        _section(text, heading)
    assert DRAFT_HEADER in _section(text, "/brief")
    assert "docs/demo.html" in text


def test_readme_mm_keeps_the_ai_marten_link_as_a_todo():
    text = _read(README)
    comments = re.findall(r"<!--(.*?)-->", text, flags=re.S)
    assert any("TODO" in c and "AI Marten" in c for c in comments)
    # No link to it yet: the author confirms first.
    assert "AI Marten" not in _without_comments(text)


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
    for status in ("said", "corroborated", "confirmed", "conflicted"):
        assert status in plain, status
    # Five moments, in the spec's order.
    moments = re.findall(r'<section class="moment" id="([a-z-]+)"', html)
    assert moments == ["catch-up", "routed", "memory-catch", "panel", "brief"]
    # The page says the transcripts are illustrative, with a fictional sprinter.
    assert "fictional" in plain.casefold()


def test_demo_companion_turns_ask_one_question():
    """Each companion turn in the demo asks at most one question."""
    html = _read(DEMO)
    turns = re.findall(r'<div class="turn companion[^"]*"[^>]*>(.*?)</div>\s*<!-- /turn -->', html, flags=re.S)
    assert len(turns) >= 12  # every companion turn, panel takes included
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
