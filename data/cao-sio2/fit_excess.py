"""Fit the CaO-SiO2 liquid MQMQA excess (v0.2) to open experimental activities.

The engine itself is the optimizer's forward model: for a trial set of excess
coefficients L we compute a(CaO), a(SiO2) from the C engine (see _activity.py) and
least-squares match them, in ln(a) space, to two open datasets:

  Stolyarova et al. 1991, J. Electrochem. Soc. 138(12) 3710, KEMS at 1933 K
    (Tables IIa/IIb, direct-measurement columns Eq [2]/[3]); reference = pure oxide
    (a -> 1 at the pure component), taken as the pure liquid to match the engine.
    The two CaO-richest points (x_SiO2 = 0.25, 0.33) are DROPPED: there a(CaO)
    reaches 0.96-1.00, the signature of CaO/silicate saturation (a two-phase melt),
    which the single-liquid model cannot and should not reproduce.

  Kay & Taylor 1960, Trans. Faraday Soc. 56, 1372, CO/SiC gas-slag equilibrium at
    ~1821 K (Table 3); a(SiO2) referenced to pure SOLID SiO2. Converted to the pure
    LIQUID reference by a(liq) = a(solid) / exp(dG_fus,SiO2 / RT), a 5-6% shift
    (dG_fus,SiO2 is small this close to Tm). Compositions are oxide mass percent with
    0.6% Al2O3; the tiny alumina is dropped and CaO+SiO2 renormalized to mole
    fraction. This anchors the silica-rich half of the join that Stolyarova's data
    does not reach.

Nothing here uses a fitted/optimized TDB parameter: the endmembers are the open
v0.1 build and the excess coefficients are our own least-squares result.
"""

import sys
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "python"))

import build_dat as bd
import mqmqa
from mqmqa import equilibrium as eq
import _activity as act

R = 8.3145
T_STOL = 1933.0
T_KT = 1821.65  # mean of the Kay-Taylor run temperatures (1820.15-1822.15 K)

# --- Stolyarova 1991, Table IIa: a(CaO) at 1933 K, Eq [2] (direct measurement) ---
# --- Stolyarova 1991, Table IIb: a(SiO2) at 1933 K, Eq [3] (direct measurement) ---
# x_SiO2 : (a_CaO, a_SiO2).  Reference = pure oxide (liquid).
STOL = {
    0.50: (0.07, 0.20),
    0.49: (0.11, 0.09),
    0.44: (0.26, 0.10),
    0.41: (0.29, 0.05),
    0.40: (0.52, 0.03),
    0.39: (0.52, 0.04),
    0.38: (0.63, 0.023),
    0.33: (0.96, 0.003),
    0.25: (1.00, 0.004),
}
# Stolyarova state the liquidus at x_SiO2 = 0.41 at 1933 K (p.3711: "the liquidus
# point ... 0.41 mole fraction of SiO2"; congruent vaporization for x_SiO2 = 0.01-
# 0.37). Points below x_SiO2 = 0.41 are therefore sub-liquidus: the melt is
# saturated with solid Ca-silicate (2CaO.SiO2 / 3CaO.SiO2), and the measured
# activities are two-phase (a_CaO -> 1 at the CaO-rich end), NOT homogeneous-liquid
# mixing. The single-liquid model is fit only to the genuinely single-phase points.
STOL_DROP = {0.25, 0.33, 0.38, 0.39, 0.40}

# --- Kay & Taylor 1960, Table 3: a(SiO2) vs pure SOLID SiO2, near-binary slag ---
# (CaO, SiO2) mass percent (Al2O3 = 0.6% dropped), a(SiO2) solid ref, run T.
KAYTAYLOR = [
    # wt%CaO, wt%SiO2, a_SiO2_solidref, T_K, run
    (38.1, 61.3, 0.762, 1821.15, "34"),
    (38.1, 61.3, 0.766, 1821.15, "34R"),
    (42.5, 56.9, 0.569, 1820.15, "35"),
    (46.9, 52.5, 0.267, 1821.15, "36"),
    (51.4, 48.0, 0.180, 1822.15, "37"),
    (55.8, 43.6, 0.096, 1822.15, "38"),
]
MW_CAO, MW_SIO2 = 56.077, 60.083
DHFUS_SIO2, TM_SIO2 = bd.OXIDES["SiO2"]["dHfus"], bd.OXIDES["SiO2"]["Tm"]


