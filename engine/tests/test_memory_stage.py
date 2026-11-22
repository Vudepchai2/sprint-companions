import json
import subprocess
import sys

import pytest

from companions.memory import create_bank, open_bank
from companions.memory.pages import HEADER
from companions.memory.retain import retain
from companions.memory.stage import BriefError, render_brief, source_label

SAID = {"kind": "said", "ref": "sessions/a", "at": "2026-11-02T10:00:00Z"}
DRAFT = "Draft: in your words, from your memory. Change anything that doesn't sound like you."


def _add(store, items, source=SAID):
    return retain(store, {"source": source, "items": items})


@pytest.fixture
def env(tmp_path):
    directory = create_bank(tmp_path, "Ana")
    store = open_bank(directory)[0]
    _add(store, [
        {"type": "occasion", "name": "Demo Day", "date": "2026-12-05",
         "format": "3 minutes", "audience": "investors"},
        {"type": "moment", "title": "Invoices", "what_happened": "Every Friday for six years Anna did invoices by hand",
         "quotes": ["I did them by hand, every Friday"]},
        {"type": "moment", "title": "No quote", "what_happened": "She printed 1,200 invoices"},
        {"type": "claim", "about": "m1", "key": "price", "statement": "Pays 200 a month",
         "quote": "€200/month", "value": 200},
        {"type": "claim", "about": "m1", "key": "count", "statement": "1200 invoices", "quote": "1200 invoices"},
        {"type": "claim", "about": "m1", "key": "years", "statement": "Six years", "quote": "six years"},
    ])
    return store, directory


def bank_of(env):
    return open_bank(env[1])[1]


def plan(**kw):
    p = {"occasion": "oc1", "script": [{"line": "Six years of invoices.", "cites": ["m1"]}], "proof": []}
    p.update(kw)
    return p


def errors(bank, p):
    with pytest.raises(BriefError) as exc:
        render_brief(bank, p)
    return exc.value.errors


def test_source_label():
    assert source_label({"by": "tt"}) == "noted by TT"
    assert source_label({"by": "mr", "kind": "said"}) == "noted by MR"
    assert source_label({"by": "notes", "at": "2026-11-02T10:00:00Z"}) == "quiet notes, 2026-11-02"
    assert source_label({"kind": "said", "at": "2026-11-02T10:00:00Z"}) == "said, 2026-11-02"
    assert source_label({"kind": "document"}) == "document"


def test_rejects_unknown_or_retracted_ids(env):
    store, _ = env
    retain(store, {"source": SAID, "items": [{"op": "retract", "id": "c3", "reason": "wrong"}]})
    b = bank_of(env)
    errs = errors(b, {"occasion": "oc9", "script": [{"line": "x", "cites": ["m77", "c3"]}], "proof": ["c88"]})
    joined = "\n".join(errs)
    for bad in ("oc9", "m77", "c3", "c88"):
        assert bad in joined
    assert len(errs) == 4


def test_rejects_wrong_types(env):
    b = bank_of(env)
    errs = errors(b, {"occasion": "m1", "script": [{"line": "x", "cites": ["oc1"]}], "proof": ["m1"]})
    assert len(errs) == 3
    assert any("m1" in e and "occasion" in e for e in errs)
    assert any("oc1" in e for e in errs)


def test_rejects_beat_without_cites_or_with_empty_line(env):
    b = bank_of(env)
    errs = errors(b, plan(script=[{"line": "Fine.", "cites": []}, {"line": "  ", "cites": ["m1"]}]))
    assert len(errs) == 2
    assert any("beat 1" in e for e in errs) and any("beat 2" in e for e in errs)


def test_rejects_number_not_in_cited_records(env):
    b = bank_of(env)
    errs = errors(b, plan(script=[{"line": "ok", "cites": ["m1"]},
                                  {"line": "we make €300 a month", "cites": ["c1"]}]))
    assert len(errs) == 1 and "beat 2" in errs[0] and "300" in errs[0]


def test_accepts_numbers_from_cited_records(env):
    b = bank_of(env)
    out = render_brief(b, plan(script=[
        {"line": "Six years of pain.", "cites": ["m1"]},
        {"line": "She pays €200 a month.", "cites": ["c1"]},
        {"line": "1,200 invoices.", "cites": ["c2"]},
        {"line": "She printed 1,200 invoices.", "cites": ["m2"]},
    ]))
    assert "1,200 invoices." in out


def test_script_renders_line_quote_and_label(env):
    b = bank_of(env)
    out = render_brief(b, plan(script=[
        {"line": "Six years.", "cites": ["m1", "c1", "m2"]}]))
    assert '1. Six years.\n' in out
    assert '   > "I did them by hand, every Friday" — said, 2026-11-02' in out
    assert '   > "€200/month" — said, 2026-11-02' in out
    assert '   > "She printed 1,200 invoices" (your words) — said, 2026-11-02' in out


def test_length_estimate(env):
    b = bank_of(env)
    line = " ".join(["word"] * 75)
    out = render_brief(b, plan(script=[{"line": line, "cites": ["m1"]}]))
    assert "## Draft script (about 0.5 minutes at speaking pace)" in out


