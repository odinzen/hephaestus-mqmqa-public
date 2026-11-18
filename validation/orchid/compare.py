"""Hephaestus vs pycalphad on ORCHID files: every phase's G at random site fractions and T.

    python -I compare.py <databases dir> <hephaestus python dir> <file list> <out.jsonl> [workers]

One subprocess per file. Reports the largest difference per file in J/mol of atoms.
"""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CHILD = r"""
import json, sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, sys.argv[2])
import numpy as np
from mqmqa import Database
from pycalphad import Database as PDatabase, calculate
path = sys.argv[1]
out = {"phases": 0, "points": 0, "worst": 0.0, "worst_at": None, "skipped": []}
db = Database.read(path)
try:
    pdb = PDatabase(path)
except Exception as e:
    print(json.dumps({"pycalphad_error": f"{type(e).__name__}: {str(e)[:200]}"})); sys.exit()
comps = [e for e, m in db.elements] + ["VA"]
rng = np.random.default_rng(11)
# only temperatures the file declares valid: up to the lowest stated upper limit of a PARAMETER
import re
text = open(path, encoding="latin-1").read()
body = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("$"))
lims = [float(x) for x in re.findall(r"(?is)\bPAR\w*\s+[^!]*?;\s*([0-9.]+)\s+N\b[^!]*!", body)]
lo, hi = 300.0, min([2500.0] + [x for x in lims if x > 400.0])
out["t_max"] = hi
for pname in db.phase_names:
    p = db.phase_index(pname)
    subls = db.cef_sublattices(p)
    if pname not in pdb.phases:
        out["skipped"].append(pname); continue
    out["phases"] += 1
    for _ in range(4):
        T = float(rng.uniform(lo, hi))
        Y, Yp = [], []
        for sl in subls:
            y = rng.uniform(0.02, 1.0, len(sl["constituents"]))
            y = list(y / y.sum())
            Y += y
            # pycalphad orders each sublattice's constituents by name
            Yp += [v for _, v in sorted(zip(sl["constituents"], y))]
        try:
            ours = db.cef_gibbs(p, Y, T, per_mole_atoms=True)
            res = calculate(pdb, comps, pname, T=T, P=101325, N=1, points=np.array([Yp]))
            theirs = float(res.GM.values.squeeze())
        except Exception as e:
            out["skipped"].append(f"{pname}: {type(e).__name__}: {str(e)[:120]}"); break
        d = abs(ours - theirs)
        out["points"] += 1
        if d > out["worst"] or not np.isfinite(d):
            out["worst"], out["worst_at"] = float(d), [pname, round(T, 1), ours, theirs]
for i, name in enumerate(db.stoich):
    if name not in pdb.phases:
        out["skipped"].append(name); continue
    ph = pdb.phases[name]
    atoms = sum(float(r) for r, c in zip(ph.sublattices, ph.constituents)
                if {str(s) for s in c} != {"VA"})
    out["phases"] += 1
    for _ in range(3):
        T = float(rng.uniform(lo, hi))
        try:
            ours = db.stoich_gibbs(i, T) / atoms
            theirs = float(calculate(pdb, comps, name, T=T, P=101325, N=1).GM.values.squeeze())
        except Exception as e:
            out["skipped"].append(f"{name}: {type(e).__name__}: {str(e)[:120]}"); break
        d = abs(ours - theirs)
        out["points"] += 1
        if d > out["worst"] or not np.isfinite(d):
            out["worst"], out["worst_at"] = float(d), [name, round(T, 1), ours, theirs]
print(json.dumps(out))
"""


def one(path, pydir):
    try:
        p = subprocess.run([sys.executable, "-I", "-c", CHILD, str(path), pydir],
                           capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    line = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else ""
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return {"error": f"rc={p.returncode}: {p.stderr.strip()[-400:]}"}


def main():
    root, pydir, flist, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
    workers = int(sys.argv[5]) if len(sys.argv) > 5 else 4
    files = [l.strip() for l in flist.read_text(encoding="utf-8").splitlines() if l.strip()]
    with ThreadPoolExecutor(workers) as ex, out.open("w", encoding="utf-8") as fh:
        for i, (f, r) in enumerate(zip(files, ex.map(lambda f: one(root / f, pydir), files)), 1):
            r["file"] = f
            fh.write(json.dumps(r) + "\n")
            fh.flush()
            print(f"{i}/{len(files)}", flush=True)


if __name__ == "__main__":
    main()