# The CaO-SiO2 liquid has a silica-rich miscibility gap (x_SiO2 > ~0.65 at these
# T), i.e. POSITIVE deviations that a cation-mixing Q excess centered on ordering
# cannot reproduce. v0.2 targets the ordered central melt; Kay-Taylor points that
# approach the gap (x_SiO2 > KT_XMAX) are excluded from the fit and flagged.
KT_XMAX = 0.52


def kaytaylor_points(all_pts=False):
    """Return [(x_SiO2, a_SiO2_liquidref, T), ...] for Kay-Taylor (central region)."""
    pts = []
    for cao, sio2, a_sol, T, _run in KAYTAYLOR:
        n_cao, n_sio2 = cao / MW_CAO, sio2 / MW_SIO2
        x = n_sio2 / (n_cao + n_sio2)
        dg_fus = DHFUS_SIO2 * (1.0 - T / TM_SIO2)
        a_liq = a_sol / np.exp(dg_fus / (R * T))
        if all_pts or x <= KT_XMAX:
            pts.append((x, a_liq, T))
    return pts


# excess model: cation-mixing Q terms on the (Ca,Si,O,O) quadruplet. The mixing
# factor of a (p,q) term is chi_Ca^p chi_Si^q / (chi_Ca+chi_Si)^(p+q); since
# chi_Ca + chi_Si = 1, the set {(0,0),(1,0),(0,1)} spans only {1, chi_Ca} (rank 2).
# An independent basis is a polynomial in chi_Ca: {(0,0),(1,0),(2,0),(3,0)}. Two
# terms (constant + chi_Ca) are what the single-phase data support: adding curvature
# only fits the scatter in a(SiO2) and forces a spurious CaO-rich miscibility gap.
EXPONENTS = [(0, 0), (1, 0), (2, 0), (3, 0)]
N_PARAMS = 2


def make_scaffold(n_params):
    excess = [dict(code="Q", li=[1, 2, 3, 3], exp=[p, q, 0, 0],
                   coeffs=[0.0] * 6) for (p, q) in EXPONENTS[:n_params]]
    path = HERE / "_scaffold.dat"
    path.write_text(bd.build(excess), encoding="ascii")
    return path


def build_inps(n_params):
    path = make_scaffold(n_params)
    db = mqmqa.Database.read(str(path))
    p = db.phase_index("CAO-SIO2-LIQUID")
    inp_s = eq.build_inputs(db, p, T_STOL, components=["CA", "SI", "O"])
    inp_k = eq.build_inputs(db, p, T_KT, components=["CA", "SI", "O"])
    return inp_s, inp_k


# weights: a(CaO) is the clean, dominant KEMS species; Stolyarova a(SiO2) (minor
# SiO+ ion) is scattered; Kay-Taylor a(SiO2) is a solid gas-slag measurement.
W_CAO, W_SIO2_STOL, W_KT = 1.0, 0.5, 1.0


# Ridge on the excess coefficients (scaled by 1e5 J). The chi_Ca powers are
# collinear over the narrow fitted window, so an unregularized cubic oscillates and
# extrapolates to unphysical values (Delta g > +100 kJ) toward the CaO-rich edge
# that has no data. A mild ridge keeps the coefficients small and Delta g bounded
# without degrading the a(CaO) fit that carries the real curvature signal.
RIDGE = 0.0


def residuals(L, inp_s, inp_k, kt_pts, report=False):
    act.set_excess_L(inp_s, L)
    act.set_excess_L(inp_k, L)
    res, rows = [], []
    for x, (aC, aS) in sorted(STOL.items()):
        if x in STOL_DROP:
            continue
        cC, cS = act.activities(inp_s, x, T_STOL)
        res.append(W_CAO * (np.log(cC) - np.log(aC)))
        res.append(W_SIO2_STOL * (np.log(cS) - np.log(aS)))
        rows.append(("Stol aCaO", x, aC, cC))
        rows.append(("Stol aSiO2", x, aS, cS))
    for x, a_liq, T in kt_pts:
        cC, cS = act.activities(inp_k, x, T)
        res.append(W_KT * (np.log(cS) - np.log(a_liq)))
        rows.append(("KT aSiO2", x, a_liq, cS))
    if report:
        return np.array(res), rows
    # ridge only on the higher-order terms (index >= 1), not the constant g00
    res.extend(RIDGE * (Lk / 1e5) for Lk in L[1:])
    # stability penalty: forbid a spurious miscibility gap (d2 Gmix/dx2 < 0) in the
    # CaO-rich single-phase region 0.05-0.35, where the real system has NO gap (the
    # only real gap is silica-rich). Strong asymmetric ordering can otherwise drive
    # the fit to over-curve and destabilize the CaO-rich liquid.
    res.extend(STAB * min(0.0, _d2_gmix(inp_s, x) / 1e5) for x in STAB_X)
    return np.array(res)


