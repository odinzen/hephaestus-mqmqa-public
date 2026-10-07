"""Three-way joint fit of the MgO-SiO2 liquid (2026-10-03): the binary, the CaO-MgO-SiO2 face
(joint_cms.py) and the FeO-MgO-SiO2 ternary together, each ternary with its three ternary terms.

The MgO(l) heat capacity trades the binary's MgO side against the ternary interiors, which lie
300-900 K lower. Fitted with the binary and the CaO-MgO-SiO2 face alone it went to 31 J/K and put
the FeO-MgO-SiO2 olivine field 67 K and its solidus 64-79 K low; held at its 17.7 J/K prior it
left the binary's forsterite 80 K low. Here the FeO-MgO-SiO2 data vote too: the Bowen & Schairer
1935 liquidus (37 points) and 12 of the 21 Nafziger & Muan 1967 solidus points, each bracketed
around its measured value (report() checks all 21). The enstatite correction is held at its stored
value, so the ternary files' orthopyroxene is the shipped one.

Run:  python joint3.py --p0=<22 values> [--fit] [--workers=N]
      (joint_cms vector, then fesi_mg, mgsi_fe, feo_mgo in J)
"""
import contextlib
import csv
import importlib.util
import io
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import joint_cms as jc                   # noqa: E402
import mqmqa                             # noqa: E402
from mqmqa import vis3d                  # noqa: E402

a = jc.a
D = HERE.parents[1]


def _load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


fms = _load("joint3_fms_bd", D / "feo-mgo-sio2" / "build_dat.py")
bc = _load("joint3_fms_bc", D / "feo-mgo-sio2" / "build_combined_dat.py")
bs = _load("joint3_bs", D / "feo-mgo-sio2" / "bs1935_liquidus.py")
chk = _load("joint3_chk", D / "feo-mgo-sio2" / "assessment" / "check.py")
mgo = fms._mgo

ROWS = list(csv.DictReader(open(bs.TABLE, encoding="ascii")))
COMPS = [bs.cation_fractions(r) for r in ROWS]
T_LIQ = np.array([float(r["T_C"]) + 273.15 for r in ROWS])
SOL_FIT = [chk.TABLE6[i] for i in (0, 2, 4, 6, 7, 8)] + [chk.TABLE10[i] for i in (0, 2, 4, 5, 8, 10)]
SOL_ALL = chk.TABLE6 + chk.TABLE10
SIG_T, TERN_PRIOR, PRIOR = 15.0, 30000.0, 15000.0      # as data/feo-mgo-sio2/assessment
T_LO, T_HI = 1350.0, 2300.0
NC = jc.NB + 3                                           # FeO-MgO-SiO2 terms start here
NAMES = ["fesi_mg", "mgsi_fe", "feo_mgo"]


def fms_file(pp):
    """The FeO-MgO-SiO2 combined file for parameter vector pp, as a Database."""
    nb, t = pp[:jc.NB], pp[NC:]
    mgo.OXIDES["MgO"]["dCp_fus"] = nb[-3]
    mgo.MGSI_SRO_X = 1.0 / 3.0 + nb[a.NLIQ]
    mgsi = a.liquid_excess(nb, li=(2, 3, 4, 4))
    tmp = Path(tempfile.gettempdir()) / f"_joint3_fms_{os.getpid()}"
    tmp.mkdir(exist_ok=True)
    bc.LIQ, bc.OUT = tmp / "liq.dat", tmp / "combined.dat"
    bc.LIQ.write_text(fms.build(excess=fms.EX_FEO_SIO2 + mgsi + fms.ternary_excess(tuple(t))), encoding="ascii")
    with contextlib.redirect_stdout(io.StringIO()):
        bc.build()
    return mqmqa.Database.read(str(bc.OUT))


def _has_liquid(db, x2, x3, T):
    return any(p == chk.LIQ and f > 1e-3 for p, f, *_ in vis3d.Hull(db, T).assemblage(x2, x3))


