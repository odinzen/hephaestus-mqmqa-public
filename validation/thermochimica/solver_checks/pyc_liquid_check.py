"""MQMQA liquids: the reported potentials against pycalphad's liquid alone at the liquid's
reported composition. pycalphad's MQMQA energy is the model Hephaestus's was translated from,
so this checks the potentials (solver and finish), not the model. Points where pycalphad
splits the liquid into two sets are skipped, as the protocol rule says.

    python pyc_liquid_check.py RESULTS.json
"""
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
from pycalphad import Database, equilibrium, variables as v  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "python"))
import mqmqa  # noqa: E402

R_ = Path(__file__).resolve().parents[3]
DATA = Path(os.environ.get("THERMOCHIMICA_DATA", "../thermochimica-ref/data"))
cond = json.loads((R_ / "validation/thermochimica/conditions.json").read_text(encoding="utf-8"))
dbname = {c["id"]: c.get("database") for c in cond["conditions"] + cond["extended_grid"]}
pts = json.load(open(sys.argv[1]))["points"]
cache, worst, n = {}, 0.0, 0
for k, p in pts.items():
    if p["class"] != "computed":
        continue
    name = dbname[k]
    if name not in cache:
        hdb = mqmqa.Database.read(str(DATA / name))
        cache[name] = (hdb, None)
    hdb, pdb = cache[name]
    for s in p["phases"]:
        pi = hdb.phase_index(s["phase"])
        if pi < 0 or hdb.phase_kind(pi) != 0:
            continue
        if pdb is None:
            pdb = Database(str(DATA / name))
            cache[name] = (hdb, pdb)
        phase = next(ph for ph in pdb.phases if ph.upper() == s["phase"].upper())
        x = {e.upper(): val for e, val in s["x"].items() if val > 1e-12}
        els = sorted(x)
        comps = els + ["VA"]
        conds = {v.T: p["T_K"], v.P: p["P_atm"] * 101325.0, v.N: 1.0}
        for e in els[1:]:
            conds[v.X(e)] = x[e]
        try:
            eq = equilibrium(pdb, comps, [phase], conds)
        except Exception as exc:
            print(f"{k:22s} {name:16s} {s['phase']:10s} pycalphad failed: {str(exc)[:80]}")
            continue
        phases = [str(ph) for ph in np.ravel(eq.Phase.values) if str(ph)]
        if len(phases) > 1:
            print(f"{k:22s} {name:16s} {s['phase']:10s} skipped: pycalphad splits the liquid")
            continue
        mu = {str(c): float(m) for c, m in zip(eq.component.values, np.ravel(eq.MU.values))}
        dev = max(abs(mu[e] - p["mu_J_per_mol"][next(q for q in p["mu_J_per_mol"] if q.upper() == e)]) for e in els)
        if not np.isfinite(dev):
            print(f"{k:22s} {name:16s} {s['phase']:10s} pycalphad gave no potentials (NaN)")
            continue
        n += 1
        worst = max(worst, dev)
        print(f"{k:22s} {name:16s} {s['phase']:10s} max |dmu| vs pycalphad {dev:9.4f} J/mol")
print(f"{n} liquids checked, largest deviation {worst:.4f} J/mol")
