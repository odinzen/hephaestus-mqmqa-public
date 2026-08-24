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

STATUS - PRELIMINARY (v0.1). The topology is right (a continuous olivine loop, olivine always
more Mg-rich than the coexisting liquid) and the FAYALITE end is essentially exact: the pure
X_Fe=1 congruent point comes out 1476 K vs 1478 K measured. Two documented limits remain for
v0.2:
  - The FORSTERITE end is ~91 K high (computed 2254 K vs 2163 K measured). The MgO-SiO2 liquid
    was assessed against its own (co-optimized) forsterite solid, which differs from the
    olivine CEF forsterite endmember (Robie-Hemingway) by ~4.7 kJ/formula; on this join the
    liquid meets the R&H forsterite, so the Mg-rich liquidus rides high. Reconciling the two
    forsterite representations is the fix.
  - The liquidus is faceted at the ~20 J multi-start minimizer noise (the true liquid G is
    smooth); an exact ternary minimizer or a denser/averaged grid would clean it up.
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


def _liquid_G_factory(db, p, nstart=10):
    """Multi-start minimizer for the ternary liquid Gibbs per (Mg,Fe)2SiO4 formula at
    x_SiO2 = 1/3 and composition X_Fe. A single SLSQP start lands ~700 J high in the
    6-quadruplet ternary space; multi-start from Dirichlet points reaches ~20 J of the
    true minimum (verified against pycalphad)."""
    rng = np.random.default_rng(0)

    def liquid_G(xFe, T):
        inp = eqm.build_inputs(db, p, T, components=["FE", "MG", "SI", "O"])
        n = len(inp["quads"])
        target = {"FE": 2 * xFe / NATOMS, "MG": 2 * (1 - xFe) / NATOMS,
                  "SI": 1.0 / NATOMS, "O": 4.0 / NATOMS}
        order = sorted(target)

        def comp_res(X):
            els = eqm.element_moles(inp, X)
            tot = sum(els.values())
            return [els.get(e, 0.0) / tot - target[e] for e in order[:-1]]

        cons = [{"type": "eq", "fun": lambda X: sum(X) - 1.0},
                {"type": "eq", "fun": comp_res}]
        starts = [np.full(n, 1.0 / n)] + [rng.dirichlet(np.ones(n)) for _ in range(nstart - 1)]
        best = None
        for x0 in starts:
            r = minimize(lambda X: eqm.gibbs_per_quad(inp, X), x0, method="SLSQP",
                         bounds=[(1e-12, 1.0)] * n, constraints=cons,
                         options={"ftol": 1e-14, "maxiter": 3000})
            els = eqm.element_moles(inp, r.x)
            tot = sum(els.values())
            if max(abs(els.get(e, 0.0) / tot - target[e]) for e in order) < 1e-7:
                g = eqm.gibbs_per_quad(inp, r.x) / tot
                if best is None or g < best:
                    best = g
        return best * NATOMS if best is not None else np.nan

    return liquid_G


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


def _refine_tangent(xs, g_ol, g_liq, seed):
    """Refine a grid tie-line to the true common tangent between smooth fits of the two
    Gibbs curves (equal slope + shared tangent line). The olivine curve is exact so it is
    interpolated; the liquid curve carries ~20 J multi-start noise, so it is lightly
    smoothed (the true liquid G is smooth) before its derivative is taken. Returns
    (x_sol, x_liq)."""
    from scipy.interpolate import CubicSpline, UnivariateSpline
    from scipy.optimize import fsolve
    so = CubicSpline(xs, g_ol)
    sl = UnivariateSpline(xs, g_liq, k=3, s=len(xs) * 30.0 ** 2)

    def eqs(z):
        xs_, xl_ = z
        return [so(xs_, 1) - sl.derivative()(xl_),
                so(xs_) + so(xs_, 1) * (xl_ - xs_) - sl(xl_)]

    sol = fsolve(eqs, seed, full_output=True)
    z, _, ier, _ = sol
    lo, hi = xs[0], xs[-1]
    if ier == 1 and lo <= z[0] <= hi and lo <= z[1] <= hi and z[0] < z[1]:
        return float(z[0]), float(z[1])
    return seed


def compute_loop(T_lo=1480.0, T_hi=2260.0, dT=20.0, nx=41):
    cdb = mqmqa.Database.read(str(OLV))
    pol = cdb.phase_index("OLIVINE")
    ldb = mqmqa.Database.read(str(LIQ))
    lp = ldb.phase_index("FEO-MGO-SIO2-LIQUID")
    liquid_G = _liquid_G_factory(ldb, lp)
    xs = np.linspace(1e-3, 1 - 1e-3, nx)

    Ts = np.arange(T_lo, T_hi + 1e-6, dT)
    solidus, liquidus, Tkeep = [], [], []
    for T in Ts:
        g_ol = np.array([olivine_G(cdb, pol, float(x), T) for x in xs])
        g_liq = np.array([liquid_G(float(x), T) for x in xs])
        ok = np.isfinite(g_liq)
        tl = _tie_line(xs[ok], g_ol[ok], g_liq[ok])
        if tl is not None:
            xsol, xliq = _refine_tangent(xs[ok], g_ol[ok], g_liq[ok], tl)
            solidus.append(xsol)
            liquidus.append(xliq)
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
