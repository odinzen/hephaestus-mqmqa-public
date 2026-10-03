"""Assess the ternary-level parameters of the FeO-MgO-SiO2 liquid with every solid and both
silicate binaries fixed: two ternary Q terms (Poschmann Eq. 25-26, r = 1), the Fe-Si
interaction with Mg as the additional cation and the Mg-Si interaction with Fe, and the FeO-MgO
interaction. FeO-MgO melts are close to ideal, so that one carries a prior of 0 +- 15 kJ.

Data: the Bowen & Schairer 1935 liquidus (bs1935_table1.csv, 37 points) and the Nafziger &
Muan 1967 solidus (check.py, 21 points). They pull in opposite directions (the liquid of the
magnesian interior against the iron-rich first melt), so both enter the fit.

Run:  python assess.py [--fit]
"""
import csv
import importlib.util
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

SIG_T = 15.0            # K: B&S quote +-4 degC; composition and Fe2O3 add the rest
PRIOR = 15000.0
# the two ternary terms trade against each other (2026-09-30: -83 and +50 kJ for a 2% gain),
# so each carries a prior of 0 +- 30 kJ
TERN_PRIOR = 30000.0
T_LO, T_HI = 1350.0, 2300.0
NAMES = ["fesi_mg", "mgsi_fe", "feo_mgo"]


def _load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


bs = _load("fms_bs1935", HERE.parent / "bs1935_liquidus.py")
ROWS = list(csv.DictReader(open(bs.TABLE, encoding="ascii")))
COMPS = [bs.cation_fractions(r) for r in ROWS]
T_MEAS = np.array([float(r["T_C"]) + 273.15 for r in ROWS])


def write_combined(pp, tag):
    """The combined file with this FeO-MgO interaction, in a temp folder."""
    bd = _load(f"fms_bd_{tag}", HERE.parent / "build_dat.py")
    bc = _load(f"fms_bc_{tag}", HERE.parent / "build_combined_dat.py")
    tmp = Path(tempfile.gettempdir()) / f"_fms_assess_{os.getpid()}_{tag}"
    tmp.mkdir(exist_ok=True)
    bc.LIQ, bc.OUT = tmp / "liq.dat", tmp / "combined.dat"
    bc.LIQ.write_text(bd.build(excess=bd.EX_FEO_SIO2 + bd.EX_MGO_SIO2 + bd.ternary_excess(pp)),
                      encoding="ascii")
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        bc.build()
    return str(bc.OUT)


_db = None


def _init(path):
    global _db
    import mqmqa
    _db = mqmqa.Database.read(path)


def _liq(x):
    from mqmqa import vis3d
    return vis3d.liquidus_point(_db, x[1], x[2], T_LO, T_HI)


def liquidus(pp, tag="fit"):
    path = write_combined(pp, tag)
    with Pool(8, initializer=_init, initargs=(path,)) as pool:
        return pool.map(_liq, COMPS, chunksize=1)


sys.path.insert(0, str(HERE))
import check as chk      # by plain name: the solidus workers must import it in their own process
T_SOL = np.array([r[3] + 273.15 for r in chk.TABLE6 + chk.TABLE10])


def residuals(pp, detail=False):
    model = liquidus(pp)
    T = np.array([t for t, _ in model])
    _, Ts = chk.solidus_all(write_combined(pp, "sol"))
    Ts = np.array(Ts)
    res = np.concatenate([(T - T_MEAS) / SIG_T, (Ts - T_SOL) / SIG_T,
                          [pp[0] / TERN_PRIOR, pp[1] / TERN_PRIOR, pp[2] / PRIOR]])
    return (res, (model, Ts)) if detail else res


def report(pp):
    res, (model, Ts) = residuals(pp, detail=True)
    hits = n = 0
    dT = {}
    for r, (T, prim), Tm in zip(ROWS, model, T_MEAS):
        want = bs.MODEL_PHASE[r["primary"]]
        if want:
            n += 1
            hits += prim == want
        dT.setdefault(r["primary"], []).append(T - Tm)
    for name, keys in bs.FIELDS.items():
        d = np.concatenate([dT[k] for k in keys if k in dT])
        print(f"  {name:9s} field: {len(d):2d} points, mean {d.mean():+.0f} K, "
              f"mean absolute {np.abs(d).mean():.0f} K, worst {np.abs(d).max():.0f} K")
    print(f"  primary phase as measured: {hits} of {n}")
    for tag, sl in (("solidus ol + px (N&M Table 6)", slice(0, 9)), ("solidus ol + mw (Table 10)", slice(9, 21))):
        d = Ts[sl] - T_SOL[sl]
        print(f"  {tag}: mean {np.nanmean(d):+.0f} K, mean absolute {np.nanmean(np.abs(d)):.0f} K")
    print(f"  total cost = {0.5 * float(res @ res):.2f}   RMS residual = {np.sqrt(np.mean(res ** 2)):.2f}")


if __name__ == "__main__":
    bd = _load("fms_bd_main", HERE.parent / "build_dat.py")
    p0 = list(getattr(bd, "TERNARY_EXCESS", (0.0, 0.0, 0.0)))
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
