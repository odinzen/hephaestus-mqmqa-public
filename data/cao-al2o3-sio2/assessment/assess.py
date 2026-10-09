"""Assess the ternary-level terms of the CaO-Al2O3-SiO2 liquid with every solid and the three
binaries fixed: the Ca-Si interaction with Al as the additional cation, the Al-Si interaction
with Ca and the Ca-Al interaction with Si (Poschmann Eq. 25-26, r = 1).

Data: the Rankin & Wright (1915) liquidus (rankin1915_liquidus.csv) and the 45 measured silica
activities that validate_kt.py reads (24 by gas-slag equilibrium, Kay & Taylor 1960; 21 by KEMS,
Zaitsev 1997); the first term
was fitted to the Zaitsev points alone in v0.2, so both sets enter together here. The two new
terms carry a prior of 0 +- 50 kJ.

Run:  python assess.py [--fit] [--p0=a,b,c] [--si-group=N]
"""
import csv
import json
import math
import os
import sys
import tempfile
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "python"))
sys.path.insert(0, str(HERE.parent))

import build_dat as bd          # noqa: E402
import validate_kt as kt        # noqa: E402

SIG_T = 20.0            # K: Rankin quote +-2 to +-20 degC by field; the 1915 scale adds some
SIG_LNA = 0.5           # ln a(SiO2): the scatter between the two KEMS studies
PRIOR = 50000.0
T_LO, T_HI = 1300.0, 2700.0
NAMES = ["casi_al", "alsi_ca", "caal_si"]
WORKERS = int(os.environ.get("CAS_WORKERS", "8"))
SI_GROUP = next((int(a.split("=")[1]) for a in sys.argv if a.startswith("--si-group=")),
                bd.SI_GROUP)

# Rankin & Wright's alumina field may hold hibonite, unknown in 1915 (their supposed new
# compound there "proved to be alumina")
MODEL = {"pseudowollastonite": "CASIO3", "anorthite": "CAAL2SI2O8", "gehlenite": "CA2AL2SIO7",
         "corundum": {"AL2O3_CORUNDUM", "CAAL12O19"}, "Ca2SiO4": "CA2SIO4", "CaAl4O7": "CAAL4O7",
         "CaAl2O4": "CAAL2O4", "Ca3Al2O6": "CA3AL2O6", "C12A7": "CA12AL14O33",
         "mullite": "AL6SI2O13", "silica": "SIO2_CRISTOBALITE", "rankinite": "CA3SI2O7"}
M = {"CaO": 56.077, "Al2O3": 101.961, "SiO2": 60.084}

# Dry slags: Rankin & Wright worked in air, and their two eutectics with 5CaO.3Al2O3 (Ca12Al14O33,
# stable only with absorbed water) are left out of the dry assessment.
ROWS = [r for r in csv.DictReader(line for line in open(HERE / "rankin1915_liquidus.csv", encoding="ascii")
                                  if not line.startswith("#")) if "C12A7" not in r["primary"]]


def cation_fractions(r):
    n = [float(r["CaO"]) / M["CaO"], 2 * float(r["Al2O3"]) / M["Al2O3"], float(r["SiO2"]) / M["SiO2"]]
    return [v / sum(n) for v in n]


COMPS = [cation_fractions(r) for r in ROWS]
T_MEAS = np.array([float(r["T_C"]) + 273.15 for r in ROWS])


def _activity_points():
    """(id, T, composition, a_SiO2) from measured_asio2.csv, the file validate_kt.py reads."""
    with open(kt.MEASURED, newline="", encoding="utf-8") as f:
        return [(a["id"], float(a["T_K"]), kt.parse_composition(a["composition"]), float(a["a_SiO2"]))
                for a in csv.DictReader(f)]


ACT = _activity_points()


def write_dat(pp):
    path = Path(tempfile.gettempdir()) / f"_cas_assess_{os.getpid()}.dat"
    bd.build(out=path, ternary=dict(zip(NAMES, pp)), si_group=SI_GROUP)
    return str(path)


_db = _pdb = None


def _init(path):
    global _db, _pdb
    import mqmqa
    from pycalphad import Database
    _db, _pdb = mqmqa.Database.read(path), Database(path)


def _liq(x):
    from mqmqa import vis3d
    try:
        return vis3d.liquidus_point(_db, x[1], x[2], T_LO, T_HI, x_tol=3e-3, max_refine=40)
    except vis3d.Vis3DError as e:
        return float("nan"), f"failed: {e}"


