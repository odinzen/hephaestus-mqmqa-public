"""Fit the CaO-Al2O3 liquid excess to the Rankin & Wright (1915) invariants and report the
resulting diagram. Targets (temperatures K; liquid compositions converted from R&W wt% CaO to
x_AlO1.5 = n_Al / (n_Ca + n_Al)):

  eutectic  C3A + C12A7   1668.15 K   liq 50.0 wt% CaO  -> x 0.5238
  congruent C12A7         1728.15 K   (compound x 14/26)
  eutectic  C12A7 + CA    1673.15 K   liq 47.0          -> x 0.5537
  congruent CA            1873.15 K   (compound x 2/3)
  eutectic  CA + CA2      1863.15 K   liq 33.5          -> x 0.6859
  eutectic  CA2 + cor     1973.15 K   liq 24.0          -> x 0.7789

Reported, not fitted: C3A peritectic (R&W 1808.15 K, decomposes to CaO + liquid) and the
CA2-side congruent point (R&W give 1993.15 K for their "3C5A" at x 0.769; modern CA2 sits at
x 0.8, the documented compound-identity revision).

Run with --fit to re-optimize; default evaluates the stored parameters and writes the .dat.
"""
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "python"))

import build_dat
import mqmqa
from mqmqa import dbbuild
from mqmqa import equilibrium as eq
from mqmqa.dbbuild import ExcessTerm, solid_gibbs_coeffs

M_CAO, M_AL2O3 = 56.077, 101.961


def wt_to_x(wt_cao):
    n_ca = wt_cao / M_CAO
    n_al = 2.0 * (100.0 - wt_cao) / M_AL2O3
    return n_al / (n_ca + n_al)


EUTECTICS = [  # (solid_lo, solid_hi, T_meas, x_meas)
    ("Ca3Al2O6", "Ca12Al14O33", 1668.15, wt_to_x(50.0)),
    ("Ca12Al14O33", "CaAl2O4", 1673.15, wt_to_x(47.0)),
    ("CaAl2O4", "CaAl4O7", 1863.15, wt_to_x(33.5)),
    ("CaAl4O7", "Al2O3_corundum", 1973.15, wt_to_x(24.0)),
]
CONGRUENTS = [("Ca12Al14O33", 1728.15), ("CaAl2O4", 1873.15)]

ATOMS = {"CaO": 2.0, "AlO1.5": 2.5}


class Model:
    """Liquid + solid Gibbs on the CaO/AlO1.5 cation-unit basis, from a written .dat."""

    def __init__(self, dat_path):
        self.db = mqmqa.Database.read(str(dat_path))
        self.p = self.db.phase_index("CAO-ALO1.5-LIQUID")
        self._cache = {}

    def g_liq(self, x, T):
        """Absolute liquid Gibbs per mole of cation units at AlO1.5 fraction x."""
        if T not in self._cache:
            inp = eq.build_inputs(self.db, self.p, T, components=["CA", "AL", "O"])
            gm, _ = dbbuild._binary_activity_solver(inp, ATOMS["CaO"], ATOMS["AlO1.5"])
            self._cache[T] = gm
        gm = self._cache[T]
        atoms = (1.0 - x) * ATOMS["CaO"] + x * ATOMS["AlO1.5"]
        return gm(x) * atoms

    @staticmethod
    def g_solid(name, T):
        """Solid Gibbs per mole of cation units, and its x position."""
        n_ca, n_al, cf = build_dat.SOLIDS[name]
        A, B, C, D, E, F = solid_gibbs_coeffs(cf["dHf"], cf["S298"], cf["a"], cf["b"], cf["c"])
        g = A + B * T + C * T * math.log(T) + D * T * T + E * T ** 3 + F / T
        units = n_ca + n_al
        return g / units, n_al / units


def eutectic_T(model, lo_name, hi_name, T_lo=1300.0, T_hi=2400.0):
    """T and x where the liquid last touches the chord between two adjacent solids."""
    def depth(T):
        g1, x1 = model.g_solid(lo_name, T)
        g2, x2 = model.g_solid(hi_name, T)
        xs = np.linspace(x1 + 1e-3, x2 - 1e-3, 30)
        chord = g1 + (g2 - g1) * (xs - x1) / (x2 - x1)
        vals = np.array([model.g_liq(float(x), T) for x in xs]) - chord
        return float(vals.min()), float(xs[vals.argmin()])

    lo, hi = T_lo, T_hi
    if depth(lo)[0] < 0 or depth(hi)[0] > 0:
        return None, None
    for _ in range(20):
        mid = 0.5 * (lo + hi)
        lo, hi = (lo, mid) if depth(mid)[0] < 0 else (mid, hi)
    T = 0.5 * (lo + hi)
    return T, depth(T)[1]


