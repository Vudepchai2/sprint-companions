"""Release hygiene: no private terms or email addresses ship anywhere in the repo.

The private list of terms lives in `.scrub-list` at the repo root. It is git-ignored and never
committed. Without it the term check skips, unless COMPANIONS_REQUIRE_SCRUB=1, when it fails.
A failure names the file and line, never the term.

The four people the companions are inspired by may be named (in the README, the demo page and the
persona files), so their names are allowed even if the list holds them.
"""
import os
import re
import sys
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".venv", "__pycache__", ".pytest_cache", ".git"}
SKIP_NAMES = {".scrub-list"}
BINARY = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".wav", ".mp3", ".m4a", ".zip", ".pdf", ".pyc"}
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
EMAIL_OK = ("@users.noreply.github.com", "@example.com")
ALLOWED_NAMES = ("Tai Tran", "Kasper Suomalainen", "Mårten Mickos", "Maija Renko")


def _files():
    for p in sorted(ROOT.rglob("*")):
        rel = p.relative_to(ROOT).parts
        if not p.is_file() or p.name in SKIP_NAMES:  # binaries are walked: their names are checked
            continue
        if any(part in SKIP_DIRS or part.endswith(".egg-info") for part in rel):
            continue
        yield p


def _fold(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _lines(path):
    if path.suffix.lower() in BINARY:  # a binary's contents are never read
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    yield from enumerate(text.splitlines(), 1)


def _allowed():
    """Each allowed name, and each word of it, folded and case-folded."""
    out = set()
    for name in ALLOWED_NAMES:
        folded = _fold(name).casefold()
        out.add(folded)
        out.update(folded.split())
    return out


def _terms():
    f = ROOT / ".scrub-list"
    if not f.is_file():
        return []
    terms = [t.strip() for t in f.read_text(encoding="utf-8").splitlines() if t.strip()]
    allowed = _allowed()
    return [t for t in terms if _fold(t).casefold() not in allowed]


def _patterns(terms):
    # Only letters and digits count as word characters, so "_" does not hide a term.
    return [re.compile(rf"(?<![A-Za-z0-9]){re.escape(_fold(t))}(?![A-Za-z0-9])", re.IGNORECASE)
            for t in terms]


def _matches(pats, text):
    return any(p.search(text) or p.search(_fold(text)) for p in pats)


def find_hits(terms, files, root):
    """Return 'file:line' (or 'file (file name)') for every term hit; never the term."""
    pats = _patterns(terms)
    hits = []
    for p in files:
        rel = p.relative_to(root).as_posix()
        if _matches(pats, rel):
            hits.append(f"{rel} (file name)")
        for n, line in _lines(p):
            if _matches(pats, line):
                hits.append(f"{rel}:{n}")
    return hits


def test_no_scrub_terms():
    terms = _terms()
    if not terms:
        if (ROOT / ".scrub-list").is_file():
            why = ".scrub-list holds no terms once the allowed names are left out"
        else:
            why = "no .scrub-list was found"
        if os.environ.get("COMPANIONS_REQUIRE_SCRUB") == "1":
            pytest.fail(f"COMPANIONS_REQUIRE_SCRUB=1 but {why}")
        pytest.skip(why)
    hits = find_hits(terms, _files(), ROOT)
    assert not hits, "scrub-list hits (term not shown):\n" + "\n".join(hits)


def test_scrub_list_is_git_ignored():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".scrub-list" in [line.strip() for line in ignored]


def test_matcher_catches_underscore_accents_and_file_name(tmp_path):
    (tmp_path / "zorblax-notes.md").write_text("x\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("ok\nname = 'x_zorblax_y'\nZORBLAXIAN is fine\nZörblax met us\n",
                                   encoding="utf-8")
    files = sorted(tmp_path.iterdir())
    hits = find_hits(["zorblax"], files, tmp_path)
    assert hits == ["b.md:2", "b.md:4", "zorblax-notes.md (file name)"]


def test_the_four_names_are_allowed(tmp_path, monkeypatch):
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    (tmp_path / ".scrub-list").write_text("Marten Mickos\nRenko\ntai\nzorblax\n", encoding="utf-8")
    (tmp_path / "a.md").write_text("inspired by Mårten Mickos\ninspired by Maija Renko\nTai\nzorblax\n",
                                   encoding="utf-8")
    assert _terms() == ["zorblax"]
    assert find_hits(_terms(), _files(), tmp_path) == ["a.md:4"]


def test_walk_skips_caches_and_covers_the_whole_repo():
    rels = {p.relative_to(ROOT).parts for p in _files()}
    assert not any(set(parts) & SKIP_DIRS for parts in rels)
    assert ("README.md",) in rels
    assert any(parts[:1] == ("engine",) for parts in rels)
    assert any(parts[-1] == "SKILL.md" for parts in rels)
    assert (".scrub-list",) not in rels


def test_binary_names_are_checked_but_not_their_contents(tmp_path, monkeypatch):
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    (tmp_path / "zorblax-icon.png").write_bytes(b"\x89PNG\r\n")
    (tmp_path / "plain.png").write_bytes(b"\x89PNG zorblax \xff\xfe")  # contents of a binary are never read
    (tmp_path / "cache").mkdir()
    hits = find_hits(["zorblax"], _files(), tmp_path)
    assert hits == ["zorblax-icon.png (file name)"]


def test_list_of_only_allowed_names_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    (tmp_path / ".scrub-list").write_text("Maija Renko\n\nTai\n", encoding="utf-8")
    monkeypatch.setenv("COMPANIONS_REQUIRE_SCRUB", "1")
    with pytest.raises(pytest.fail.Exception, match="holds no terms"):
        test_no_scrub_terms()


def test_missing_list_skips_or_fails_when_required(tmp_path, monkeypatch):
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    monkeypatch.delenv("COMPANIONS_REQUIRE_SCRUB", raising=False)
    with pytest.raises(pytest.skip.Exception):
        test_no_scrub_terms()
    monkeypatch.setenv("COMPANIONS_REQUIRE_SCRUB", "1")
    with pytest.raises(pytest.fail.Exception, match="no .scrub-list was found"):
        test_no_scrub_terms()


def test_no_email_addresses():
    hits = []
    for p in _files():
        for n, line in _lines(p):
            for m in EMAIL.finditer(line):
                if not m.group(0).lower().endswith(EMAIL_OK):
                    hits.append(f"{p.relative_to(ROOT).as_posix()}:{n}")
    assert not hits, "email addresses:\n" + "\n".join(hits)
