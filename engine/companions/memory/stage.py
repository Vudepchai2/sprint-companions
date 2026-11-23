"""The demo-day brief: a draft script whose beats cite real memory and invent no numbers."""
from __future__ import annotations

import re

from .bank import Bank
from .pages import HEADER
from .schema import BY

DRAFT_LINE = "Draft: in your words, from your memory. Change anything that doesn't sound like you."
WORDS_PER_MINUTE = 150
PROOF_ORDER = ("confirmed", "corroborated", "said", "documented")
_TEXT_FIELDS = ("title", "what_happened", "statement", "quote")


class BriefError(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


def source_label(source: dict) -> str:
    by = source.get("by")
    at = str(source.get("at") or "")[:10]
    if by in BY and by != "notes":
        return f"noted by {by.upper()}"
    if by == "notes":
        return f"quiet notes, {at}" if at else "quiet notes"
    kind = source.get("kind", "")
    return f"{kind}, {at}" if at else str(kind)


_UNITS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * i for i, w in enumerate(
    "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}
_SCALES = {"hundred": 100, "thousand": 1000, "million": 1_000_000, "billion": 1_000_000_000}
_TOKEN = re.compile(r"\d{1,3}(?:,\d{3})+(?!\d)(?:\.\d+)?|\d+(?:\.\d+)?|[a-z]+")
# A magnitude suffix glued to a number or one space after it: 50k, 2.5m, 1.2bn, 3 b. The number must
# start a word and the suffix end it, so "b2b" and "km" are not suffixes.
_SUFFIXES = {"k": 1_000, "m": 1_000_000, "mn": 1_000_000, "b": 1_000_000_000, "bn": 1_000_000_000}


def _find_numbers(text: str) -> list[tuple[str, float]]:
    """Every number in the text, as (the words as written, its value): digits and number words."""
    low = text.lower()
    matches = list(_TOKEN.finditer(low))
    toks = [m.group(0) for m in matches]
    found: list[tuple[str, float]] = []
    total = cur = 0.0
    run: list[str] = []
    last = ""  # kind of the last token in the run: digit, unit, tens, scale

    def flush():
        nonlocal total, cur, run, last
        if run:
            found.append((" ".join(run), round(total + cur, 6)))  # 1.2 x 1e9 is 1.2e9, as written
        total = cur = 0.0
        run, last = [], ""

    def suffix(i: int) -> float | None:
        """The multiplier if token i+1 is a magnitude suffix on the number at token i."""
        if i + 1 >= len(toks) or toks[i + 1] not in _SUFFIXES:
            return None
        here, nxt_m = matches[i], matches[i + 1]
        before, after = low[here.start() - 1:here.start()] if here.start() else "", low[nxt_m.end():nxt_m.end() + 1]
        if (low[here.end():nxt_m.start()] not in ("", " ") or (after and after.isalnum())
                or (before and before.isalpha())):
            return None
        return _SUFFIXES[toks[i + 1]]

    skip = -1
    for i, t in enumerate(toks):
        if i == skip:
            continue
        nxt = toks[i + 1] if i + 1 < len(toks) else ""
        if t[0].isdigit():
            flush()
            cur, run, last = float(t.replace(",", "")), [t], "digit"
            mult = suffix(i)
            if mult is not None:
                gap = low[matches[i].end():matches[i + 1].start()]
                cur, run, skip = cur * mult, [t + gap + nxt], i + 1
                flush()
        elif t in _UNITS:
            if last == "tens" and _UNITS[t] < 10 and _UNITS[t] > 0 or last in ("scale", "and"):
                cur += _UNITS[t]
                run.append(t)
                last = "unit"
            else:
                flush()
                cur, run, last = float(_UNITS[t]), [t], "unit"
        elif t in _TENS:
            if last not in ("scale", "and"):
                flush()
            cur += _TENS[t]
            run.append(t)
            last = "tens"
        elif t in _SCALES or t == "dozen":
            mult = 12 if t == "dozen" else _SCALES[t]
            if not run and last != "pending":
                flush()
                cur, run = 1.0, [t]
            elif run and run[-1] in ("a", "an"):
                cur = 1.0
                run.append(t)
            else:
                run.append(t)
            if t == "dozen":
                cur *= 12
            elif mult == 100:
                cur *= 100
            else:
                total += cur * mult
                cur = 0.0
            last = "scale"
        elif t in ("a", "an") and nxt in (*_SCALES, "dozen"):
            flush()
            run, last = [t], "pending"
        elif t == "and" and last == "scale" and nxt in (*_UNITS, *_TENS):
            run.append(t)
            last = "and"
        else:
            flush()
    flush()
    return found


def _numbers(text: str) -> set[float]:
    return {v for _, v in _find_numbers(text)}


def _record_numbers(rec: dict) -> set[float]:
    d = rec["data"]
    nums: set[float] = set()
    for f in _TEXT_FIELDS:
        nums |= _numbers(str(d.get(f) or ""))
    for q in d.get("quotes") or []:
        nums |= _numbers(str(q))
    v = d.get("value")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        nums.add(round(float(v), 6))
    elif isinstance(v, str):
        nums |= _numbers(v)
    return nums


def _check_id(bank: Bank, id_, types: tuple[str, ...], where: str, errors: list[str]):
    rec = bank.records.get(id_) if isinstance(id_, str) else None
    if rec is None:
        errors.append(f"{where}: {id_!r} is not in the memory")
    elif rec["retracted"]:
        errors.append(f"{where}: {id_} was retracted")
    elif rec["type"] not in types:
        errors.append(f"{where}: {id_} is a {rec['type']}, not a {' or '.join(types)}")
    else:
        return rec
    return None


def _quote_lines(rec: dict) -> list[str]:
    d = rec["data"]
    quote = d.get("quote") or (d.get("quotes") or [None])[0]
    if quote:
        text = f'"{quote}"'
    else:
        text = f'"{d.get("statement") or d.get("what_happened") or d.get("title") or ""}" (your words)'
    label = source_label(rec["sources"][0]) if rec["sources"] else "no source"
    return [f"   > {text} — {label}"]


def _proof_line(bank: Bank, id_: str) -> str:
    d = bank.records[id_]["data"]
    line = f"- {d.get('statement', '')} · {bank.claim_status(id_)}"
    return line + (f' · "{d["quote"]}"' if d.get("quote") else "")


def render_brief(bank: Bank, plan: dict) -> str:
    errors: list[str] = []
    if not isinstance(plan, dict):
        raise BriefError(["the plan must be a JSON object"])
    occasion = _check_id(bank, plan.get("occasion"), ("occasion",), "occasion", errors)

    beats = []
    script = plan.get("script") or []
    if not isinstance(script, list):
        errors.append("script must be a list of beats")
        script = []
    for n, beat in enumerate(script, 1):
        where = f"beat {n}"
        if not isinstance(beat, dict):
            errors.append(f"{where}: must be an object with line and cites")
            continue
        line = beat.get("line")
        line = line.strip() if isinstance(line, str) else ""
        cites = beat.get("cites")
        if not line:
            errors.append(f"{where}: the line is empty")
        if not isinstance(cites, list) or not cites:
            errors.append(f"{where}: cites at least one moment or claim")
            cites = []
        recs = [r for c in cites if (r := _check_id(bank, c, ("moment", "claim"), f"{where} cites", errors))]
        for r in recs:  # a conflict is the sprinter's to settle; a line built on one side picks it for them
            if r["type"] == "claim" and bank.claim_status(r["id"]) == "conflicted":
                errors.append(f"{where} cites: {r['id']} is in an open conflict; settle it with the sprinter first")
        recs = [r for r in recs if not (r["type"] == "claim" and bank.claim_status(r["id"]) == "conflicted")]
        if line and len(recs) == len(cites) and cites:
            known = set().union(*(_record_numbers(r) for r in recs))
            for raw, value in dict.fromkeys(_find_numbers(line)):
                if value not in known:
                    errors.append(f"{where}: the number {raw} is not in any record it cites")
            beats.append((n, line, recs))

    proof_ids = plan.get("proof") or []
    if not isinstance(proof_ids, list):
        errors.append("proof must be a list of claim ids")
        proof_ids = []
    proof = [c for c in proof_ids if _check_id(bank, c, ("claim",), "proof", errors)]

    questions = plan.get("before_stage") or []
    if not isinstance(questions, list):
        errors.append("before_stage must be a list")
        questions = []
    asks = []
    for n, q in enumerate(questions, 1):
        by = q.get("by") if isinstance(q, dict) else None
        text = q.get("question") if isinstance(q, dict) else None
        if by not in BY or by == "notes":
            errors.append(f"before_stage {n}: by must be one of {', '.join(b for b in BY if b != 'notes')}, not {by!r}")
        elif not isinstance(text, str) or not text.strip():
            errors.append(f"before_stage {n}: the question is empty")
        else:
            asks.append(f"- {by.upper()}: {text.strip()}")
    if errors:
        raise BriefError(errors)

    d = occasion["data"]
    title = f"# Demo-day brief: {d.get('name', '')}" + (f" ({d['date']})" if d.get("date") else "")
    out = [HEADER, "", title, "", DRAFT_LINE]
    if d.get("format"):
        out.append(f"Format: {d['format']}")
    if d.get("audience"):
        out.append(f"Audience: {d['audience']}")
    words = sum(len(line.split()) for _, line, _ in beats)
    out += ["", f"## Draft script (about {words / WORDS_PER_MINUTE:.1f} minutes at speaking pace)"]
    for n, line, recs in beats:
        out += ["", f"{n}. {line}"]
        for r in recs:
            out += _quote_lines(r)
    if not beats:
        out += ["", "- none"]

    live = [c for c in dict.fromkeys(proof) if bank.claim_status(c) != "conflicted"]
    live.sort(key=lambda c: PROOF_ORDER.index(bank.claim_status(c)))
    out += ["", "## Proof", ""] + ([_proof_line(bank, c) for c in live] or ["- none"])
    # Every open conflict is listed, in the plan's proof or not: conflicts are flagged, never hidden.
    open_claims = [c for k in bank.conflicts.values() if k["open"] for c in k["claims"]
                   if not bank.records[c]["retracted"]]
    conflicted = [c for c in dict.fromkeys([*proof, *open_claims]) if bank.claim_status(c) == "conflicted"]
    if conflicted:
        out += ["", "### Conflicts to settle", ""] + [_proof_line(bank, c) for c in conflicted]
    if asks:
        out += ["", "## Before you go on stage", ""] + asks
    return "\n".join(out) + "\n"