def congruent_T(model, name, T_lo=1300.0, T_hi=2600.0):
    _, x = model.g_solid(name, 1500.0)

    def f(T):
        gs, _ = model.g_solid(name, T)
        return model.g_liq(x, T) - gs

    lo, hi = T_lo, T_hi
    if f(lo) * f(hi) > 0:
        return None
    for _ in range(28):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if f(lo) * f(mid) > 0 else (lo, mid)
    return 0.5 * (lo + hi)


def peritectic_check(model, T):
    """Is C3A below the CaO(s)-liquid construction at T (i.e. decomposed), per the hull?"""
    g_c3a, x_c3a = model.g_solid("Ca3Al2O6", T)
    g_cao, _ = model.g_solid("CaO_solid", T)
    xs = np.linspace(0.30, 0.60, 61)
    best = min((model.g_liq(float(x), T) - g_cao) / x for x in xs)  # steepest tangent from CaO
    return g_c3a - (g_cao + best * x_c3a)   # >0 means C3A unstable (decomposed)


def evaluate(terms, label):
    dat = build_dat.build(terms)
    m = Model(dat)
    print(f"--- {label} ---")
    rows = []
    for lo_name, hi_name, T_meas, x_meas in EUTECTICS:
        T, x = eutectic_T(m, lo_name, hi_name)
        rows.append((f"eut {lo_name[:9]}/{hi_name[:9]}", T, T_meas, x, x_meas))
    for name, T_meas in CONGRUENTS:
        T = congruent_T(m, name)
        rows.append((f"congr {name}", T, T_meas, None, None))
    for tag, T, T_meas, x, x_meas in rows:
        dT = "  --" if T is None else f"{T - T_meas:+6.0f}"
        xs = "" if x is None else f"   x {x:.3f} (meas {x_meas:.3f})"
        print(f"  {tag:28s} T {'none' if T is None else f'{T:7.1f}'}  meas {T_meas:7.1f}  dT {dT}{xs}")
    return m, rows


def residual(vec):
    terms = [ExcessTerm(a=vec[0], b=vec[1], p=0, q=0), ExcessTerm(a=vec[2], b=0.0, p=1, q=0)]
    dat = build_dat.build(terms)
    m = Model(dat)
    res = []
    for lo_name, hi_name, T_meas, x_meas in EUTECTICS:
        T, x = eutectic_T(m, lo_name, hi_name)
        res.append(((T if T is not None else 500.0) - T_meas) / 25.0)
        res.append(((x - x_meas) / 0.02) if x is not None else 10.0)
    for name, T_meas in CONGRUENTS:
        T = congruent_T(m, name)
        res.append(((T if T is not None else 500.0) - T_meas) / 25.0)
    print("  vec", np.round(vec, 1), "resid", np.round(res, 2))
    return np.asarray(res, float)


# Fitted 2026-08-25 (least_squares over the 6 R&W targets; the 4-term variant only improved
# cost 21.1 -> 20.3 by going unphysical: positive g00 enthalpy with -172 J/K entropy, the
# degenerate-valley pattern, so the 3-term physically-sane solution is kept).
STORED = [-156581.1, 2.159, 133468.2]


def main():
    if "--fit" in sys.argv:
        from scipy.optimize import least_squares
        sol = least_squares(residual, STORED, diff_step=0.05, xtol=1e-8)
        print("fitted:", sol.x, "cost", sol.cost)
        vec = sol.x
    else:
        vec = STORED
    terms = [ExcessTerm(a=vec[0], b=vec[1], p=0, q=0), ExcessTerm(a=vec[2], b=0.0, p=1, q=0)]
    m, _ = evaluate(terms, f"terms a={vec[0]:.0f}+{vec[1]:.2f}T, chi a={vec[2]:.0f}")
    per = peritectic_check(m, 1808.15)
    print(f"  C3A at R&W peritectic T (1808 K): {'decomposed (peritectic)' if per > 0 else 'stable'}"
          f"  [margin {per:+.0f} J/unit]")


if __name__ == "__main__":
    main()
