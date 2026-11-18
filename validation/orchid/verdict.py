"""How far each SGTE dataset traces: one verdict per file from trace.py's output.

    python verdict.py <trace out dir>

Each binary parameter (any parameter not the Gibbs energy of a pure element) is put in one class
by the source its tag names:

  primary          the assessment the dataset is taken from (named in its header and file name)
  paper_verified   another published paper whose DOI record agrees on author, year, volume, page
  convention       a rule the compiler states (same interaction as the stable phase, Laves
                   convention, linear combination of lattice stabilities)
  paper_unchecked  a published paper without a DOI whose record could be checked
  unknown          tagged Null, or no tag at all
  unpublished      unpublished work, a thesis, a report
  database         a compiled database (COST 507, SGTE substance data)
  other            anything else, mostly compilers' later adjustments
  missing_tag      a tag the file's reference list does not define

traced: the assessment is verified and every binary parameter is primary, paper_verified or
convention. traced_except_some: the assessment is verified, some parameters are not.
primary_not_verified / no_primary: the assessment itself could not be verified.
"""
import json
import sys
from collections import Counter
from pathlib import Path

GOOD = ("primary", "paper_verified", "convention")


def kind(tag, txt, primaries, cites):
    if tag in primaries:
        return "primary"
    t = (txt or "").lower()
    if tag in ("NULL", "") or "unknown source" in t:
        return "unknown"
    if tag in ("SAME", "LIN", "REFLAV") or t.startswith("same or similar") or "convention" in t \
            or "linear combination" in t:
        return "convention"
    if txt is None:
        return "missing_tag"
    if any(w in t for w in ("unpublished", "private", "thesis", "report", "personal")):
        return "unpublished"
    if txt in cites:
        return "paper_verified" if cites[txt]["status"] == "verified" else "paper_unchecked"
    if "database" in t or t.startswith("sgte") or "cost" in t:
        return "database"
    return "other"


def main():
    out_dir = Path(sys.argv[1])
    files = json.loads((out_dir / "files.json").read_text(encoding="utf-8"))
    cites = json.loads((out_dir / "citations.json").read_text(encoding="utf-8"))
    rows, verdicts, totals = [], Counter(), Counter()
    for f in files:
        k = Counter()
        for tag, n in f["tags"].items():
            k[kind(tag, f["refs"].get(tag), f["primary_tags"], cites)] += n
        status = [cites[t]["status"] if t in cites else "not_a_paper" for t in f["primary_refs"]]
        if not f["primary_refs"]:
            v = "no_primary"
        elif "verified" not in status:
            v = "primary_not_verified"
        elif sum(k[g] for g in GOOD) == sum(k.values()):
            v = "traced"
        else:
            v = "traced_except_some"
        verdicts[v] += 1
        totals.update(k)
        rows.append({**f, "param_kinds": dict(k), "primary_status": status, "verdict": v})
    (out_dir / "verdicts.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print("files by verdict", dict(verdicts.most_common()))
    print("binary parameters by source", dict(totals.most_common()))


if __name__ == "__main__":
    main()