def _act(pt):
    from pycalphad import equilibrium, variables as v
    _, T, x, _ = pt
    n = {"CA": x.get("CaO", 0.0), "AL": 2 * x.get("Al2O3", 0.0), "SI": x.get("SiO2", 0.0)}
    n["O"] = x.get("CaO", 0.0) + 3 * x.get("Al2O3", 0.0) + 2 * x.get("SiO2", 0.0)
    tot = sum(n.values())
    r = equilibrium(_pdb, ["CA", "AL", "SI", "O"], ["CAO-ALO1.5-SIO2-LIQUID"],
                    {v.T: T, v.P: 101325, v.N: 1, v.X("CA"): n["CA"] / tot,
                     v.X("AL"): n["AL"] / tot, v.X("SI"): n["SI"] / tot})
    mu = {c: float(r.MU.sel(component=c).values.ravel()[0]) for c in r.component.values}
    return (mu["SI"] + 2 * mu["O"] - kt.g_cristobalite(T)) / (kt.R * T)


def model(pp):
    path = write_dat(pp)
    with Pool(WORKERS, initializer=_init, initargs=(path,)) as pool:
        liq = pool.map(_liq, COMPS, chunksize=1)
        lna = pool.map(_act, ACT, chunksize=1)
    return liq, np.array(lna)


def residuals(pp, detail=False):
    liq, lna = model(pp)
    T = np.array([t for t, _ in liq])
    rT = np.where(np.isfinite(T), (T - T_MEAS) / SIG_T, 8.0)
    ra = np.where(np.isfinite(lna), (lna - np.log([a[3] for a in ACT])) / SIG_LNA, 8.0)
    res = np.concatenate([rT, ra, [pp[1] / PRIOR, pp[2] / PRIOR]])
    return (res, (liq, lna)) if detail else res


def allowed(primary):
    out = set()
    for p in primary.split("+"):
        out |= MODEL[p] if isinstance(MODEL[p], set) else {MODEL[p]}
    return out


def report(pp):
    res, (liq, lna) = residuals(pp, detail=True)
    hits = 0
    groups = {}
    for r, (T, prim), Tm in zip(ROWS, liq, T_MEAS):
        ok = prim in allowed(r["primary"])
        hits += ok
        key = "eutectics" if r["source"].startswith("point") else r["primary"]
        groups.setdefault(key, []).append(T - Tm)
        print(f"  {r['source']:10s} {r['CaO']:>5s} {r['Al2O3']:>5s} {r['SiO2']:>5s}  meas {Tm:7.1f}  "
              f"model {T:7.1f} ({T - Tm:+5.0f})  {prim}{'' if ok else '  <- want ' + r['primary']}")
    for name, d in groups.items():
        d = np.array(d)
        d = d[np.isfinite(d)]
        print(f"  {name:20s} {len(d):2d} points, mean {d.mean():+.0f} K, mean absolute "
              f"{np.abs(d).mean():.0f} K, worst {np.abs(d).max():.0f} K")
    print(f"  primary phase as measured: {hits} of {len(ROWS)}")
    meas = np.log([a[3] for a in ACT])
    for tag in ("zaitsev", "kay"):
        sel = np.array([tag in a[0] for a in ACT])
        d = lna[sel] - meas[sel]
        print(f"  ln a(SiO2) {tag:8s} n={sel.sum()}  RMS {np.sqrt(np.mean(d ** 2)):.2f}  bias {d.mean():+.2f}")
    print(f"  total cost = {0.5 * float(res @ res):.2f}   RMS residual = {np.sqrt(np.mean(res ** 2)):.2f}")


if __name__ == "__main__":
    p0 = [bd.TERNARY[n] for n in NAMES]
    for arg in sys.argv:
        if arg.startswith("--p0="):
            p0 = [float(v) for v in arg[5:].split(",")]
    if "--fit" in sys.argv:
        scale = np.array([5e4, 5e4, 5e4])
        n = [0]

        # solve in u = 1 + p/scale: a relative diff_step taken at u = 0 would collapse to a
        # machine-epsilon step, and a zero start would never move
        def fun(u):
            n[0] += 1
            r = residuals((u - 1.0) * scale)
            print(f"  eval {n[0]:3d} {[round(float(v), 1) for v in (u - 1.0) * scale]} "
                  f"cost={0.5 * float(r @ r):.2f}", flush=True)
            return r
        u = least_squares(fun, 1.0 + np.asarray(p0) / scale, diff_step=0.05, max_nfev=40).x
        p0 = list((u - 1.0) * scale)
    print(f"  Si chemical group {SI_GROUP}")
    report(p0)
    print("\n  params:", dict(zip(NAMES, [round(float(v), 1) for v in p0])))
