"""Component activities of the FeO-SiO2 liquid from the MQMQA engine.

a(i) = exp((mu_i - G_i_pure_liquid) / (R T)) with mu_i the partial molar Gibbs of
oxide component i, obtained by central finite difference of the total Gibbs energy
G_tot(n_MgO, n_SiO2) = GM(x_SiO2) * n_atoms with respect to n_i at fixed n_j. The
reference is the pure LIQUID oxide endmember (a -> 1 as x_i -> 1), matching the
engine's liquid-only model. R = 8.3145 (the engine's CALPHAD gas constant).

The general SLSQP equilibrium solver in equilibrium.py carries enough numerical
noise (~1 J/mol) to wreck a finite-difference chemical potential (step ~1e-4 mole
amplifies it by 1e4). For the FeO-SiO2 binary the quadruplet distribution has a
single internal degree of freedom (the mixed (Ca,Si,O,O) fraction), so we solve it
exactly: the two cation species moles are linear in the three quadruplet fractions,
mass balance + normalization pin two of them to the third, and GM is minimized in
1-D with Brent to ~1e-12. That gives a smooth GM(x) and clean potentials.

The excess coefficients L (one scalar per MQMX parameter, already evaluated at T)
are written straight into the prebuilt `inp` so the optimizer never re-reads the
.dat; only the numbers L change between iterations, never the model structure.
"""

import numpy as np
from scipy.optimize import minimize_scalar

from mqmqa import equilibrium as eq

R = 8.3145
ATOMS = {"FeO": 2.0, "SiO2": 3.0}  # atoms per oxide formula unit


def binary_coeffs(inp):
    """Precompute the linear map from quadruplet fractions to cation moles.

    Quad order is Q0=(Ca,Ca,O,O), Q1=(Ca,Si,O,O), Q2=(Si,Si,O,O). Returns the
    constants (cCa0, aCa, cSi2, aSi) with n_Ca = cCa0*X0 + aCa*X1 and
    n_Si = cSi2*X2 + aSi*X1.
    """
    Za, Zb = inp["Za"], inp["Zb"]
    cCa0 = 1.0 / Za[0] + 1.0 / Zb[0]
    aCa = 1.0 / Za[1]
    cSi2 = 1.0 / Za[2] + 1.0 / Zb[2]
    aSi = 1.0 / Zb[1]
    return cCa0, aCa, cSi2, aSi


def _quad_fractions(inp, x_sio2, X1):
    """Given the mixed-quad fraction X1 and target x_SiO2, the other two fractions."""
    cCa0, aCa, cSi2, aSi = binary_coeffs(inp)
    x = x_sio2
    num = x * cCa0 * (1.0 - X1) + X1 * (x * aCa - (1.0 - x) * aSi)
    den = (1.0 - x) * cSi2 + x * cCa0
    X2 = num / den
    X0 = 1.0 - X1 - X2
    return np.array([X0, X1, X2])


def _X1_bounds(inp, x_sio2):
    """Range of X1 for which X0, X2 stay non-negative."""
    lo, hi = 0.0, 1.0
    for _ in range(80):  # bisection on the feasibility of both endmember quads
        mid = 0.5 * (lo + hi)
        X = _quad_fractions(inp, x_sio2, mid)
        if X[0] >= 0 and X[2] >= 0:
            lo = mid
        else:
            hi = mid
    # lo is the largest feasible X1; feasible region is [0, lo]
    return 0.0, max(lo - 1e-9, 1e-12)


def gm(inp, x_sio2):
    """Molar Gibbs per mole of ATOMS at oxide fraction x_sio2 (exact 1-D minimum)."""
    x_sio2 = min(max(x_sio2, 1e-9), 1.0 - 1e-9)
    x1_lo, x1_hi = _X1_bounds(inp, x_sio2)

    def obj(X1):
        X = _quad_fractions(inp, x_sio2, X1)
        X = np.clip(X, 1e-300, None)
        g_quad = eq.gibbs_per_quad(inp, X)
        els = eq.element_moles(inp, X)
        return g_quad / sum(els.values())

    res = minimize_scalar(obj, bounds=(x1_lo, x1_hi), method="bounded",
                          options={"xatol": 1e-12})
    return res.fun


def _g_total(inp, n_feo, n_sio2):
    n_atoms = ATOMS["FeO"] * n_feo + ATOMS["SiO2"] * n_sio2
    return gm(inp, n_sio2 / (n_feo + n_sio2)) * n_atoms


def set_excess_L(inp, L):
    inp["ex"]["L"] = list(L)


def g_pure_liquid(inp, which):
    if which == "SiO2":
        return gm(inp, 1.0 - 1e-9) * ATOMS["SiO2"]
    return gm(inp, 1e-9) * ATOMS["FeO"]


def activities(inp, x_sio2, T, h=2e-4):
    """(a_MgO, a_SiO2) at oxide fraction x_sio2 and temperature T, liquid ref."""
    n_feo, n_sio2 = 1.0 - x_sio2, x_sio2
    mu_sio2 = (_g_total(inp, n_feo, n_sio2 + h)
               - _g_total(inp, n_feo, n_sio2 - h)) / (2.0 * h)
    mu_feo = (_g_total(inp, n_feo + h, n_sio2)
              - _g_total(inp, n_feo - h, n_sio2)) / (2.0 * h)
    a_feo = np.exp((mu_feo - g_pure_liquid(inp, "FeO")) / (R * T))
    a_sio2 = np.exp((mu_sio2 - g_pure_liquid(inp, "SiO2")) / (R * T))
    return float(a_feo), float(a_sio2)


def delta_g_mix(inp, x_sio2):
    """Integral Gibbs energy of mixing per mole of oxide formula (liquid ref).

    G_mix = G(x) - (1-x) G_MgO_pure - x G_SiO2_pure, all per oxide formula unit.
    """
    n_atoms = ATOMS["FeO"] * (1 - x_sio2) + ATOMS["SiO2"] * x_sio2
    g = gm(inp, x_sio2) * n_atoms  # per (1-x) MgO + x SiO2, i.e. per oxide formula
    g_cao = g_pure_liquid(inp, "FeO")
    g_sio2 = g_pure_liquid(inp, "SiO2")
    return g - (1 - x_sio2) * g_cao - x_sio2 * g_sio2
