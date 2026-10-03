"""Joint fit of the MgO-SiO2 liquid with the CaO-MgO-SiO2 face (2026-10-03).

The binary data all lie at or above 1816 K; the Bowen (1914) liquidus of the
diopside-forsterite-silica plane lies at 1600-1900 K. The MgO(l) heat capacity and the Mg-Si
ordering composition act on both, and fitted to the binary alone they put the ternary interior
125-200 K low (heat capacity 33 J/K) or left the binary's MgO side 80 K off (held at its 17.7 J/K
prior). Here one parameter set answers to both: the binary residuals of assess.py plus the
face liquidus of data/cao-feo-mgo-sio2/assessment with its three ternary terms, fitted together.
The enstatite correction is held at its stored value, so the face's enstatite (copied from the
shipped quaternary file) is the one the binary sees.

Run:  python joint_cms.py --p0=<19 values> [--workers=N]
      (binary vector of assess.py, then casi_mg, mgsi_ca, cao_mgo in J)
"""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import assess as a                       # noqa: E402
import mqmqa                             # noqa: E402
from mqmqa import vis3d                  # noqa: E402

D = HERE.parents[1]


def _load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


cms = _load("joint_cms_face", D / "cao-feo-mgo-sio2" / "assessment" / "cms.py")
bq = _load("joint_bq", D / "cao-feo-mgo-sio2" / "build_dat.py")
mgo = bq._fms._mgo                       # the MgO-SiO2 builder the quaternary liquid reads

ROWS = cms.rows()
COMPS = [cms.cation_fractions(r) for r in ROWS]
T_MEAS = np.array([(float(r["T_lo_C"]) + float(r["T_hi_C"])) / 2 + 273.15 for r in ROWS])
SIG_T, TERN_PRIOR, PRIOR = 15.0, 30000.0, 15000.0      # as data/cao-feo-mgo-sio2/assessment
T_LO, T_HI = 1300.0, 2300.0
SOLIDS = cms.solid_blocks(cms.COMBINED.read_text().splitlines())
NB = a.NLIQ + 4                                          # binary parameters, as in assess.py
NAMES = ["casi_mg", "mgsi_ca", "cao_mgo"]


def face(pp):
    """The CaO-MgO-SiO2 face file for parameter vector pp, as a Database."""
    nb, t = pp[:NB], pp[NB:]
    mgo.OXIDES["MgO"]["dCp_fus"] = nb[-3]
    mgo.MGSI_SRO_X = 1.0 / 3.0 + nb[a.NLIQ]
    mgsi = [dict(code="Q", li=[3, 4, 5, 5], exp=[pw, q, 0, 0], coeffs=[nb[2 * i], nb[2 * i + 1], 0, 0, 0, 0])
            for i, (pw, q) in enumerate(a.TERMS)]
    excess = bq.EX_CAO_SIO2 + mgsi + bq.cms_excess([(t[0], 0.0), (t[1], 0.0), (t[2], 0.0)])
    liq = bq.build(excess=excess, cations=["Ca", "Mg", "Si"]).splitlines()
    head = [" System CaO-MgO-SiO2 face (joint fit scratch file)",
            f"    4    1    3    {len(cms.SOLIDS)}"] + liq[2:6]
    path = Path(tempfile.gettempdir()) / f"_joint_face_{os.getpid()}.dat"
    path.write_text("\n".join(head + liq[6:] + SOLIDS) + "\n", encoding="ascii")
    return mqmqa.Database.read(str(path))


def face_liquidus(pp):
    db = face(pp)
    out = []
    for x in COMPS:
        try:
            out.append(vis3d.liquidus_point(db, x[1], x[2], T_LO, T_HI))
        except vis3d.Vis3DError:
            out.append((T_HI, None))      # no liquidus in the window: charged at its top
    return out


def residuals(pp, detail=False):
    pp = np.asarray(pp, float)
    r_bin = a.residuals(pp[:NB], detail=detail)
    model = face_liquidus(pp)
    T = np.array([t for t, _ in model])
    t = pp[NB:]
    r_face = np.concatenate([(T - T_MEAS) / SIG_T, [t[0] / TERN_PRIOR, t[1] / TERN_PRIOR, t[2] / PRIOR]])
    if detail:
        return np.concatenate([r_bin[0], r_face]), r_bin[1], model, r_face
    return np.concatenate([r_bin, r_face])


