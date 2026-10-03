"""v0.4 assessment of the FeO-SiO2 liquid: the excess and the FeO(l) below-melting correction
fitted at once to the measured activities AND the measured liquidus (dataset.py).

v0.3 took the excess from the activities alone and set the FeO(l) correction by fayalite's
congruent melting alone. That left the wustite liquidus far too high (about 1550 K at the
fayalite composition, so the congruent melting was preempted by wustite + liquid), which no
single correction can fix. Here both enter one weighted least squares, against the solids
the ternaries use: fayalite from data/olivine/endmembers.py (Robie-Hemingway), wustite and
cristobalite from build_dat.

The measured a(FeO) below 1644 K (Bodsworth; Schuhmann-Ensio) are referred to the
silica-free iron-saturated melt at the same temperature, which is supercooled there, so their
level carries that reference's extrapolation (Bjorkman 1985, Calphad 9:271, eq. 12 and the
text around it) and, like the FeO(l) correction, is not measured. They are fitted up to one
common offset in ln a (parameter dlna_low); their composition dependence is data. The 2153 K
set (Distin et al.) is above wustite melting and is fitted absolutely.

Run:  python assess.py [--fit] [--write]
"""
import math
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy.optimize import brentq, least_squares

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[2] / "python"))

import build_dat as bd
import mqmqa
import phase_diagram as pdg
import _activity as act
from mqmqa import equilibrium as eq
import dataset as ds

COMP = pdg.COMPONENTS
SIG_LN_A = 0.05          # read noise of the digitized activities, ln units
# Excess Q terms [0,0] (a + bT), [1,0], [0,3], [0,5]. No [0,1]: in a binary it equals
# [0,0] minus [1,0] exactly. The silica-side [0,5] is what lets the two-liquid field sit
# near its measured temperature; a [0,7] on top bought little and took alternating
# coefficients of up to 178 kJ.
NAMES = ["a00", "b00", "a10", "a03", "a05", "beta", "dlna_low"]
T_FEO_MELT = 1644.0      # below it the activity reference is a supercooled melt
X_SOLID = {"wustite": 0.0, "fayalite": 1.0 / 3.0, "silica": 1.0}


def activity_data():
    rows = []
    for line in (HERE.parent / "activities_feo_bjorkman1985_fig3.csv").read_text().splitlines():
        if line.startswith(("#", "X_FeO")) or not line.strip():
            continue
        p = line.split(",")
        rows.append((float(p[0]), float(p[1]), float(p[3])))
    return rows


def excess_of(pp):
    a00, b00, a10, a03, a05 = pp[:5]
    q = lambda p, q_, c: dict(code="Q", li=[1, 2, 3, 3], exp=[p, q_, 0, 0], coeffs=c)
    return [q(0, 0, [a00, b00, 0, 0, 0, 0]), q(1, 0, [a10, 0, 0, 0, 0, 0]),
            q(0, 3, [a03, 0, 0, 0, 0, 0]), q(0, 5, [a05, 0, 0, 0, 0, 0])]


def build_db(pp):
    import os
    # scratch copy per process (parallel fits), outside the repository
    path = Path(tempfile.gettempdir()) / f"_feo-sio2_assess_{os.getpid()}.dat"
    path.write_text(bd.build(excess_of(pp), version="v0.4", feo_liq_beta=pp[5]), encoding="ascii")
    db = mqmqa.Database.read(str(path))
    return db, db.phase_index("FEO-SIO2-LIQUID")


def g_solid(solid, T):
    if solid == "wustite":
        return pdg.solid_oxide_gibbs(bd.OXIDES["FeO"], T)
    if solid == "silica":
        return pdg.solid_oxide_gibbs(bd.OXIDES["SiO2"], T)
    return pdg.solid_gibbs_per_formula_unit("Fa(fayalite)", T)[0]


def tangent_gap(db, p, solid, x, T, h=2e-4):
    """G_solid minus the liquid tangent at x extended to the solid: < 0 where the solid is
    more stable than the liquid of composition x (below the liquidus)."""
    inp = eq.build_inputs(db, p, T, components=COMP)
    xs = X_SOLID[solid]
    lo, hi = max(x - h, 1e-6), min(x + h, 1 - 1e-6)
    g = lambda xx: pdg.liquid_gibbs_per_formula_unit(inp, xx, T)
    gl = g(x)
    slope = (g(hi) - g(lo)) / (hi - lo)
    return g_solid(solid, T) - (gl + (xs - x) * slope)


