import re
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1] / "plugin"
HEADINGS = ["## Role and lens", "## Outcome line", "## How they talk",
            "## Signature questions", "## Never", "## Sources"]
DISCLOSURE = {
    "tt": "I'm TT, an AI companion inspired by Tai Tran. I'm not him, and I don't speak for him.",
    "ks": "I'm KS, an AI companion inspired by Kasper Suomalainen. I'm not him, and I don't speak for him.",
    "mm": "I'm MM, an AI companion inspired by Mårten Mickos. I'm not him, and I don't speak for him.",
    "mr": "I'm MR, an AI companion inspired by Maija Renko. I'm not her, and I don't speak for her.",
}


@pytest.mark.parametrize("code", ["tt", "ks", "mm", "mr"])
def test_persona_has_sections_disclosure_and_sources(code):
    text = (PLUGIN / "skills" / code / "persona.md").read_text(encoding="utf-8")
    for h in HEADINGS:
        assert h in text
    assert DISCLOSURE[code] in text
    sources = text.split("## Sources", 1)[1]
    assert len(re.findall(r"^- .*https?://", sources, re.M)) >= 2
    questions = text.split("## Signature questions", 1)[1].split("\n## ", 1)[0]
    assert 3 <= len(re.findall(r"^- ", questions, re.M)) <= 5


def _section(code, heading):
    text = (PLUGIN / "skills" / code / "persona.md").read_text(encoding="utf-8")
    return text.split(heading + "\n", 1)[1].split("\n## ", 1)[0]


def test_mr_has_research_honesty_rule():
    never = _section("mr", "## Never")
    assert "make up a citation" in never
    assert "## Sources" not in never


def test_tt_lists_phrases_as_the_companion_s():
    talk = _section("tt", "## How they talk")
    assert "**Phrases the companion uses" in talk
    assert "Phrases he leans on" not in talk


def test_mm_opens_with_one_question():
    questions = _section("mm", "## Signature questions")
    first = next(line for line in questions.splitlines() if line.startswith("- "))
    assert first.count("?") == 1
