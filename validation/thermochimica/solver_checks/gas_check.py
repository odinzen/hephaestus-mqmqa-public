"""Ideal phases (the gases): mass action from the reported potentials.

For a phase whose energy is exactly ideal mixing of its species (checked at random points),
the reported potentials fix every species fraction, y_j = exp((a_j . mu - g_j) / RT) with g_j
the species' own energy at the pressure. At an equilibrium those fractions sum to one and give
the phase's reported composition. Independent of how the gas was solved, and exact for a gas
of almost one molecule (CO2 over graphite), where solving from the composition is not.

    python gas_check.py RESULTS.json
"""
import json
import math
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import verify_sets as vs  # noqa: E402
from mqmqa._abi import _lib  # noqa: E402

pts = json.load(open(sys.argv[1]))["points"]
worst_sum, worst_x, n = 0.0, 0.0, 0
for k, p in pts.items():
    if p["class"] != "computed":
        continue
    name = vs.dbname[k]
    db = vs._dbs.setdefault(name, vs.mqmqa.Database.read(str(vs.DATA / name)))
    _lib.mqmqa_db_set_pressure(db._db, p["P_atm"] * 101325.0)
    try:
        for s in p["phases"]:
            for pi in [i for i, nm in enumerate(db.phase_names) if nm == s["phase"]]:
                if db.phase_kind(pi) != 1 or len(db.cef_sublattices(pi)) != 1:
                    continue
                ph = vs.Phase(db, pi, p["T_K"])
                if any(c is None for c in ph.comp):
                    continue
                T, nv = p["T_K"], len(ph.names)
                RT = ph.R * T
                g0 = [db.cef_gibbs(pi, [1.0 if j == i else 0.0 for j in range(nv)], T, per_mole_atoms=False)
                      for i in range(nv)]
                rng = random.Random(3)
                ideal = True
                for _ in range(3):
                    y = [rng.random() + 0.01 for _ in range(nv)]
                    y = [v / sum(y) for v in y]
                    g = db.cef_gibbs(pi, y, T, per_mole_atoms=False)
                    ref = sum(y[i] * g0[i] for i in range(nv)) + RT * sum(v * math.log(v) for v in y)
                    if abs(g - ref) > 1e-6 * max(1.0, abs(g)):
                        ideal = False
                if not ideal:
                    continue
                mu = {e.upper(): v for e, v in p["mu_J_per_mol"].items()}
                logs = []
                for i, c in enumerate(ph.comp):
                    if any(e not in mu for e in c):
                        logs.append(-math.inf)
                        continue
                    logs.append((sum(a * mu[e] for e, a in c.items()) - g0[i]) / RT)
                ys = np.exp(np.array(logs))
                tot = ys.sum()
                N = {}
                for i, c in enumerate(ph.comp):
                    for e, a in c.items():
                        N[e] = N.get(e, 0.0) + ys[i] * a
                atoms = sum(N.values())
                xs = {e.upper(): v for e, v in s["x"].items()}
                dx = max(abs(N.get(e, 0.0) / atoms - xs.get(e, 0.0)) for e in set(N) | set(xs))
                n += 1
                worst_sum, worst_x = max(worst_sum, abs(tot - 1.0)), max(worst_x, dx)
                flag = "  <<" if abs(tot - 1.0) > 1e-8 or dx > 1e-8 else ""
                print(f"{k:22s} {name:22s} {s['phase']:10s} sum of fractions - 1 = {tot - 1.0:+.2e}, "
                      f"composition off by {dx:.1e}{flag}")
                break
    finally:
        _lib.mqmqa_db_set_pressure(db._db, 101325.0)
print(f"{n} ideal sets checked; largest |sum - 1| {worst_sum:.1e}, largest composition error {worst_x:.1e}")
