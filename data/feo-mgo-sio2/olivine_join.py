"""The Mg2SiO4-Fe2SiO4 (forsterite-fayalite) olivine melting loop from the open database.

The headline multicomponent check: does the open FeO-MgO-SiO2 liquid, together with the
olivine (Mg,Fe)2SiO4 CEF solid solution, reproduce the measured olivine-join melting loop
(Bowen & Schairer 1935)? Along the join x_SiO2 = 1/3 the composition is one variable,
X_Fe = Fe/(Fe+Mg), so the liquid <-> olivine equilibrium is a common tangent between two
Gibbs curves per formula unit (Mg,Fe)2SiO4:

  - olivine G(X_Fe, T): the CEF solid solution, via the C kernel mqmqa_cef_gibbs
    (data/olivine, Robie-Hemingway endmembers + Wood-Kleppa excess).
  - liquid G(X_Fe, T): the ternary MQMQA liquid at x_SiO2 = 1/3, minimized over the six
    quadruplet fractions by the engine with a multi-start SLSQP (a single start gets stuck
    ~700 J above the minimum in the 3-cation space; multi-start reaches within ~20 J = ~0.4 K,
    matching pycalphad). The whole loop is thus computed with our own stack.

At each T the melting loop is the tie-line of the lower convex hull of the pooled curves
whose ends fall on different phases (liquidus = its liquid end, solidus = its olivine end).

STATUS (v0.2). BOTH congruent endpoints are reproduced: forsterite 2163 K (X_Fe=0) and
fayalite 1476 K (X_Fe=1), vs 2163 / 1478 measured. The forsterite end was reconciled by the
MgO(l) below-3098 K liquidus calibration (build_dat.MGO_LIQ_BETA, fit_mgo_beta below), which
puts the liquid on the same measured (Robie-Hemingway) forsterite the olivine CEF uses; the
fayalite end already followed from the FeO-SiO2 v0.3 FeO(l) calibration. The loop topology and
width match Bowen & Schairer's lens. Residual limit: the interior liquidus still carries small
facets from the few-J ternary liquid-minimizer noise (a warm-started, polynomial-smoothed
multi-start; an exact ternary minimizer / the C multiphase hull would remove them). The solid
side (olivine CEF) is exact.
Run: writes olivine_join_loop.png (regenerable, not committed).
"""
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))

import mqmqa
from mqmqa import equilibrium as eqm

LIQ = HERE / "FeO-MgO-SiO2-liquid.dat"
OLV = HERE.parents[0] / "olivine" / "Olivine-CEF.dat"
NATOMS = 7.0  # atoms per (Mg,Fe)2SiO4 formula unit


def olivine_G(cdb, pol, xFe, T):
    # reader alphabetizes the metal sublattice to [FE, MG]; per-formula Gibbs
    return cdb.cef_gibbs(pol, [xFe, 1.0 - xFe, 1.0, 1.0], T, per_mole_atoms=False)


def fit_mgo_beta(T_forsterite=2163.0):
    """The MGO_LIQ_BETA in build_dat: the MgO(l) below-3098 K correction that makes the
    MgO-SiO2 liquid melt the measured (Robie-Hemingway) forsterite - the olivine CEF
    endmember - congruently at 2163 K. Orthogonal to the activities (pure MgO endmember
    shift), so this is a single-point analytic solve, not an optimization. Returns beta;
    the value is cached in build_dat.MGO_LIQ_BETA."""
    import importlib.util

    def _load(name, rel):
        spec = importlib.util.spec_from_file_location(name, HERE.parents[1] / rel)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    from mqmqa import equilibrium as eqm
    mgo_bd = _load("mgo_bd_fit", "data/mgo-sio2/build_dat.py")
    actM = _load("mgo_act_fit", "data/mgo-sio2/_activity.py")
    olv = _load("olv_em_fit", "data/olivine/endmembers.py")
    db = mqmqa.Database.read(str(HERE.parents[0] / "mgo-sio2" / "MgO-SiO2-liquid.dat"))
    p = db.phase_index("MGO-SIO2-LIQUID")
    inp = eqm.build_inputs(db, p, T_forsterite)
    liq = actM.gm(inp, 1.0 / 3.0) * NATOMS  # MgO-SiO2 liquid per Mg2SiO4 formula
    fo = olv.gibbs("forsterite", T_forsterite)
    return (fo - liq) / (2.0 * (T_forsterite - mgo_bd.MGO_TM))


