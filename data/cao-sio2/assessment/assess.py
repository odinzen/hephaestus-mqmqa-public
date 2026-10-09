"""v0.4 assessment of the CaO-SiO2 liquid on the Robie-Hemingway calcium silicates.

v0.3 fitted the excess to two congruent melting points against Neumann-Kopp compounds,
which run 3-36 kJ away from the measured ones at liquidus temperatures (rankinite worst).
Here the solids are data/cao-sio2/silicates.py, the file the ternaries read, and the liquid
is fitted in one weighted least squares to every measured invariant (dataset.py), the
silica-side two liquids, and the activities. Rankinite's enthalpy of formation is the one
solid quantity assessed with it, held to its +-10 kJ R&H uncertainty by a prior.

Run:  python assess.py [--fit] [--write]
"""
import math
import os
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
import silicates as sil
import _activity as act
import fit_excess as fx
from mqmqa import equilibrium as eq
import dataset as ds

COMP = ["CA", "SI", "O"]
R = 8.3145
# Silica-side polynomial in chi_Si, the form the MgO-SiO2 liquid uses: [0,q] for q = 0, 1, 3,
# 5, 7, the first two with entropy parts. ([1,0] adds nothing: in a binary it equals [0,0]
# minus [0,1] exactly.)
# q = 2 with an entropy part, 2026-10-01: the CaO-side freedom (in a binary a CaO-power term is a
# combination of silica powers 0-2), for the lime liquidus that sat 134 K high at x 0.27
QTERMS = [(0, True), (1, True), (3, False), (5, False), (7, False), (2, True)]
# --qb=3,5: entropy parts on those silica-rich terms as well, each under a 0 +- 15 J/K prior. The
# measured dome closes only 27 K above the monotectic, which an enthalpy-only silica side could not
# reproduce without dragging the silica liquidus down (2026-10-07 refits).
QB = {int(q) for a in sys.argv if a.startswith("--qb=") for q in a[5:].split(",")}
QTERMS = [(q, has_b or q in QB) for q, has_b in QTERMS]
# --qx=4,6,9: further silica powers, enthalpy only (q = 4 and 6 complete the degree-7 polynomial)
QTERMS += [(int(q), int(q) in QB) for a in sys.argv if a.startswith("--qx=") for q in a[5:].split(",")]
SIG_QB = 15.0
NAMES = [n for q, has_b in QTERMS for n in ([f"a0{q}", f"b0{q}"] if has_b else [f"a0{q}"])]
NAMES.append("rankinite_dHf")
W_BASIC = 3.0                    # a lime-side gap is unphysical: weighted above one sigma
# slope of the missing-gap penalty per unit of stability margin (d2G/dx2 over RT)
W_NOGAP = next((float(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--wgap=")), 1.0)
SIG_KT, SIG_STOL = 0.10, 0.50    # ln a; Stolyarova is the documented outlier (fit_excess)
# MatterSim melt mixing enthalpy at x = 0.5, 1900 K, shifted by the potential's formation bias
# against the measured calcium silicates. A model value is data, but low weight until validated
# against experiment, and this potential misses the measured silicate formation enthalpies (9 kJ
# per CaSiO3), so the anchor is wide. -53 kJ corrects the bias, per CaSiO3 (two oxide units), that
# v0.4 applied in full to a per-oxide-unit dH_mix (-58; MLIP audit 2026-10-07). Refits with the
# anchor tightened or removed moved nothing (cost 133.27 / 133.08).
MLIP_DH, SIG_DH = -53000.0, 15000.0
SIG_RANK = 10000.0               # R&H uncertainty of rankinite dHf
# --cao-beta: the supercooled CaO(l) slope (build_dat.CAO_LIQ_BETA) joins the fit as the last
# parameter, under the same 0 +- 5 J/K prior the MgO(l) slope carries
CAO_BETA = "--cao-beta" in sys.argv
SIG_BETA = 5.0
# --sro: the Ca-Si ordering composition joins as the last parameter (offset from 1/3), as in the
# MgO-SiO2 assessment
SRO = "--sro" in sys.argv
I_RANK = -1 - int(CAO_BETA) - int(SRO)
I_BETA = I_RANK + 1
X_SOLID = {name: n_si / (n_ca + n_si) for name, (n_ca, n_si, *_rest) in pdg.SOLIDS.items()}


def excess_of(pp):
    out, i = [], 0
    for q, has_b in QTERMS:
        a, b = pp[i], (pp[i + 1] if has_b else 0.0)
        i += 2 if has_b else 1
        out.append(dict(code="Q", li=[1, 2, 3, 3], exp=[0, q, 0, 0], coeffs=[a, b, 0, 0, 0, 0]))
    return out


def build_db(pp):
    sil.RANKINITE_DHF_SHIFT = float(pp[I_RANK])
    # scratch copy per process (parallel fits), outside the repository
    path = Path(tempfile.gettempdir()) / f"_cao-sio2_assess_{os.getpid()}.dat"
    path.write_text(bd.build(excess_of(pp), version="v0.4",
                             cao_liq_beta=float(pp[I_BETA]) if CAO_BETA else None,
                             x_sro=1.0 / 3.0 + float(pp[-1]) if SRO else None), encoding="ascii")
    db = mqmqa.Database.read(str(path))
    return db, db.phase_index("CAO-SIO2-LIQUID")


def tangent_gap(db, p, solid, x, T, h=2e-4):
    """G_solid minus the liquid tangent at x extended to the solid: < 0 below the liquidus."""
    inp = eq.build_inputs(db, p, T, components=COMP)
    xs = X_SOLID[solid]
    lo, hi = max(x - h, 1e-6), min(x + h, 1 - 1e-6)
    g = lambda xx: pdg.liquid_gibbs_per_formula_unit(inp, xx, T)
    slope = (g(hi) - g(lo)) / (hi - lo)
    return pdg.solid_gibbs_per_formula_unit(solid, T)[0] - (g(x) + (xs - x) * slope)


def liquidus_T(db, p, solid, x, lo=1300.0, hi=3000.0, extrapolate=True):
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


def binodal(db, p, T, lo=0.55, hi=0.9995, n=240):
    """Conjugate liquids (x_lo, x_hi) of the silica-side gap at T, or None: the widest
    liquid-liquid step of the lower hull on a grid, refined to a common tangent."""
    inp = eq.build_inputs(db, p, T, components=COMP)
    g = lambda x: pdg.liquid_gibbs_per_formula_unit(inp, x, T)
    xs = np.linspace(lo, hi, n)
    h = []
    for q in [(x, g(x)) for x in xs]:
        while len(h) >= 2 and ((h[-1][1] - h[-2][1]) * (q[0] - h[-2][0])
                               >= (q[1] - h[-2][1]) * (h[-1][0] - h[-2][0])):
            h.pop()
        h.append(q)
    w, x1, x2 = max((b[0] - a[0], a[0], b[0]) for a, b in zip(h, h[1:]))
    if w < 3.0 * (xs[1] - xs[0]):
        return None
    d = 1e-4
    dg = lambda x: (g(x + d) - g(x - d)) / (2 * d)
    for _ in range(30):
        chord = (g(x2) - g(x1)) / (x2 - x1)
        c1 = (dg(x1 + d) - dg(x1 - d)) / (2 * d)
        c2 = (dg(x2 + d) - dg(x2 - d)) / (2 * d)
        n1 = x1 - (dg(x1) - chord) / c1 if c1 > 0 else x1
        n2 = x2 - (dg(x2) - chord) / c2 if c2 > 0 else x2
        n1, n2 = min(max(n1, lo), hi), min(max(n2, lo), hi)
        if abs(n1 - x1) + abs(n2 - x2) < 1e-7:
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


def monotectic_T(db, p, lo=1800.0, hi=2150.0):
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
        return pdg.solid_gibbs_per_formula_unit("SiO2(cristobalite)", T)[0] - (g(x2) + (1.0 - x2) * chord)
    flo = f(lo)
    if flo is None:
        return None
    fhi = f(hi)
    while fhi is None:          # the gap closes below hi: bracket under the consolute
        hi -= 25.0
        if hi <= lo:
            return None
        fhi = f(hi)
    if flo * fhi <= 0:
        return brentq(f, lo, hi, xtol=0.05)
    Tx = lo - flo * (hi - lo) / (fhi - flo)
    if Tx < lo:
        return lo - 300.0 * math.asinh((lo - Tx) / 300.0)
    return hi + 300.0 * math.asinh((Tx - hi) / 300.0)


def consolute_T(db, p, lo, hi=4000.0):
    """Temperature where the silica-side gap closes, or None with no gap at lo; hi if it is
    still open there."""
    if binodal(db, p, lo) is None:
        return None
    if binodal(db, p, hi) is not None:
        return hi
    while hi - lo > 0.5:
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if binodal(db, p, mid) else (lo, mid)
    return lo


def residuals(pp, detail=False):
    db, p = build_db(pp)
    res, rows = [], []

    def add(tag, r, info=""):
        res.append(r)
        rows.append((tag, r, info))

    for d in ds.INVARIANTS:
        T_inv = []
        for s in d["solids"]:
            Tl = liquidus_T(db, p, s, d["x"])
            T_inv.append(Tl)
            add(f"{d['id'].split(':')[-1]} {s.split('(')[0]}", (Tl - d["T"]) / d["sigT"],
                f"{Tl:.1f}/{d['T']:.1f}")
        # a solid outside the invariant crystallizing first is a miss of the field
        worst = 0.0
        for other in X_SOLID:
            if other not in d["solids"]:
                To = liquidus_T(db, p, other, d["x"], extrapolate=False)
                if To is not None:
                    worst = max(worst, (To - max(T_inv)) / d["sigT"])
        add(f"  field at x={d['x']:.3f}", worst)

    m = ds.MONOTECTIC
    Tm = monotectic_T(db, p)
    add("monotectic T (silica + L1 + L2)", ((Tm - m["T"]) / m["sigT"]) if Tm
        else 5.0 + W_NOGAP * stability_margin(db, p, 1800.0, 0.55, 0.9995),
        f"{Tm:.1f}/{m['T']:.1f}" if Tm else "no gap")
    gap = binodal(db, p, m["T"])
    add("monotectic x_hi", ((gap[1] - m["x_hi"]) / m["sigx"]) if gap
        else 5.0 + W_NOGAP * stability_margin(db, p, m["T"], 0.55, 0.9995),
        f"{gap[1]:.4f}/{m['x_hi']:.4f}  x_lo {gap[0]:.3f}" if gap else "no gap")
    c = ds.CONSOLUTE
    lo_gap = binodal(db, p, c["T"] - c["sigT"])
    hi_gap = binodal(db, p, c["T"] + c["sigT"])
    add("consolute: gap below", 0.0 if lo_gap
        else 5.0 + W_NOGAP * stability_margin(db, p, c["T"] - c["sigT"], 0.55, 0.9995),
        f"{lo_gap[0]:.3f}-{lo_gap[1]:.3f}" if lo_gap else "none")
    # where the gap closes, softened beyond 300 K. The width 15 K above the measured top, the
    # residual used until 2026-10-07, stops changing once the gap is wide, and the fit left the
    # dome open past 3000 K.
    Tc = consolute_T(db, p, c["T"] - c["sigT"])
    add("consolute T", (300.0 / c["sigT"]) * math.asinh((Tc - c["T"]) / 300.0) if Tc else 0.0,
        f"{Tc:.0f}/{c['T']:.0f}" if Tc else "no gap")

    # no two liquids on the lime side (curvature terms can open one; fit_excess notes)
    for Tb in (2000.0, 2300.0, 2600.0):
        basic = binodal(db, p, Tb, lo=0.02, hi=0.5)
        add(f"no basic gap at {Tb:.0f} K", W_BASIC * ((basic[1] - basic[0]) / 0.02) if basic else 0.0,
            f"{basic[0]:.3f}-{basic[1]:.3f}" if basic else "none")

    for x, a_liq, T in fx.kaytaylor_points():
        _ac, a_s = act.activities(eq.build_inputs(db, p, T, components=COMP), x, T)
        add(f"KT a(SiO2) x={x:.3f}", (np.log(a_s) - np.log(a_liq)) / SIG_KT, f"{a_s:.3f}/{a_liq:.3f}")
    inp = eq.build_inputs(db, p, fx.T_STOL, components=COMP)
    cao, sio2 = bd.OXIDES["CaO"], bd.OXIDES["SiO2"]
    for x, (aC, aS) in sorted(fx.STOL.items()):
        if x in fx.STOL_DROP:
            continue
        cC, cS = act.activities(inp, x, fx.T_STOL)
        cC *= np.exp(cao["dHfus"] * (1 - fx.T_STOL / cao["Tm"]) / (R * fx.T_STOL))
        cS *= np.exp(sio2["dHfus"] * (1 - fx.T_STOL / sio2["Tm"]) / (R * fx.T_STOL))
        add(f"Stol a(CaO) x={x:.2f}", (np.log(cC) - np.log(aC)) / SIG_STOL, f"{cC:.3f}/{aC:.3f}")
        add(f"Stol a(SiO2) x={x:.2f}", (np.log(cS) - np.log(aS)) / SIG_STOL, f"{cS:.3f}/{aS:.3f}")

    T0 = 1900.0
    gT = lambda T: act.delta_g_mix(eq.build_inputs(db, p, T, components=COMP), 0.5)
    dH = gT(T0) - T0 * (gT(T0 + 50.0) - gT(T0 - 50.0)) / 100.0
    add("MLIP dH_mix x=0.5 (low weight)", (dH - MLIP_DH) / SIG_DH, f"{dH / 1000:.1f}/{MLIP_DH / 1000:.1f} kJ")
    i = 0
    for q, has_b in QTERMS:
        if has_b and q in QB:
            add(f"prior b0{q}", pp[i + 1] / SIG_QB, f"{pp[i + 1]:.2f} J/K")
        i += 2 if has_b else 1
    add("rankinite dHf prior", pp[I_RANK] / SIG_RANK, f"{pp[I_RANK] / 1000:+.2f} kJ")
    if CAO_BETA:
        add("prior CaO(l) beta", pp[I_BETA] / SIG_BETA, f"{pp[I_BETA]:.2f} J/K")
    if SRO:
        rows.append(("Ca-Si ordering x_SiO2", 0.0, f"{1.0 / 3.0 + pp[-1]:.4f}"))
    return (np.array(res), rows) if detail else np.array(res)


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
    scale = np.array([v for _, has_b in QTERMS for v in ([5e4, 10.0] if has_b else [5e4])]
                     + [3e3] + ([10.0] if CAO_BETA else []) + ([0.02] if SRO else []))
    sol = least_squares(lambda u: fun(u * scale), np.asarray(p0) / scale,
                        diff_step=0.02, ftol=1e-5, xtol=1e-6, max_nfev=150)
    return sol.x * scale


def report(pp, write=False):
    res, rows = residuals(pp, detail=True)
    for tag, r, info in rows:
        print(f"    {tag:38s} {info:30s} r={r:+6.2f}")
    print(f"\n  total cost = {0.5 * float(res @ res):.3f}   RMS residual = {np.sqrt(np.mean(res ** 2)):.2f}")
    if write:
        (HERE.parent / "CaO-SiO2-liquid.dat").write_text(bd.build(excess_of(pp), version="v0.4"),
                                                          encoding="ascii")
        print("  wrote CaO-SiO2-liquid.dat")


if __name__ == "__main__":
    # The assessed liquid is build_dat.ASSESSED_EXCESS and the rankinite shift is in
    # silicates.py (2026-09-29): total cost 133.3, RMS 2.61, nearly all of it the Stolyarova
    # a(CaO) points and the consolute. --fit re-runs from here.
    stored = {q: (a, b) for q, a, b in bd.ASSESSED_EXCESS}
    ASSESSED = [v for q, has_b in QTERMS
                for v in (stored.get(q, (0.0, 0.0)) if has_b else stored.get(q, (0.0, 0.0))[:1])]
    ASSESSED.append(sil.RANKINITE_DHF_SHIFT)
    if CAO_BETA:
        ASSESSED.append(bd.CAO_LIQ_BETA)
        NAMES.append("cao_liq_beta")
    if SRO:
        ASSESSED.append(bd.CASI_SRO_X - 1.0 / 3.0)
        NAMES.append("casi_sro_dx")
    for arg in sys.argv:
        if arg.startswith("--p0="):
            ASSESSED = [float(v) for v in arg[5:].split(",")]
    pp = fit(ASSESSED) if "--fit" in sys.argv else ASSESSED
    report(pp, write=("--write" in sys.argv))
    print("\n  params:", dict(zip(NAMES, [round(float(v), 4) for v in pp])))
