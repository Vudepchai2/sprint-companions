"""The `companions` command line."""
import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .home import people_dir, read_settings, update_settings
from .memory import bank_slug, create_bank
from .memory import cli as memory_cli
from .notes import inbox, notes_state, set_project


def cmd_version(a):
    print(f"companions {__version__}")


def cmd_bank(a):
    root = people_dir()
    slug = read_settings().get("bank")
    if slug and (root / slug / "person.json").exists():
        print(root / slug)
        return
    if not a.ensure:
        print('no bank yet; run: companions bank --ensure --name "<your name>"', file=sys.stderr)
        sys.exit(1)
    try:
        existing = root / bank_slug(a.name)
        if (existing / "person.json").exists():
            update_settings(bank=existing.name)
            print(existing)
            return
        directory = Path(create_bank(root, a.name))
    except (ValueError, FileExistsError) as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    update_settings(bank=directory.name)
    print(directory)


def _positive(value):
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError("must be 1 or more")
    return n


def cmd_notes(a):
    try:
        if a.action in ("on", "off"):
            update_settings(quiet_notes=a.action)
            print(f"quiet notes: {a.action}")
        elif a.action == "status":
            print(notes_state())
        elif a.action == "read":
            print(json.dumps(inbox.read(a.limit), ensure_ascii=False))
        elif a.action == "done":
            inbox.done(a.through)
        elif a.action == "project":
            set_project(a.cwd, a.startup == "yes")
            print(f"{a.cwd}: {'startup' if a.startup == 'yes' else 'not the startup'}")
    except OSError as e:
        print(f"quiet notes: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_hook(a):
    """Runs inside Claude Code on every prompt: always exits 0, never a traceback.

    `prompt` prints nothing (its stdout would become context); `session-start` prints only its JSON.
    """
    try:
        from .notes import hooks
        if a.event == "prompt" and a.payload is not None:
            text = hooks.take_payload(a.payload)  # read, then deleted at once
        else:
            text = sys.stdin.buffer.read().decode("utf-8-sig", errors="replace")
        if a.event == "prompt":
            hooks.prompt(text)
            hooks.sweep_pending()
        else:
            out = hooks.session_start(text)
            if out:
                sys.stdout.write(out + "\n")
                sys.stdout.flush()
    except BaseException:
        pass


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="companions")
    sub = p.add_subparsers(required=True)
    sub.add_parser("version").set_defaults(fn=cmd_version)
    memory_cli.register(sub)
    b = sub.add_parser("bank", help="print the active memory bank folder")
    b.add_argument("--ensure", action="store_true")
    b.add_argument("--name", default="me")
    b.set_defaults(fn=cmd_bank)
    n = sub.add_parser("notes", help="quiet notes: opt in or out, startup folders, read and mark digested")
    ns = n.add_subparsers(dest="action", required=True)
    ns.add_parser("on")
    ns.add_parser("off")
    ns.add_parser("status")
    nr = ns.add_parser("read")
    nr.add_argument("--limit", type=_positive, default=150)
    nd = ns.add_parser("done")
    nd.add_argument("--through", required=True)
    np = ns.add_parser("project")
    np.add_argument("cwd")
    np.add_argument("--startup", choices=("yes", "no"), required=True)
    n.set_defaults(fn=cmd_notes)
    h = sub.add_parser("hook", help="Claude Code hook entry points")
    h.add_argument("event", choices=("prompt", "session-start"))
    h.add_argument("--payload", help="prompt only: read the hook payload from this file in notes/pending, then delete it")
    h.set_defaults(fn=cmd_hook)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
