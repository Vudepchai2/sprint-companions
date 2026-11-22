"""The `companions` command line."""
import argparse
import sys
from pathlib import Path

from . import __version__
from .home import people_dir, read_settings, update_settings
from .memory import bank_slug, create_bank
from .memory import cli as memory_cli


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
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