def solidus(db, row, half=120.0, n=7):
    """First-liquid T at one Nafziger & Muan bulk, bracketed around the measured value and widened
    if the bracket misses; nan if no liquid appears below 2000 K."""
    fe, mg, si, t_c = row
    tot = fe + mg + si
    x2, x3 = mg / tot, si / tot
    lo, hi = t_c + 273.15 - half, t_c + 273.15 + half
    while _has_liquid(db, x2, x3, lo) and lo > 900.0:
        lo, hi = lo - 2 * half, lo
    while not _has_liquid(db, x2, x3, hi):
        if hi > 2000.0:
            return float("nan")
        lo, hi = hi, hi + 2 * half
    for _ in range(n):
        m = 0.5 * (lo + hi)
        lo, hi = (lo, m) if _has_liquid(db, x2, x3, m) else (m, hi)
    return 0.5 * (lo + hi)


def fms_model(pp, sol_rows=SOL_FIT):
    db = fms_file(pp)
    liq = []
    for x in COMPS:
        try:
            liq.append(vis3d.liquidus_point(db, x[1], x[2], T_LO, T_HI))
        except vis3d.Vis3DError:
            liq.append((T_HI, None))
    return liq, [solidus(db, r) for r in sol_rows]


def residuals(pp, detail=False):
    pp = np.asarray(pp, float)
    r_jc = jc.residuals(pp[:NC], detail=detail)
    liq, sol = fms_model(pp)
    T = np.array([t for t, _ in liq])
    Ts = np.array([2000.0 if np.isnan(s) else s for s in sol])
    t = pp[NC:]
    r_f = np.concatenate([(T - T_LIQ) / SIG_T, (Ts - np.array([r[3] + 273.15 for r in SOL_FIT])) / SIG_T,
                          [t[0] / TERN_PRIOR, t[1] / TERN_PRIOR, t[2] / PRIOR]])
    if detail:
        return np.concatenate([r_jc[0], r_f]), r_jc, r_f
    return np.concatenate([r_jc, r_f])


def _res(pp):
    return residuals(pp)


def report(pp):
    jc.report(pp[:NC])
    a.vf.RES = a.vf.FINE
    liq, sol = fms_model(np.asarray(pp, float), SOL_ALL)
    dT = {}
    hits = n = 0
    for r, (T, prim), Tm in zip(ROWS, liq, T_LIQ):
        want = bs.MODEL_PHASE[r["primary"]]
        if want:
            n += 1
            hits += prim == want
        dT.setdefault(r["primary"], []).append(T - Tm)
    print("  FeO-MgO-SiO2 (Bowen & Schairer 1935 liquidus, Nafziger & Muan 1967 solidus, all 21):")
    for name, keys in bs.FIELDS.items():
        d = np.concatenate([dT[k] for k in keys if k in dT])
        print(f"    {name:9s} field: {len(d):2d} points, mean {d.mean():+.0f} K, mean absolute {np.abs(d).mean():.0f} K")
    print(f"    primary phase as measured: {hits} of {n}")
    Ts = np.array(sol)
    Tm = np.array([r[3] + 273.15 for r in SOL_ALL])
    for tag, sl in (("solidus ol + px (Table 6)", slice(0, 9)), ("solidus ol + mw (Table 10)", slice(9, 21))):
        d = Ts[sl] - Tm[sl]
        print(f"    {tag}: mean {np.nanmean(d):+.0f} K, mean absolute {np.nanmean(np.abs(d)):.0f} K")
    print(f"  ternary terms: CaO-MgO-SiO2 {[round(v) for v in pp[jc.NB:NC]]}, FeO-MgO-SiO2 {[round(v) for v in pp[NC:]]} J")


if __name__ == "__main__":
    p0 = next(([float(v) for v in arg[5:].split(",")] for arg in sys.argv if arg.startswith("--p0=")), None)
    if p0 is None or len(p0) != NC + 3:
        sys.exit(f"--p0 needs {NC + 3} values")
    # --dcp=X holds MGO_LIQ_DCP at X (as in assess.py)
    for arg in sys.argv:
        if arg.startswith("--dcp="):
            p0[jc.NB - 3] = float(arg[6:])
            a.LOWER[-3], a.UPPER[-3] = p0[jc.NB - 3], p0[jc.NB - 3] + 1e-6
    workers = next((int(arg.split("=", 1)[1]) for arg in sys.argv if arg.startswith("--workers=")), 12)
    pp = jc.fit(p0, workers, resfun=_res, n_terms=6) if "--fit" in sys.argv else p0
    report(pp)
    print("\n  params:", [round(float(x), 1) for x in pp])
    print("  params_full:", ",".join(repr(float(x)) for x in pp))
