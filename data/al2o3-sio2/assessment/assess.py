"""Assess the Al2O3-SiO2 liquid against Bowen & Greig (1924), the measurements that replaced the
sillimanite picture of Rankin & Wright (1915) the v0.1 fit used.

Each liquidus point is scored at the lowest temperature where the liquid sits on the lower hull
of the liquid, cristobalite, mullite and corundum, so a metastable liquidus cannot count. The
eutectic enters by temperature and composition. Mullite's own melting (their 1810 C breakdown to
corundum + liquid, later disputed) is reported, not scored. Temperature parts carry a prior of
0 +- 15 J/K.

Run:  python assess.py [--fit] [--p0=...]
"""
import csv
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[2] / "python"))

import build_dat                                   # noqa: E402
import v01_fit as v1                               # noqa: E402
from mqmqa.dbbuild import ExcessTerm               # noqa: E402

B_PRIOR = 15.0
# (p, q) of each term, as a + b T; p acts on SiO2, q on AlO1.5
TERMS = [(0, 0), (5, 0), (0, 1)]
NAMES = [f"{c}{p}{q}" for p, q in TERMS for c in "ab"]
PRIMARY = {"cristobalite": "SiO2_cristobalite", "mullite": "Al6Si2O13", "corundum": "Al2O3_corundum"}

ROWS = list(csv.DictReader(line for line in open(HERE / "bowen_greig1924.csv")
                           if not line.startswith("#")))


def excess(pp):
    return [ExcessTerm(a=pp[2 * i], b=pp[2 * i + 1], p=p, q=q) for i, (p, q) in enumerate(TERMS)]


def model(pp):
    path = Path(tempfile.gettempdir()) / f"_alsi_assess_{os.getpid()}.dat"
    build_dat.build(excess(pp), out=path)
    return v1.Model(path)


def _hull(m, T, xs):
    pts = [(float(x), m.g_liq(float(x), T), "L") for x in xs]
    for name in build_dat.SOLIDS:
        g, x = m.g_solid(name, T)
        pts.append((x, g, name))
    pts.sort(key=lambda q: q[0])
    h = []
    for p in pts:
        while len(h) >= 2 and ((h[-1][0] - h[-2][0]) * (p[1] - h[-2][1])
                               - (h[-1][1] - h[-2][1]) * (p[0] - h[-2][0])) <= 1e-9:
            h.pop()
        h.append(p)
    return h


def liquidus_point(m, x, lo=1500.0, hi=2500.0, n=24):
    """(T, primary) at x: the lowest T where the liquid at x is on the lower hull."""
    x = round(float(x), 6)      # the grid is rounded; x must be one of its points exactly
    xs = np.unique(np.round(np.concatenate([np.linspace(0.01, 0.99, 50),
                                            x + np.linspace(-0.03, 0.03, 13)]), 6))
    xs = xs[(xs > 0) & (xs < 1)]

    def on_hull(T):
        return any(abs(q[0] - x) < 1e-9 and q[2] == "L" for q in _hull(m, T, xs))
    if on_hull(lo) or not on_hull(hi):
        return None, None
    for _ in range(n):
        mid = 0.5 * (lo + hi)
        lo, hi = (lo, mid) if on_hull(mid) else (mid, hi)
    h = _hull(m, lo, xs)
    for a, b in zip(h, h[1:]):
        if a[0] <= x <= b[0]:
            solids = [q[2] for q in (a, b) if q[2] != "L"]
            return hi, "+".join(solids) or None
    return hi, None


def residuals(pp, detail=False):
    m = model(pp)
    out, rows = [], []

    def add(tag, r, info):
        out.append(r)
        rows.append((tag, r, info))

    for r in ROWS:
        x_meas = v1.wt_al2o3_to_x(float(r["Al2O3_wt"]))
        T_meas = float(r["T_C"]) + 273.15
        sig = float(r["sigma_K"])
        if r["kind"] == "eutectic":
            T, x = v1.eutectic_T(m, "SiO2_cristobalite", "Al6Si2O13")
            add("eutectic T", ((T - T_meas) / sig) if T else 8.0, f"{T:.0f}/{T_meas:.0f}" if T else "none")
            add("eutectic x", ((x - x_meas) / 0.01) if x is not None else 8.0,
                f"{x:.3f}/{x_meas:.3f}" if x is not None else "none")
            continue
        T, prim = liquidus_point(m, x_meas)
        want = PRIMARY[r["primary"]]
        add(f"liq {r['Al2O3_wt']} wt%", ((T - T_meas) / sig) if T else 8.0,
            f"{T:.0f}/{T_meas:.0f} {prim}{'' if prim == want else ' (want ' + want + ')'}" if T else "none")
    for i, name in enumerate(NAMES):
        if name.startswith("b"):
            add(f"prior {name}", pp[i] / B_PRIOR, f"{pp[i]:.2f}")
    res = np.asarray(out, float)
    return (res, rows) if detail else res


def report(pp):
    res, rows = residuals(pp, detail=True)
    for tag, r, info in rows:
        print(f"  {tag:24s} {info:46s} r={r:+6.2f}")
    print(f"  total cost = {0.5 * float(res @ res):.2f}   RMS residual = {np.sqrt(np.mean(res ** 2)):.2f}")


if __name__ == "__main__":
    p0 = [v1.STORED[0], 0.0, v1.STORED[1], 0.0, 0.0, 0.0]
    for arg in sys.argv:
        if arg.startswith("--p0="):
            p0 = [float(v) for v in arg[5:].split(",")]
    if "--fit" in sys.argv:
        scale = np.array([5e4, 10.0] * len(TERMS))
        n = [0]

        # solve in u = 1 + p/scale so a zero start still gets a real finite-difference step
        def fun(u):
            n[0] += 1
            r = residuals((u - 1.0) * scale)
            print(f"  eval {n[0]:3d} cost={0.5 * float(r @ r):.2f} p0="
                  + ",".join(f"{v:.6g}" for v in (u - 1.0) * scale), flush=True)
            return r
        u = least_squares(fun, 1.0 + np.asarray(p0) / scale, diff_step=0.05, max_nfev=60,
                          ftol=1e-4, xtol=1e-4).x
        p0 = list((u - 1.0) * scale)
    report(p0)
    print("\n  params:", dict(zip(NAMES, [round(float(v), 2) for v in p0])))
