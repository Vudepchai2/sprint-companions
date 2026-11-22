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


def test_mr_has_research_honesty_rule():
    never = (PLUGIN / "skills" / "mr" / "persona.md").read_text(encoding="utf-8").split("## Never", 1)[1]
    assert "make up a citation" in never