def liquidus_T(db, p, solid, x, lo=1000.0, hi=2600.0, extrapolate=True):
    """Liquidus of `solid` at x. With no root in [lo, hi] and extrapolate, a linear
    extrapolation of the tangent gap, compressed (asinh, 300 K scale) beyond the bracket so
    the fit keeps a bounded slope. Without extrapolate: hi if the solid beats the liquid over
    the whole bracket, None if it never does."""
    f = lambda T: tangent_gap(db, p, solid, x, T)
    flo, fhi = f(lo), f(hi)
    if flo * fhi <= 0:
        return brentq(f, lo, hi, xtol=0.05)
    if not extrapolate:
        return hi if flo < 0 else None
    Tx = lo - flo * (hi - lo) / (fhi - flo)
    if Tx < lo:
        return lo - 300.0 * math.asinh((lo - Tx) / 300.0)
    if Tx > hi:
        return hi + 300.0 * math.asinh((Tx - hi) / 300.0)
    return hi if flo < 0 else lo


def binodal(db, p, T, lo=0.40, hi=0.999, n=240):
    """Conjugate liquids (x_lo, x_hi) of the silica-side gap at T, or None. The widest
    liquid-liquid step of the lower hull on a grid, then refined to equal chemical
    potentials."""
    inp = eq.build_inputs(db, p, T, components=COMP)
    g = lambda x: pdg.liquid_gibbs_per_formula_unit(inp, x, T)
    xs = np.linspace(lo, hi, n)
    pts = [(x, g(x)) for x in xs]
    h = []
    for q in pts:
        while len(h) >= 2 and ((h[-1][1] - h[-2][1]) * (q[0] - h[-2][0])
                               >= (q[1] - h[-2][1]) * (h[-1][0] - h[-2][0])):
            h.pop()
        h.append(q)
    steps = [(b[0] - a[0], a[0], b[0]) for a, b in zip(h, h[1:])]
    w, x1, x2 = max(steps)
    if w < 3.0 * (xs[1] - xs[0]):
        return None
    d = 2e-4
    dg = lambda x: (g(x + d) - g(x - d)) / (2 * d)
    for _ in range(30):
        s1, s2 = dg(x1), dg(x2)
        chord = (g(x2) - g(x1)) / (x2 - x1)
        # each end moves until its own slope equals the chord (Newton on the tangent)
        c1 = (dg(x1 + d) - dg(x1 - d)) / (2 * d)
        c2 = (dg(x2 + d) - dg(x2 - d)) / (2 * d)
        n1 = x1 - (s1 - chord) / c1 if c1 > 0 else x1
        n2 = x2 - (s2 - chord) / c2 if c2 > 0 else x2
        n1, n2 = min(max(n1, lo), hi), min(max(n2, lo), hi - 1e-4)
        if abs(n1 - x1) + abs(n2 - x2) < 1e-6:
            break
        x1, x2 = n1, n2
    return x1, x2


def stability_margin(db, p, T, lo, hi, n=60):
    """Smallest d2G/dx2 of the liquid over [lo, hi] in units of RT: negative inside a
    spinodal. With no gap it says how far the liquid is from opening one, which gives the
    fit a slope where a missing gap would otherwise be a flat penalty."""
    inp = eq.build_inputs(db, p, T, components=COMP)
    g = lambda x: pdg.liquid_gibbs_per_formula_unit(inp, x, T)
    d = 2e-3
    return min((g(x + d) - 2 * g(x) + g(x - d)) / (d * d)
               for x in np.linspace(lo + d, hi - d, n)) / (8.3145 * T)


def monotectic_T(db, p, lo=1700.0, hi=2150.0):
    """Temperature at which cristobalite touches the two-liquid common tangent (silica + L1
    + L2), or None with no gap at lo. Outside the bracket, extrapolated as in liquidus_T."""
    def f(T):
        gap = binodal(db, p, T)
        if gap is None:
            return None
        x1, x2 = gap
        inp = eq.build_inputs(db, p, T, components=COMP)
        g = lambda x: pdg.liquid_gibbs_per_formula_unit(inp, x, T)
        chord = (g(x2) - g(x1)) / (x2 - x1)
        return g_solid("silica", T) - (g(x2) + (1.0 - x2) * chord)
    flo = f(lo)
    if flo is None:
        return None
    fhi = f(hi)
    while fhi is None:          # the gap closes below hi: bracket under the consolute
        hi -= 50.0
        fhi = f(hi)
    if flo * fhi <= 0:
        return brentq(f, lo, hi, xtol=0.05)
    Tx = lo - flo * (hi - lo) / (fhi - flo)
    if Tx < lo:
        return lo - 300.0 * math.asinh((lo - Tx) / 300.0)
    return hi + 300.0 * math.asinh((Tx - hi) / 300.0)


