"""Assess the CaO-MgO-SiO2 ternary-level terms of the quaternary liquid with every solid and
the three silicate binaries fixed: the Ca-Si interaction with Mg as the additional cation, the
Mg-Si interaction with Ca (Poschmann Eq. 25-26, r = 1), and the CaO-MgO interaction. CaO-MgO
melts are close to ideal, so that one carries a prior of 0 +- 15 kJ.

Data: the Bowen (1914) liquidus of the diopside-forsterite-silica plane (bowen1914_liquidus.csv,
bracket midpoints), on the face file of cms.py.

Run:  python assess.py [--fit] [--p0=a,b,c]
"""
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
sys.path.insert(0, str(HERE))
import cms                # by plain name: the pool workers import it in their own process

SIG_T = 15.0            # K: Bowen's brackets are 2-10 K; the 1914 temperature scale adds the rest
PRIOR = 15000.0
# the two ternary terms trade against each other (2026-09-30: -83 and +50 kJ for a 2% gain),
# so each carries a prior of 0 +- 30 kJ
TERN_PRIOR = 30000.0
T_LO, T_HI = 1300.0, 2300.0
NAMES = ["casi_mg", "mgsi_ca", "cao_mgo"]
WORKERS = int(os.environ.get("CMS_WORKERS", "8"))

ROWS = cms.rows()
COMPS = [cms.cation_fractions(r) for r in ROWS]
T_MEAS = np.array([(float(r["T_lo_C"]) + float(r["T_hi_C"])) / 2 + 273.15 for r in ROWS])

_bq = cms._load("cms_assess_bq", HERE.parent / "build_dat.py")


def excess(pp):
    base = [t for t in _bq.EXCESS if t not in _bq.cms_excess()]
    return base + _bq.cms_excess([(pp[0], 0.0), (pp[1], 0.0), (pp[2], 0.0)])


def write_face(pp):
    path = Path(tempfile.gettempdir()) / f"_cms_assess_{os.getpid()}.dat"
    return cms.build(path, excess(pp))


_db = None


def _init(path):
    global _db
    import mqmqa
    _db = mqmqa.Database.read(path)


def _liq(x):
    from mqmqa import vis3d
    return vis3d.liquidus_point(_db, x[1], x[2], T_LO, T_HI)


def liquidus(pp):
    path = write_face(pp)
    with Pool(WORKERS, initializer=_init, initargs=(path,)) as pool:
        return pool.map(_liq, COMPS, chunksize=1)


def residuals(pp, detail=False):
    model = liquidus(pp)
    T = np.array([t for t, _ in model])
    res = np.concatenate([(T - T_MEAS) / SIG_T, [pp[0] / TERN_PRIOR, pp[1] / TERN_PRIOR,
                                                  pp[2] / PRIOR]])
    return (res, model) if detail else res


def report(pp):
    res, model = residuals(pp, detail=True)
    hits = 0
    groups = {}
    for r, (T, prim), Tm in zip(ROWS, model, T_MEAS):
        ok = prim in cms.allowed(r["primary"])
        hits += ok
        groups.setdefault(r["primary"], []).append(T - Tm)
        print(f"  {r['table']:14s} {r['pyroxene_wt']:>3s}(En{r['En']:>2s} Di{r['Di']:>3s}) "
              f"+{r['added_wt']:>2s} {r['added']:7s} meas {Tm:7.1f}  model {T:7.1f} "
              f"({T - Tm:+5.0f})  {prim}{'' if ok else '  <- primary differs'}")
    for name, d in groups.items():
        d = np.array(d)
        print(f"  {name:22s} {len(d):2d} points, mean {d.mean():+.0f} K, "
              f"mean absolute {np.abs(d).mean():.0f} K, worst {np.abs(d).max():.0f} K")
    print(f"  primary phase as measured: {hits} of {len(ROWS)}")
    print(f"  total cost = {0.5 * float(res @ res):.2f}   RMS residual = {np.sqrt(np.mean(res ** 2)):.2f}")


if __name__ == "__main__":
    p0 = [ab[0] for ab in _bq.CMS_TERNARY]
    for arg in sys.argv:
        if arg.startswith("--p0="):
            p0 = [float(v) for v in arg[5:].split(",")]
    if "--fit" in sys.argv:
        scale = np.array([2e4, 2e4, 1e4])
        n = [0]

        # solve in u = 1 + p/scale: a relative diff_step taken at u = 0 would collapse to a
        # machine-epsilon step, and a zero start would never move
        def fun(u):
            n[0] += 1
            r = residuals((u - 1.0) * scale)
            print(f"  eval {n[0]:3d} {[round(float(v), 1) for v in (u - 1.0) * scale]} cost={0.5 * float(r @ r):.2f}", flush=True)
            return r
        u = least_squares(fun, 1.0 + np.asarray(p0) / scale, diff_step=0.05, max_nfev=40).x
        p0 = list((u - 1.0) * scale)
    report(p0)
    print("\n  params:", dict(zip(NAMES, [round(float(v), 1) for v in p0])))
