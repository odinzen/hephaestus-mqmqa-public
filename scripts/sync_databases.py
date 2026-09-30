"""Sync the shipped databases in web/ from their sources, driven by data/databases.toml.

    python scripts/sync_databases.py          # copy drifted sources, regenerate the load buttons
    python scripts/sync_databases.py --check  # change nothing; exit 1 if anything is out of sync

Every database file in web/ is a copy of a source under data/, and the calculator's load
buttons are generated from the registry. The script refuses to continue when a source is
missing, a file sits in web/ without a registry entry, a .utdb half is missing, a shipped file
would be hidden by .gitignore, or the button markers in web/index.html are gone.
"""
from __future__ import annotations

import argparse
import filecmp
import html
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORMATS = {"dat", "tdb", "utdb", "xtdb"}
CARDS = {"load": "data-shipped", "xtdb": "data-shipped-xtdb"}
BUTTON_INDENT = " " * 6


class SyncError(ValueError):
    pass


@dataclass
class Entry:
    file: str
    source: str
    format: str
    parts: list[str] = field(default_factory=list)
    card: str | None = None
    button: str | None = None
    label: str | None = None
    title: str | None = None
    kind: str | None = None
    blurb: str | None = None


def load_registry(root: Path = ROOT) -> list[Entry]:
    raw = tomllib.loads((root / "data" / "databases.toml").read_text("utf-8"))
    return [Entry(**e) for e in raw.get("database", [])]


def check_registry(entries: list[Entry], root: Path) -> None:
    seen_files, seen_buttons = set(), set()
    for e in entries:
        where = f"databases.toml entry {e.file!r}"
        if e.format not in FORMATS:
            raise SyncError(f"{where}: format {e.format!r} is not one of {sorted(FORMATS)}")
        if Path(e.file).suffix.lower() != "." + e.format or Path(e.source).suffix.lower() != "." + e.format:
            raise SyncError(f"{where}: file and source must both end in .{e.format}")
        if not e.source.startswith("data/") or not (root / e.source).is_file():
            raise SyncError(f"{where}: source {e.source!r} is not a file under data/")
        if e.format == "utdb" and not e.parts:
            raise SyncError(f"{where}: a .utdb must list the sources of its halves in parts")
        for p in e.parts:
            if not (root / p).is_file():
                raise SyncError(f"{where}: part {p!r} does not exist")
        if e.card is not None:
            if e.card not in CARDS:
                raise SyncError(f"{where}: card {e.card!r} is not one of {sorted(CARDS)}")
            missing = [k for k in ("button", "label", "title", "kind", "blurb") if not getattr(e, k)]
            if missing:
                raise SyncError(f"{where}: a loadable database needs {', '.join(missing)}")
            if e.card == "xtdb" and e.format != "xtdb" or e.card == "load" and e.format == "xtdb":
                raise SyncError(f"{where}: .xtdb files load on the xtdb card, everything else on the load card")
        if e.file in seen_files or (e.button and e.button in seen_buttons):
            raise SyncError(f"{where}: duplicate file or button id")
        seen_files.add(e.file)
        if e.button:
            seen_buttons.add(e.button)


def unregistered_web_files(entries: list[Entry], root: Path) -> list[str]:
    registered = {e.file for e in entries}
    return sorted(p.name for p in (root / "web").iterdir()
                  if p.is_file() and p.suffix.lower().lstrip(".") in FORMATS and p.name not in registered)


def gitignored(entries: list[Entry], root: Path) -> list[str]:
    """Shipped files that .gitignore would keep out of the repo (web/*.dat needs a whitelist line)."""
    paths = [f"web/{e.file}" for e in entries]
    r = subprocess.run(["git", "check-ignore", "--no-index", *paths], cwd=root, capture_output=True, text=True)
    return r.stdout.split()


def drifted(entries: list[Entry], root: Path) -> list[Entry]:
    out = []
    for e in entries:
        dst = root / "web" / e.file
        if not dst.is_file() or not filecmp.cmp(root / e.source, dst, shallow=False):
            out.append(e)
    return out