def test_header(env):
    b = bank_of(env)
    out = render_brief(b, plan())
    lines = out.splitlines()
    assert lines[0] == HEADER
    assert lines[2] == "# Demo-day brief: Demo Day (2026-12-05)"
    assert DRAFT in lines and "Format: 3 minutes" in lines and "Audience: investors" in lines
    assert lines.index(DRAFT) < lines.index("Format: 3 minutes") < lines.index("Audience: investors")
    store, _ = env
    _add(store, [{"type": "occasion", "name": "Bare"}])
    out = render_brief(bank_of(env), plan(occasion="oc2"))
    assert "# Demo-day brief: Bare\n" in out and "Format:" not in out and "Audience:" not in out


def test_proof_sorted_by_status(env):
    store, _ = env
    store.append([{"op": "add", "id": "s1", "type": "source", "data": {"filename": "inv.pdf"}, "source": SAID}])
    _add(store, [{"type": "claim", "about": "m1", "key": "a", "statement": "Doc claim", "quote": "dq"}], {"kind": "document", "ref": "s1"})
    _add(store, [{"type": "claim", "about": "m1", "key": "p", "statement": "Conf claim", "quote": "cq"}])
    _add(store, [{"type": "claim", "about": "m1", "key": "price", "statement": "Pays 500", "quote": "€500", "value": 500}])
    b = bank_of(env)
    conflicted = [i for i in b.records if b.records[i]["type"] == "claim" and b.claim_status(i) == "conflicted"]
    assert conflicted
    proof = [i for i in b.records if b.records[i]["type"] == "claim"
             and b.claim_status(i) in ("documented", "said")]
    out = render_brief(b, plan(proof=proof + conflicted))
    assert "### Conflicts to settle" in out
    head, tail = out.split("### Conflicts to settle")
    sec = head.split("## Proof")[1]
    assert sec.index("· said ·") < sec.index("· documented ·")
    assert '- Doc claim · documented · "dq"' in sec
    for c in conflicted:
        assert b.records[c]["data"]["statement"] in tail
        assert b.records[c]["data"]["statement"] not in sec


def test_before_stage(env):
    b = bank_of(env)
    out = render_brief(b, plan(before_stage=[{"by": "mm", "question": "Interested, or paying?"}]))
    assert "- MM: Interested, or paying?" in out
    for bad in ("notes", "zz"):
        errs = errors(b, plan(before_stage=[{"by": bad, "question": "q"}]))
        assert len(errs) == 1 and bad in errs[0]


def test_cli_writes_page_or_fails_clean(env, tmp_path):
    _, directory = env
    pf = tmp_path / "plan.json"
    pf.write_text(json.dumps(plan()), encoding="utf-8")
    r = subprocess.run([sys.executable, "-m", "companions", "memory", "demo-brief", str(directory), str(pf)],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    page = directory / "pages" / "brief-oc1.md"
    assert r.stdout.strip() == str(page) and page.exists()
    page.unlink()
    pf.write_text(json.dumps(plan(proof=["c99"])), encoding="utf-8")
    r = subprocess.run([sys.executable, "-m", "companions", "memory", "demo-brief", str(directory), str(pf)],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 1 and "c99" in r.stderr and not page.exists()


def _with_quote(env, statement, quote, line):
    store, _ = env
    _add(store, [{"type": "claim", "about": "m1", "key": "x" + str(abs(hash(quote)) % 999),
                  "statement": statement, "quote": quote}])
    b = bank_of(env)
    cid = max((i for i in b.records if b.records[i]["type"] == "claim"), key=lambda i: int(i[1:]))
    return b, plan(script=[{"line": line, "cites": [cid]}])


def test_spelled_out_number_not_in_cited_records_is_rejected(env):
    b, p = _with_quote(env, "Customers", "some customers", "three hundred customers")
    errs = errors(b, p)
    assert len(errs) == 1 and "beat 1" in errs[0] and "three hundred" in errs[0]
    b, p = _with_quote(env, "Customers", "some customers", "a hundred percent")
    assert "a hundred" in errors(b, p)[0]


def test_spelled_out_number_matches_digits_in_record(env):
    b, p = _with_quote(env, "Customers", "300 customers", "three hundred customers")
    assert "three hundred customers" in render_brief(b, p)
    b, p = _with_quote(env, "Clinics", "12 clinics", "a dozen clinics")
    assert "a dozen clinics" in render_brief(b, p)
    b, p = _with_quote(env, "Team", "25 people", "twenty-five people")
    assert "twenty-five people" in render_brief(b, p)


def test_spelled_out_number_matches_words_in_record(env):
    b, p = _with_quote(env, "Tenure", "for six years", "for six years")
    assert "for six years" in render_brief(b, p)


def test_comma_only_joins_thousands_groups(env):
    b, p = _with_quote(env, "Count", "it was 23 times", "2,3 times")
    errs = errors(b, p)
    assert len(errs) == 2 and "number 2 " in errs[0] and "number 3 " in errs[1]
