"""The `memory` subcommands."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from . import create_bank, open_bank
from .recall import brief, gaps, recall
from .retain import BatchError, retain
from .pages import write_pages
from .sources import import_source
from .stage import BriefError, render_brief
from .pages import write_page


def _fail(msg: str, code: int = 1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def _utf8() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def _warn(store) -> None:
    for w in store.warnings:
        print(w, file=sys.stderr)


def _person(directory: Path) -> dict:
    return json.loads((Path(directory) / "person.json").read_text(encoding="utf-8"))


def _open(directory):
    _utf8()
    store, bank = open_bank(Path(directory))
    _warn(store)
    return store, bank


def _regen(directory: Path) -> None:
    """Rewrite the pages. The log is already written, so a failure here is only a warning."""
    try:
        store, bank = open_bank(directory)
        write_pages(bank, _person(directory)["name"], Path(directory) / "pages")
    except Exception as e:
        print(f"warning: the pages were not updated ({e}). The memory itself was saved; "
              f"run `memory pages {directory}` to retry.", file=sys.stderr)


def _retain(store, batch: dict) -> dict:
    try:
        return retain(store, batch)
    except BatchError as e:
        for err in e.errors:
            print(err, file=sys.stderr)
        sys.exit(1)


def cmd_init(a):
    _utf8()
    print(create_bank(Path(a.root), a.name))


def cmd_retain(a):
    store, _ = _open(a.bank)
    try:
        batch = json.loads(Path(a.batch).read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        _fail(f"batch file is not valid JSON: {e}")
    report = _retain(store, batch)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)  # before pages: the write succeeded
    _regen(Path(a.bank))


def cmd_import(a):
    _open(a.bank)
    id_, created = import_source(Path(a.bank), Path(a.file))
    print(f"{id_} {'new' if created else 'already imported'}", flush=True)
    _regen(Path(a.bank))


def cmd_brief(a):
    _, bank = _open(a.bank)
    print(brief(bank, _person(Path(a.bank))["name"]))


def cmd_recall(a):
    _, bank = _open(a.bank)
    out = recall(bank, query=a.query, about=a.about, entity=a.entity, type=a.type,
                 since=a.since, limit=a.limit)
    print(json.dumps(out, ensure_ascii=False, indent=2))


def cmd_gaps(a):
    _, bank = _open(a.bank)
    print(json.dumps(gaps(bank), ensure_ascii=False, indent=2))


def cmd_pages(a):
    _, bank = _open(a.bank)
    for p in write_pages(bank, _person(Path(a.bank))["name"], Path(a.bank) / "pages"):
        print(p)


def cmd_demo_brief(a):
    _, bank = _open(a.bank)
    try:
        plan = json.loads(Path(a.plan).read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        _fail(f"plan file is not valid JSON: {e}")
    try:
        text = render_brief(bank, plan)
    except BriefError as e:
        for err in e.errors:
            print(err, file=sys.stderr)
        sys.exit(1)
    out_dir = Path(a.bank) / "pages"
    out_dir.mkdir(parents=True, exist_ok=True)
    body = text.split("\n", 2)[2].rstrip("\n").split("\n")  # write_page adds the header itself
    print(write_page(out_dir / f"brief-{plan['occasion']}.md", body))


def cmd_forget(a):
    store, _ = _open(a.bank)
    _retain(store, {"source": {"kind": "said", "ref": "forget"},
                    "items": [{"op": "retract", "id": a.id, "reason": a.reason}]})
    print(f"retracted {a.id}", flush=True)
    _regen(Path(a.bank))


def cmd_delete(a):
    _utf8()
    directory = Path(a.bank)
    if not a.yes:
        _fail(f"Refusing to delete {directory} without --yes. "
              "This removes every memory for this person and cannot be undone.", 2)
    if not (directory / "person.json").exists():
        _fail(f"no memory bank at {directory}")
    shutil.rmtree(directory)
    print(f"deleted {directory}")


def register(sub) -> None:
    m = sub.add_parser("memory", help="per-person memory bank")
    ms = m.add_subparsers(required=True)

    def add(name, fn, *args):
        c = ms.add_parser(name)
        for arg in args:
            c.add_argument(*arg[0], **arg[1])
        c.set_defaults(fn=fn)
        return c

    pos = lambda n, **k: ((n,), k)
    opt = lambda n, **k: ((n,), k)
    from pathlib import Path as _P
    from companions.home import people_dir
    default_root = str(people_dir())
    add("init", cmd_init, pos("name"), opt("--root", default=default_root))
    add("retain", cmd_retain, pos("bank"), pos("batch"))
    add("import", cmd_import, pos("bank"), pos("file"))
    add("brief", cmd_brief, pos("bank"))
    add("recall", cmd_recall, pos("bank"), opt("--query"), opt("--about"), opt("--entity"),
        opt("--type"), opt("--since"), opt("--limit", type=int, default=10))
    add("gaps", cmd_gaps, pos("bank"))
    add("pages", cmd_pages, pos("bank"))
    add("demo-brief", cmd_demo_brief, pos("bank"), pos("plan"))
    add("forget", cmd_forget, pos("bank"), pos("id"), opt("--reason", required=True))
    add("delete", cmd_delete, pos("bank"), opt("--yes", action="store_true"))