def _liquid_curve(db, p, T, xs, nstart=6):
    """Ternary liquid Gibbs per (Mg,Fe)2SiO4 formula along X_Fe at x_SiO2 = 1/3, minimized
    over the six quadruplet fractions. A single SLSQP start lands ~700 J high in the
    ternary space, so each composition is WARM-STARTED from the previous one's optimum
    (the quad distribution varies smoothly with X_Fe) plus a few Dirichlet starts for
    robustness; the best feasible G is kept. Reaches ~a few J of pycalphad. Returns g(xs)."""
    inp = eqm.build_inputs(db, p, T, components=["FE", "MG", "SI", "O"])
    n = len(inp["quads"])
    rng = np.random.default_rng(0)
    g = np.full(len(xs), np.nan)
    warm = np.full(n, 1.0 / n)
    for i, xFe in enumerate(xs):
        target = {"FE": 2 * xFe / NATOMS, "MG": 2 * (1 - xFe) / NATOMS,
                  "SI": 1.0 / NATOMS, "O": 4.0 / NATOMS}
        order = sorted(target)

        def comp_res(X):
            els = eqm.element_moles(inp, X)
            tot = sum(els.values())
            return [els.get(e, 0.0) / tot - target[e] for e in order[:-1]]

        cons = [{"type": "eq", "fun": lambda X: sum(X) - 1.0},
                {"type": "eq", "fun": comp_res}]
        starts = [warm, np.full(n, 1.0 / n)] + [rng.dirichlet(np.ones(n)) for _ in range(nstart)]
        best, bestX = None, None
        for x0 in starts:
            r = minimize(lambda X: eqm.gibbs_per_quad(inp, X), x0, method="SLSQP",
                         bounds=[(1e-12, 1.0)] * n, constraints=cons,
                         options={"ftol": 1e-14, "maxiter": 3000})
            els = eqm.element_moles(inp, r.x)
            tot = sum(els.values())
            if max(abs(els.get(e, 0.0) / tot - target[e]) for e in order) < 1e-7:
                gv = eqm.gibbs_per_quad(inp, r.x) / tot
                if best is None or gv < best:
                    best, bestX = gv, r.x
        if best is not None:
            g[i] = best * NATOMS
            warm = bestX
    return g


def _tie_line(xs, g_ol, g_liq):
    """Lower convex hull of the two pooled curves; return (x_solidus, x_liquidus) of the
    hull edge that jumps olivine->liquid, or None if the whole join is single-phase at T."""
    pts = ([(x, g, "ol") for x, g in zip(xs, g_ol)]
           + [(x, g, "liq") for x, g in zip(xs, g_liq)])
    pts.sort(key=lambda p: (p[0], p[1]))
    # keep the lower point at each x, then monotone-chain lower hull
    hull = []
    for x, g, tag in pts:
        while len(hull) >= 2:
            (x1, g1, _), (x2, g2, _) = hull[-2], hull[-1]
            if (x2 - x1) * (g - g1) - (g2 - g1) * (x - x1) <= 1e-9:
                hull.pop()
            else:
                break
        hull.append((x, g, tag))
    # a real two-phase tie-line = a hull edge whose ends are different phases and that
    # skips grid compositions between them (not two adjacent samples of one curve)
    best = None
    for (x1, g1, t1), (x2, g2, t2) in zip(hull, hull[1:]):
        if t1 != t2 and (x2 - x1) > 1.5 * (xs[1] - xs[0]):
            xol = x1 if t1 == "ol" else x2
            xliq = x1 if t1 == "liq" else x2
            best = (xol, xliq)
    return best


