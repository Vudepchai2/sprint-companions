import pytest

from companions.memory import open_bank
from companions.memory.schema import BY, SOURCE_KINDS
from test_memory_retain import bank, errors_of, run  # noqa: F401  (bank is a fixture)

MOMENT = {"type": "moment", "title": "T", "what_happened": "W"}
CLAIM_ITEMS = [{"type": "moment", "ref": "@m", "title": "First clinic", "what_happened": "Signed"},
               {"type": "claim", "about": "@m", "key": "mrr", "statement": "€200/month",
                "value": 200, "unit": "eur_month", "quote": "first clinic signed, €200/month"}]


def claim(about="m1"):
    return {"type": "claim", "about": about, "key": "mrr", "statement": "€200/month",
            "value": 200, "unit": "eur_month", "quote": "€200/month"}


def test_constants():
    assert SOURCE_KINDS == ("said", "document", "build", "companion")
    assert BY == ("tt", "ks", "mm", "mr", "notes")


def test_build_source_adds_claims_and_counts_as_told(bank):
    store, directory = bank
    r = run(store, CLAIM_ITEMS, source={"kind": "build", "ref": "sessions/abc", "by": "notes"})
    b = open_bank(directory)[1]
    assert b.moment_status(r["added"][0]["id"]) == "told"
    assert b.records["m1"]["sources"][0]["by"] == "notes"


def test_same_session_said_and_build_is_not_corroborated(bank):
    store, directory = bank
    run(store, CLAIM_ITEMS[:1], {"kind": "said", "ref": "sessions/abc"})
    run(store, [claim()], {"kind": "build", "ref": "sessions/abc"})
    run(store, [claim()], {"kind": "said", "ref": "sessions/abc", "by": "ks"})
    b = open_bank(directory)[1]
    assert b.claim_status("c1") == "said"


def test_two_sessions_corroborate(bank):
    store, directory = bank
    run(store, CLAIM_ITEMS[:1], {"kind": "said", "ref": "sessions/abc"})
    run(store, [claim()], {"kind": "build", "ref": "sessions/abc"})
    run(store, [claim()], {"kind": "said", "ref": "sessions/def", "by": "mm"})
    assert open_bank(directory)[1].claim_status("c1") == "corroborated"


def test_companion_source_only_adds_observations(bank):
    store, _ = bank
    run(store, [MOMENT])
    source = {"kind": "companion", "ref": "sessions/abc", "by": "mm"}
    assert "a companion source can only add observations" in errors_of(store, [claim()], source)[0]
    run(store, [{"type": "observation", "about": "person", "statement": "s"}], source)


@pytest.mark.parametrize("kind", ["coach", "transcript"])
def test_coach_and_transcript_kinds_are_rejected(bank, kind):
    store, _ = bank
    assert "source.kind must be one of" in errors_of(store, [MOMENT], {"kind": kind, "ref": "x"})[0]


def test_unknown_by_is_rejected(bank):
    store, _ = bank
    assert "source.by must be one of" in errors_of(
        store, [MOMENT], {"kind": "said", "ref": "sessions/a", "by": "marten"})[0]
    assert "source.by must be one of" in errors_of(
        store, [MOMENT], {"kind": "said", "ref": "sessions/a", "by": 3})[0]


def test_every_by_value_is_accepted(bank):
    store, _ = bank
    for by in BY:
        run(store, [MOMENT], {"kind": "said", "ref": "sessions/a", "by": by})


def test_occasion_format_and_audience(bank):
    store, directory = bank
    run(store, [{"type": "occasion", "name": "Demo day", "date": "2026-12-04",
                 "format": "3-minute pitch with slides, no Q&A",
                 "audience": "seed investors and corporates, they care about paying customers"}])
    d = open_bank(directory)[1].live("occasion")[0]["data"]
    assert d["format"].startswith("3-minute")
    assert d["audience"].startswith("seed investors")
    assert errors_of(store, [{"type": "occasion", "name": "X", "format": 3}]) == [
        "item 0: format must be a string"]


def test_companion_observation_reads_as_companions_reading(bank):
    from companions.memory.recall import observation_line
    store, directory = bank
    run(store, [{"type": "observation", "about": "telling", "statement": "Rushes"}],
        {"kind": "companion", "ref": "sessions/a", "by": "tt"})
    line = observation_line(open_bank(directory)[1].records["o1"])
    assert line.endswith("(0 evidence) (companion's reading)")