def render_block(entries: list[Entry], card: str, eol: str = "\n") -> str:
    attr = CARDS[card]
    return eol.join(
        f'{BUTTON_INDENT}<button class="filebtn ghost" id="{html.escape(e.button)}" type="button" '
        f'{attr}="{html.escape(e.file)}">{html.escape(e.label)}</button>'
        for e in entries if e.card == card)


def with_blocks(index_html: str, entries: list[Entry], eol: str = "\n") -> str:
    for card in CARDS:
        begin = f"<!-- shipped-databases:{card} (generated from data/databases.toml by scripts/sync_databases.py) -->"
        end = f"<!-- /shipped-databases:{card} -->"
        head, sep, rest = index_html.partition(begin)
        _, sep2, tail = rest.partition(end)
        if not sep or not sep2:
            raise SyncError(f"web/index.html: the {card} button markers are missing")
        index_html = f"{head}{begin}{eol}{render_block(entries, card, eol)}{eol}{BUTTON_INDENT}{end}{tail}"
    return index_html


def uncommitted(paths: list[str], root: Path) -> set[str]:
    r = subprocess.run(["git", "status", "--porcelain", "--", *paths], cwd=root, capture_output=True, text=True)
    return {ln[3:].strip() for ln in r.stdout.splitlines()}


def sync(root: Path = ROOT, check: bool = False, committed_only: bool = False,
         force: bool = False) -> list[str]:
    """Return what changed (or, with check, what would change). Raises SyncError on a refusal.

    A web/ copy with uncommitted edits is someone's work in progress and is never overwritten
    unless force is set; the edits belong in the source. committed_only, for unattended runs,
    also holds back a copy whose source has uncommitted edits.
    """
    entries = load_registry(root)
    check_registry(entries, root)
    stray = unregistered_web_files(entries, root)
    if stray:
        raise SyncError(f"web/ holds database files with no registry entry: {', '.join(stray)}")
    hidden = gitignored(entries, root)
    if hidden:
        raise SyncError(f".gitignore would hide {', '.join(hidden)}; add a !<path> whitelist line")
    changes = []
    drift = drifted(entries, root)
    dirty = uncommitted([p for e in drift for p in (e.source, f"web/{e.file}")], root) if drift else set()
    for e in drift:
        if f"web/{e.file}" in dirty and not force:
            changes.append(f"held: web/{e.file} has uncommitted edits; move them into {e.source} "
                           "(or rerun with --force to discard them)")
            continue
        if committed_only and e.source in dirty:
            changes.append(f"held: web/{e.file} not updated, {e.source} has uncommitted edits")
            continue
        changes.append(f"web/{e.file} {'differs from' if (root / 'web' / e.file).exists() else 'missing, copy of'} {e.source}")
        if not check:
            shutil.copyfile(root / e.source, root / "web" / e.file)
    index = root / "web" / "index.html"
    # newline="" keeps the file's own line endings byte for byte
    with open(index, encoding="utf-8", newline="") as f:
        current = f.read()
    eol = "\r\n" if "\r\n" in current else "\n"
    wanted = with_blocks(current, entries, eol)
    if wanted != current:
        changes.append("web/index.html load buttons out of date with the registry")
        if not check:
            with open(index, "w", encoding="utf-8", newline="") as f:
                f.write(wanted)
    return changes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="report only; exit 1 if anything is out of sync")
    ap.add_argument("--committed-only", action="store_true",
                    help="leave a web/ copy alone when its source has uncommitted edits (for automatic runs)")
    ap.add_argument("--force", action="store_true",
                    help="overwrite web/ copies even when they carry uncommitted edits")
    args = ap.parse_args()
    try:
        changes = sync(check=args.check, committed_only=args.committed_only, force=args.force)
    except SyncError as e:
        print(f"sync_databases: {e}", file=sys.stderr)
        return 1
    for c in changes:
        print(c if c.startswith("held:") else ("out of sync: " if args.check else "synced: ") + c)
    if not changes:
        print("databases in sync")
    return 1 if args.check and changes else 0


if __name__ == "__main__":
    sys.exit(main())
