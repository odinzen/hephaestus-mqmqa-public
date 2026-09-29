"""Build web/library.json, the data behind the Database library window.

Inputs are the human-owned shelf list (scripts/library.toml) and a triage snapshot exported
from the assessment workspace:

    python -m workbench.engine.triage --json -o triage.json     # in the workspace
    python scripts/build_library.py triage.json                  # here

Stages and counts come from the snapshot; titles, blurbs and shelves come from the shelf list.
The build refuses, rather than guesses, whenever something could put a private system on a
public page: a proprietary classification, an unlisted public system, or a shelf entry the
snapshot does not know.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHELF_FILE = ROOT / "scripts" / "library.toml"
WEB = ROOT / "web"

KINDS = {"slag", "salt", "alloy", "oxide", "reference"}
SHELVES = {"in_progress", "planned"}
SHOWABLE = {"public_academic", "in_development"}

# Public wording for the workspace readiness ladder (workbench.engine.triage, stages 0-5).
PUBLIC_STAGES = ["Sources gathered", "Data extracted", "Model drafted", "Endmember data built"]
STAGE_INDEX = {0: 0, 1: 0, 2: 1, 3: 2, 4: 2, 5: 3}


class LibraryError(ValueError):
    pass


@dataclass
class Shipped:
    button: str
    file: str
    title: str
    kind: str
    blurb: str


@dataclass
class Announced:
    id: str
    title: str
    kind: str
    shelf: str
    blurb: str
    stage: int
    stage_label: str
    papers: int
    measurements: int
    phase_equilibria: int


def _check_kind(kind: str, where: str) -> None:
    if kind not in KINDS:
        raise LibraryError(f"{where}: kind {kind!r} is not one of {sorted(KINDS)}")


def shipped(entries: list[dict], index_html: str, web: Path) -> list[Shipped]:
    out = []
    for e in entries:
        s = Shipped(**e)
        _check_kind(s.kind, f"available {s.button}")
        if not re.search(rf'id="{re.escape(s.button)}"', index_html):
            raise LibraryError(f"available {s.title!r}: no button id={s.button!r} in web/index.html")
        if not (web / s.file).is_file():
            raise LibraryError(f"available {s.title!r}: web/{s.file} does not exist")
        out.append(s)
    return out


def announced(entries: list[dict], triage: list[dict]) -> list[Announced]:
    by_id = {r["id"]: r for r in triage}
    listed = {e["id"] for e in entries}
    # A system the workspace already marks public must be placed on a shelf deliberately,
    # so a newly public system never goes missing from, or sneaks onto, the page unreviewed.
    for r in triage:
        if r.get("classification") == "public_academic" and r["id"] not in listed:
            raise LibraryError(f"{r['id']} is public_academic but has no entry in library.toml")
    out = []
    for e in entries:
        sid = e["id"]
        r = by_id.get(sid)
        if r is None:
            raise LibraryError(f"{sid}: not in the triage snapshot (renamed or removed?)")
        cls = r.get("classification")
        if cls not in SHOWABLE:
            raise LibraryError(f"{sid}: classification {cls!r} can never be shown publicly")
        if "propri" in (r.get("status") or "").lower():
            raise LibraryError(f"{sid}: workspace status mentions proprietary; resolve before announcing")
        if e["shelf"] not in SHELVES:
            raise LibraryError(f"{sid}: shelf {e['shelf']!r} is not one of {sorted(SHELVES)}")
        _check_kind(e["kind"], sid)
        stage = STAGE_INDEX[int(r["stage"])]
        out.append(Announced(
            id=sid, title=e["title"], kind=e["kind"], shelf=e["shelf"], blurb=e["blurb"],
            stage=stage, stage_label=PUBLIC_STAGES[stage],
            papers=int(r.get("n_papers") or 0),
            measurements=int(r.get("n_measurements") or 0),
            phase_equilibria=int(r.get("n_phase_equilibrium") or 0),
        ))
    return out


def build(triage: list[dict], shelf: dict, index_html: str, web: Path, as_of: str) -> dict:
    return {
        "as_of": as_of,
        "stages": PUBLIC_STAGES,
        "available": [asdict(s) for s in shipped(shelf.get("available", []), index_html, web)],
        "systems": [asdict(a) for a in announced(shelf.get("system", []), triage)],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("triage", type=Path, help="triage JSON exported from the assessment workspace")
    ap.add_argument("-o", "--out", type=Path, default=WEB / "library.json")
    args = ap.parse_args()
    triage = json.loads(args.triage.read_text("utf-8"))
    shelf = tomllib.loads(SHELF_FILE.read_text("utf-8"))
    try:
        data = build(triage, shelf, (WEB / "index.html").read_text("utf-8"), WEB, date.today().isoformat())
    except LibraryError as e:
        print(f"build_library: {e}", file=sys.stderr)
        return 1
    args.out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", "utf-8")
    print(f"wrote {args.out.relative_to(ROOT)}: {len(data['available'])} available, "
          f"{len(data['systems'])} announced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
