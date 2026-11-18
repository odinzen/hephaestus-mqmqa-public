"""Put the SGTE binary datasets Hephaestus reads on the calculator's ORCHID shelf.

    python scripts/import_orchid.py <orchid-project.org checkout> [--tol 0.1]

Every dataset Hephaestus reads (validation/orchid/results/load.jsonl) is shelved. One is marked
checked when every phase matches pycalphad at random compositions and temperatures within the
file's stated range (compare.jsonl, largest difference at most --tol J per mole of atoms) and its
assessment and every binary parameter trace to a verified published source or a stated rule
(verdicts.json, verdict "traced"). Any other carries "check before use" and the reasons. The files
are copied unchanged into web/orchid/sgte-binary/ after their SHA-256 is checked against ORCHID's
MANIFEST.sha256; web/orchid/catalog.json carries each one's source chain and test results.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "validation" / "orchid" / "results"
WEB = ROOT / "web" / "orchid"
HALOGENS = {"F", "Cl", "Br", "I"}
CHALCOGENS = {"O", "S", "Se", "Te"}


def elements_of(stem: str) -> list[str]:
    return re.findall(r"[A-Z][a-z]?", stem.split("-")[0])


def notes_of(text: str) -> list[str]:
    """The compiler's header notes: everything after 'Dataset created' up to the first rule."""
    out, on = [], False
    for line in text.splitlines():
        if not line.startswith("$"):
            break
        s = line.strip("$ ").strip()
        if s.startswith("---"):
            break
        if s.startswith("Dataset created"):
            on = True
        if on and s:
            out.append(s)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("orchid", type=Path)
    ap.add_argument("--tol", type=float, default=0.1)
    a = ap.parse_args()
    src = a.orchid / "data" / "databases" / "sgte-binary"
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=a.orchid, capture_output=True, text=True).stdout.strip()
    manifest = {}
    for line in (src / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        if line.strip():
            sha, name = line.split(None, 1)
            manifest[name.strip().lstrip("*")] = sha

    def by_file(path):
        rows = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                rows[Path(r["file"].replace("\\", "/")).name] = r
        return rows

    load = by_file(RESULTS / "load.jsonl")
    cmp_ = by_file(RESULTS / "compare.jsonl")
    verdicts = {v["file"]: v for v in json.loads((RESULTS / "verdicts.json").read_text(encoding="utf-8"))}
    cites = json.loads((RESULTS / "citations.json").read_text(encoding="utf-8"))

    shelf, reasons = [], {}
    for name, v in sorted(verdicts.items()):
        if not load.get(name, {}).get("ok"):
            reasons["not read by Hephaestus"] = reasons.get("not read by Hephaestus", 0) + 1
            continue
        text = (src / name).read_bytes()
        sha = hashlib.sha256(text).hexdigest()
        if manifest.get(name) != sha:
            raise SystemExit(f"{name}: SHA-256 {sha} is not ORCHID's {manifest.get(name)}")
        els = elements_of(Path(name).stem)
        kind = "salt" if HALOGENS & set(els) else "oxide" if CHALCOGENS & set(els) else "alloy"
        caution = []
        k = v["param_kinds"]
        # a tag like 88CHE can match 88CHE1 and 88CHE2; take a verified one when there is one
        verified = [p for p in v["primary_refs"] if p in cites and cites[p]["status"] == "verified"]
        prim = (verified or v["primary_refs"] or [None])[0]
        if prim is None:
            caution.append("no assessment named")
        elif not verified:
            st = cites.get(prim, {}).get("status", "")
            if prim not in cites:
                caution.append("the assessment is unpublished work" if "unpublished" in prim.lower()
                               else "the assessment is not a journal paper")
            elif st.startswith("mismatch"):
                caution.append("the assessment's DOI record disagrees with the citation")
            else:
                caution.append("the assessment paper has no DOI record to check it against")
        for key, label in (("unknown", "from an unknown source"), ("unpublished", "from unpublished work"),
                           ("other", "from later adjustments"), ("paper_unchecked", "from papers that could not be checked"),
                           ("database", "from compiled databases"), ("missing_tag", "with a source tag the file does not define")):
            if k.get(key):
                caution.append(f"{k[key]} of {sum(k.values())} binary parameters {label}")
        c = cmp_.get(name, {})
        if "worst" not in c:
            caution.append("pycalphad cannot read this file, so it was not compared")
        elif c["worst"] > a.tol:
            caution.append(f"pycalphad reads this file differently (up to {c['worst']:.3g} J/mol)")
        others = []
        for tag, ref in v["refs"].items():
            if ref and ref != prim and ref in cites and cites[ref]["status"] == "verified":
                others.append({"citation": ref, "doi": cites[ref]["doi"], "parameters": v["tags"][tag]})
        shelf.append({
            "file": name, "system": "-".join(els), "kind": kind, "sha256": sha,
            "checked": not caution, "caution": caution,
            "phases": load[name].get("phases"),
            "assessment": {"citation": re.sub(r";[^;]*$", "", prim) if prim else "",
                           "doi": cites[prim]["doi"] if verified else None},
            "other_sources": others,
            "parameters": k,
            "notes": notes_of(text.decode("latin-1")),
            "pycalphad_max_diff": round(c["worst"], 4) if "worst" in c else None,
            "pycalphad_points": c.get("points"),
            "valid_to_K": c.get("t_max"),
        })
    # checked datasets first, then the rest, each in file order
    shelf.sort(key=lambda e: (not e["checked"], e["file"]))
    reasons["shelved, checked"] = sum(e["checked"] for e in shelf)
    reasons["shelved, check before use"] = sum(not e["checked"] for e in shelf)

    dest = WEB / "sgte-binary"
    dest.mkdir(parents=True, exist_ok=True)
    keep = {e["file"] for e in shelf}
    for old in dest.glob("*.tdb"):
        # a file leaving the shelf is removed only when it is byte for byte ORCHID's copy
        if old.name not in keep:
            if manifest.get(old.name) == hashlib.sha256(old.read_bytes()).hexdigest():
                old.unlink()
            else:
                print("left in place, not ORCHID's copy:", old.name)
    for e in shelf:
        shutil.copyfile(src / e["file"], dest / e["file"])
    shutil.copyfile(src / "SOURCE.md", dest / "SOURCE.md")
    catalog = {"orchid_commit": commit, "source_doi": "10.1016/j.calphad.2025.102833",
               "tolerance_J_per_mol_atoms": a.tol, "datasets": shelf, "counts": reasons}
    (WEB / "catalog.json").write_text(json.dumps(catalog, indent=0, ensure_ascii=False), encoding="utf-8")
    print(f"{len(shelf)} datasets shelved from ORCHID {commit[:9]}: {reasons}")


if __name__ == "__main__":
    main()
