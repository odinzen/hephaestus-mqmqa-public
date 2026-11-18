"""Seal the measured literature values for the held-out test.

    python seal.py my_values.csv [round]

The optional round name (default "round1") keeps separate seals apart. Writes
conditions_<round>.csv beside this script (every column except value and uncertainty),
copies the full file into the sealed folder, and prints its SHA-256. Values are never
printed, so the person writing the code can watch this run without seeing them.
"""
import csv
import hashlib
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEALED_DIR = HERE.parent / "sealed"
HIDDEN = {"value", "uncertainty"}
REQUIRED = ["system", "quantity", "composition", "composition_basis", "value", "unit",
            "source_first_author", "source_year", "table_or_figure"]


def used_sources():
    path = HERE / "USED_SOURCES.txt"
    pairs = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"([A-Z][\w'\-]+).*?((?:18|19|20)\d\d)", line.strip())
            if m:
                pairs.add((m.group(1).split("-")[0].lower(), m.group(2)))
    return pairs


def main(src, rnd="round1"):
    if not SEALED_DIR.is_dir():
        sys.exit(f"No sealed folder at {SEALED_DIR}; run the copy in the resubmission kit.")
    src = Path(src)
    with src.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit("The file has no rows.")
    cols = list(rows[0].keys())
    missing = [c for c in REQUIRED if c not in cols]
    if missing:
        sys.exit(f"Missing columns: {', '.join(missing)}. Start from the template.")

    problems, flagged = [], set()
    used = used_sources()
    for i, r in enumerate(rows, start=2):
        empty = [c for c in REQUIRED if not (r.get(c) or "").strip()]
        if empty:
            problems.append(f"row {i}: empty {', '.join(empty)}")
        key = ((r.get("source_first_author") or "").strip().split()[0:1] or [""])[0].lower()
        if (key, (r.get("source_year") or "").strip()) in used:
            flagged.add(f"{r['source_first_author']} {r['source_year']}")
    dest = SEALED_DIR / f"literature_values_{rnd}.csv"
    if dest.exists():
        sys.exit(f"{dest.name} is already sealed; use a new round name.")
    if problems:
        print("Fix these first (nothing was sealed):")
        print("\n".join(problems[:30]))
        sys.exit(1)

    with (HERE / f"conditions_{rnd}.csv").open("w", newline="", encoding="utf-8") as f:
        keep = [c for c in cols if c not in HIDDEN]
        w = csv.DictWriter(f, fieldnames=["row"] + keep)
        w.writeheader()
        for i, r in enumerate(rows, start=1):
            w.writerow({"row": i, **{c: r[c] for c in keep}})

    shutil.copyfile(src, dest)
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    (HERE / f"SEALED_HASH_{rnd}.txt").write_text(
        f"{digest}  {dest.name}\nsealed {stamp}, {len(rows)} rows\n", encoding="utf-8")

    print(f"Sealed {len(rows)} rows from {len({r['source_first_author'] + r['source_year'] for r in rows})} sources.")
    print(f"Fingerprint (SHA-256): {digest}")
    if flagged:
        print("These sources may already be in a database fit; they will be checked "
              "and, if so, excluded by rule before unsealing:")
        print("  " + "; ".join(sorted(flagged)))


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3) or (len(sys.argv) == 3 and not re.fullmatch(r"[\w\-]+", sys.argv[2])):
        sys.exit(__doc__)
    main(*sys.argv[1:])
