"""The demo-day brief: a draft script whose beats cite real memory and invent no numbers."""
from __future__ import annotations

import re

from .bank import Bank
from .pages import HEADER
from .schema import BY

DRAFT_LINE = "Draft: in your words, from your memory. Change anything that doesn't sound like you."
WORDS_PER_MINUTE = 150
PROOF_ORDER = ("confirmed", "corroborated", "said", "documented")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
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


def _numbers(text: str) -> set[float]:
    out = set()
    for m in _NUMBER.findall(text):
        try:
            out.add(float(m.replace(",", "")))
        except ValueError:
            pass
    return out


def _record_numbers(rec: dict) -> set[float]:
    d = rec["data"]
    nums: set[float] = set()
    for f in _TEXT_FIELDS:
        nums |= _numbers(str(d.get(f) or ""))
    for q in d.get("quotes") or []:
        nums |= _numbers(str(q))
    v = d.get("value")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        nums.add(float(v))
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
        if line and len(recs) == len(cites) and cites:
            known = set().union(*(_record_numbers(r) for r in recs))
            for raw in dict.fromkeys(_NUMBER.findall(line)):
                if _numbers(raw) - known:
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
    conflicted = [c for c in dict.fromkeys(proof) if bank.claim_status(c) == "conflicted"]
    if conflicted:
        out += ["", "### Conflicts to settle", ""] + [_proof_line(bank, c) for c in conflicted]
    if asks:
        out += ["", "## Before you go on stage", ""] + asks
    return "\n".join(out) + "\n"