def residuals(pp, detail=False):
    db, p = build_db(pp)
    res, rows = [], []
    for X, a, T in activity_data():
        inp = eq.build_inputs(db, p, T, components=COMP)
        am, _ = act.activities(inp, 1.0 - X, T)
        off = pp[6] if T < T_FEO_MELT else 0.0
        r = (np.log(am) + off - np.log(a)) / SIG_LN_A
        res.append(r)
        rows.append((f"a(FeO) X={X:.3f} T={T:.0f}", r, f"{am:.3f}/{a:.3f}"))
    for d in ds.LIQUIDUS:
        sig = max(d["sigT"], 5.0)
        Tl = liquidus_T(db, p, d["solid"], d["x"])
        r = (Tl - d["T"]) / sig
        res.append(r)
        rows.append((f"liq {d['solid']} x={d['x']:.3f}", r, f"{Tl or 0:.1f}/{d['T']:.1f}"))
        # another solid crystallizing first at this composition is a miss of the field
        worst = 0.0
        for other in X_SOLID:
            if other != d["solid"]:
                To = liquidus_T(db, p, other, d["x"], extrapolate=False)
                if To and Tl and To > Tl:
                    worst = max(worst, (To - Tl) / sig)
        res.append(worst)
        rows.append((f"  field {d['solid']} x={d['x']:.3f}", worst, ""))
    m = ds.MONOTECTIC
    Tm = monotectic_T(db, p)
    res.append(((Tm - m["T"]) / m["sigT"]) if Tm else 5.0 + stability_margin(db, p, 1700.0, 0.4, 0.999))
    rows.append(("monotectic T (silica + L1 + L2)", res[-1], f"{Tm:.1f}/{m['T']:.1f}" if Tm else "no gap"))
    gap = binodal(db, p, m["T"])
    for k, tag in ((0, "x_lo"), (1, "x_hi")):
        r = ((gap[k] - m[tag]) / m["sigx"]) if gap else 5.0 + stability_margin(db, p, m["T"], 0.4, 0.999)
        res.append(r)
        rows.append((f"monotectic {tag}", r, f"{gap[k]:.3f}/{m[tag]:.3f}" if gap else "no gap"))
    if detail:
        return np.array(res), rows
    return np.array(res)


def fit(p0):
    n, best = [0], [np.inf]

    def fun(pp):
        n[0] += 1
        r = residuals(pp)
        cost = 0.5 * float(r @ r)
        print(f"  eval {n[0]:3d}  cost={cost:9.3f}", flush=True)
        if cost < best[0]:
            best[0] = cost
            print("  best", [float(f"{v:.8g}") for v in pp], flush=True)
        return r
    # solve in units of each parameter's scale: scipy's finite-difference step is relative
    # to |x| (floored at 1), so a term starting at zero would otherwise get a 0.02 J step
    scale = np.array([2e4, 10.0, 2e4, 2e4, 2e4, 20.0, 0.1])
    sol = least_squares(lambda u: fun(u * scale), np.asarray(p0) / scale,
                        diff_step=0.02, ftol=1e-5, xtol=1e-6, max_nfev=150)
    return sol.x * scale


def report(pp, write=False):
    res, rows = residuals(pp, detail=True)
    for tag, r, info in rows:
        print(f"    {tag:34s} {info:16s} r={r:+6.2f}")
    print(f"\n  total cost = {0.5 * float(res @ res):.3f}   RMS residual = {np.sqrt(np.mean(res ** 2)):.2f}")
    if write:
        (HERE.parent / "FeO-SiO2-liquid.dat").write_text(
            bd.build(excess_of(pp), version="v0.4", feo_liq_beta=pp[5]), encoding="ascii")
        print("  wrote FeO-SiO2-liquid.dat")


if __name__ == "__main__":
    # The assessed liquid is build_dat.ASSESSED_EXCESS and FEO_LIQ_BETA (2026-09-29): total
    # cost 32.58, RMS 1.14. The sub-1644 K activity offset is a property of the data's
    # reference state, not of the database, so it lives in dataset.py. --fit re-runs from here.
    (_, _, a00, b00), (_, _, a10, _), (_, _, a03, _), (_, _, a05, _) = bd.ASSESSED_EXCESS
    p0 = [a00, b00, a10, a03, a05, bd.FEO_LIQ_BETA, ds.DLNA_LOW]
    for arg in sys.argv:
        if arg.startswith("--p0="):
            p0 = [float(v) for v in arg[5:].split(",")]
    pp = fit(p0) if "--fit" in sys.argv else p0
    report(pp, write=("--write" in sys.argv))
    print("\n  params:", dict(zip(NAMES, [round(float(v), 4) for v in pp])))