def _fine_tie_line(xs, g_ol, g_liq, nfine=600):
    """Smooth both curves and read the olivine<->liquid tie-line off the lower convex hull
    of a fine resampling. The olivine curve is exact (cubic interpolation); the liquid
    curve carries ~20 J multi-start noise, so it is fitted with a light smoothing spline
    (its true shape is smooth). The fine grid removes coarse-grid snapping; smoothing
    removes the minimizer jitter that otherwise facets the liquidus."""
    from scipy.interpolate import CubicSpline
    so = CubicSpline(xs, g_ol)
    # the liquid G is physically smooth (ideal mixing + a low-order excess); fit its
    # departure from the endmember chord with a degree-5 polynomial to strip the few-J
    # minimizer jitter without the shape distortion an over-stiff spline introduces.
    chord = g_liq[0] + (g_liq[-1] - g_liq[0]) * (xs - xs[0]) / (xs[-1] - xs[0])
    coef = np.polyfit(xs, g_liq - chord, 5)
    xf = np.linspace(xs[0], xs[-1], nfine)
    chord_f = g_liq[0] + (g_liq[-1] - g_liq[0]) * (xf - xs[0]) / (xs[-1] - xs[0])
    g_liq_f = np.polyval(coef, xf) + chord_f
    tl = _tie_line(xf, so(xf), g_liq_f)
    # reject an implausibly wide edge (an over-smoothing artifact spanning the whole join)
    if tl is not None and (tl[1] - tl[0]) > 0.85:
        return None
    return tl


def compute_loop(T_lo=1480.0, T_hi=2260.0, dT=20.0, nx=41):
    cdb = mqmqa.Database.read(str(OLV))
    pol = cdb.phase_index("OLIVINE")
    ldb = mqmqa.Database.read(str(LIQ))
    lp = ldb.phase_index("FEO-MGO-SIO2-LIQUID")
    xs = np.linspace(1e-3, 1 - 1e-3, nx)

    Ts = np.arange(T_lo, T_hi + 1e-6, dT)
    solidus, liquidus, Tkeep = [], [], []
    for T in Ts:
        g_ol = np.array([olivine_G(cdb, pol, float(x), T) for x in xs])
        g_liq = _liquid_curve(ldb, lp, T, xs)
        ok = np.isfinite(g_liq)
        tl = _fine_tie_line(xs[ok], g_ol[ok], g_liq[ok])
        if tl is not None:
            solidus.append(tl[0])
            liquidus.append(tl[1])
            Tkeep.append(T)
    return np.array(Tkeep), np.array(solidus), np.array(liquidus)


def main():
    T, sol, liq = compute_loop()
    print(" T(K)   solidus(X_Fe)  liquidus(X_Fe)   [olivine]      [liquid]")
    for t, s, l in zip(T, sol, liq):
        print(f" {t:6.0f}    {s:8.3f}       {l:8.3f}")
    print(f"\nloop spans {T.min():.0f}-{T.max():.0f} K "
          f"(fayalite end ~1478, forsterite end ~2163 measured)")
    np.savez(HERE / "_olivine_join_loop.npz", T=T, solidus=sol, liquidus=liq)

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(5.2, 4.2))
        ax.plot(liq, T, "-", color="0.15", lw=1.6, label="Liquidus (liquid)")
        ax.plot(sol, T, "--", color="0.15", lw=1.6, label="Solidus (olivine)")
        ax.scatter([1.0, 0.0], [1478, 2163], s=34, facecolor="white",
                   edgecolor="0.15", zorder=5, label="Measured congruent (B&S 1935)")
        ax.set_xlabel(r"$X_{\mathrm{Fe}} = \mathrm{Fe}/(\mathrm{Fe+Mg})$")
        ax.set_ylabel("Temperature (K)")
        ax.set_title("Forsterite-Fayalite Olivine Melting Loop")
        ax.set_xlim(0, 1)
        ax.legend(frameon=False, fontsize=8, loc="lower left")
        fig.tight_layout()
        out = HERE / "olivine_join_loop.png"
        fig.savefig(out, dpi=150)
        print(f"wrote {out}")
    except Exception as e:
        print("plot skipped:", e)


if __name__ == "__main__":
    main()