STAB = 2.0  # non-binding on the 2-term fit (which is stable on its own); a guard
STAB_X = np.linspace(0.05, 0.35, 7)


def _d2_gmix(inp, x, dx=0.01):
    """Second derivative of the molar (per oxide formula) Gibbs energy of mixing."""
    return (act.delta_g_mix(inp, x + dx) - 2 * act.delta_g_mix(inp, x)
            + act.delta_g_mix(inp, x - dx)) / (dx * dx)


def fit(n_params=N_PARAMS):
    inp_s, inp_k = build_inps(n_params)
    kt_pts = kaytaylor_points()
    x0 = ([-40000.0] + [0.0] * (n_params - 1))
    sol = least_squares(residuals, x0, args=(inp_s, inp_k, kt_pts),
                        method="trf", x_scale=[1e4] * n_params,
                        diff_step=1e-2, xtol=1e-10, ftol=1e-10)
    return sol, inp_s, inp_k, kt_pts


def excess_params(L):
    """The fitted MQMX excess parameters as build_dat.build() dicts."""
    return [dict(code="Q", li=[1, 2, 3, 3], exp=[p, q, 0, 0],
                 coeffs=[float(Lk), 0.0, 0.0, 0.0, 0.0, 0.0])
            for (p, q), Lk in zip(EXPONENTS[:len(L)], L)]


def write_v02(L, path=None):
    path = Path(path) if path else (HERE / "CaO-SiO2-liquid.dat")
    path.write_text(bd.build(excess_params(L)), encoding="ascii")
    return path


def main(write=True):
    n_params = int(sys.argv[1]) if len(sys.argv) > 1 else N_PARAMS
    sol, inp_s, inp_k, kt_pts = fit(n_params)
    L = sol.x
    res, rows = residuals(L, inp_s, inp_k, kt_pts, report=True)
    labels = [f"g{p}{q}" for (p, q) in EXPONENTS[:n_params]]

    print("=" * 74)
    print(f"CaO-SiO2 liquid v0.2 excess fit: {n_params} Q-code cation-mixing "
          "term(s) on (Ca,Si,O,O)")
    print("=" * 74)
    print("  Delta_g(Ca,Si)/O = " + " + ".join(
        f"{v:.1f}*chi_Ca^{p}" if (p or q) else f"{v:.1f}"
        for (p, q), v in zip(EXPONENTS, L)) + "  J/mol")
    for lab, (p, q), val in zip(labels, EXPONENTS, L):
        print(f"    {lab}  (p={p},q={q})  L = {val:12.1f} J/mol")
    print(f"  cost = {sol.cost:.5f}   RMS(ln a, data only) = "
          f"{np.sqrt(np.mean(np.array([r for r in res])**2)):.4f}")

    print("\n  per-point fit (measured vs engine, all liquid-referenced):")
    print(f"  {'dataset':12s} {'x_SiO2':>7s} {'measured':>10s} {'engine':>10s} "
          f"{'ln ratio':>9s}")
    for (lab, x, meas, calc) in rows:
        print(f"  {lab:12s} {x:7.3f} {meas:10.4f} {calc:10.4f} "
              f"{np.log(calc / meas):9.3f}")

    # integral Gibbs energy of mixing at 1933 K, single-phase points
    print("\n  Delta_G_mix at 1933 K (J/mol oxide formula):")
    act.set_excess_L(inp_s, L)
    RT = R * T_STOL
    for x, (aC, aS) in sorted(STOL.items()):
        if x in STOL_DROP:
            continue
        dg_m = (1 - x) * RT * np.log(aC) + x * RT * np.log(aS)
        dg_c = act.delta_g_mix(inp_s, x)
        print(f"    x_SiO2={x:.2f}  measured={dg_m:8.0f}  engine={dg_c:8.0f}  "
              f"diff={dg_c - dg_m:7.0f}")

    if write:
        path = write_v02(L)
        print(f"\n  wrote {path}")
    return sol, L


if __name__ == "__main__":
    main()