def _init_worker():
    a._init_worker()


def _res(pp):
    return residuals(pp)


def fit(p0, workers=12):
    """assess.fit with the face terms appended: parallel forward-difference Jacobian, steps of 3%
    of each parameter's typical size."""
    from multiprocessing import Pool
    _init_worker()
    typ = []
    for _ in a.TERMS:
        typ += [2e4, 10.0]
    typ = np.array(typ + [0.005, 10.0, 10.0, 2000.0, 2e4, 2e4, 1e4])
    lo = np.array(a.LOWER + [-np.inf] * 3, float)
    hi = np.array(a.UPPER + [np.inf] * 3, float)
    lo[NB - 1], hi[NB - 1] = p0[NB - 1], p0[NB - 1] + 1e-6           # enstatite correction held
    n = [0]
    with Pool(workers, initializer=_init_worker) as pool:
        cache = {}

        def fun(x):
            key = tuple(np.round(x, 9))
            if key not in cache:
                cache[key] = _res(x)
                n[0] += 1
                r = cache[key]
                nb = len(r) - len(COMPS) - 3
                print(f"  eval {n[0]:3d}  cost={0.5 * float(r @ r):8.3f} (binary {0.5 * float(r[:nb] @ r[:nb]):.1f}, "
                      f"face {0.5 * float(r[nb:] @ r[nb:]):.1f})  p0=" + ",".join(f"{v:.6g}" for v in x), flush=True)
            return cache[key]

        def jac(x):
            h = 0.03 * np.maximum(np.abs(x), typ)
            h = np.where(x + h > hi, -h, h)
            pts = [x + np.eye(len(x))[i] * h[i] for i in range(len(x))]
            cols = pool.map(_res, pts)
            f0 = fun(x)
            return np.column_stack([(c - f0) / hh for c, hh in zip(cols, h)])

        sol = least_squares(fun, np.asarray(p0, float), jac=jac, x_scale=typ,
                            bounds=(lo, hi), max_nfev=40, ftol=1e-4, xtol=1e-4)
    return sol.x


def report(pp):
    a.vf.RES = a.vf.FINE
    res, rows, model, r_face = residuals(pp, detail=True)
    print("\n  binary (MgO-SiO2):")
    for tag, rr, info in rows:
        if not tag.startswith(("bin_", "prior b")):
            print(f"    {tag:26s} {info:14s}  r={rr:+6.2f}")
    print(f"  Mg-Si ordering peaks at x_SiO2 = {1.0 / 3.0 + pp[a.NLIQ]:.4f}")
    groups, hits = {}, 0
    for r, (T, prim), Tm in zip(ROWS, model, T_MEAS):
        hits += prim in cms.allowed(r["primary"])
        groups.setdefault(r["primary"], []).append(T - Tm)
    print("  CaO-MgO-SiO2 face (Bowen 1914):")
    for name, d in groups.items():
        d = np.array(d)
        print(f"    {name:22s} {len(d):2d} points, mean {d.mean():+.0f} K, mean absolute {np.abs(d).mean():.0f} K")
    print(f"    primary phase as measured: {hits} of {len(ROWS)}")
    nb = len(res) - len(r_face)
    print(f"\n  cost: binary {0.5 * float(res[:nb] @ res[:nb]):.2f}, face {0.5 * float(r_face @ r_face):.2f}, "
          f"total {0.5 * float(res @ res):.2f}")


if __name__ == "__main__":
    p0 = next(([float(v) for v in arg[5:].split(",")] for arg in sys.argv if arg.startswith("--p0=")), None)
    if p0 is None or len(p0) != NB + 3:
        sys.exit(f"--p0 needs {NB + 3} values")
    workers = next((int(arg.split("=", 1)[1]) for arg in sys.argv if arg.startswith("--workers=")), 12)
    pp = fit(p0, workers) if "--fit" in sys.argv else p0
    report(pp)
    print("\n  params:", [round(float(x), 1) for x in pp])
    print("  params_full:", ",".join(repr(float(x)) for x in pp))
