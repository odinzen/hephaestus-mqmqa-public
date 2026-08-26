"""Fit the Al2O3-SiO2 liquid excess and classify mullite's melting.

Fitted target (the one usable Rankin & Wright invariant, see PROVENANCE.md):
  silica-side eutectic (mullite + cristobalite): 1883.15 K, liquid 13 wt% Al2O3
  -> x_AlO1.5 = 0.1497.

Reported, NOT fitted: the Al-rich side. R&W's own Al-rich invariants assume their
"sillimanite" compound (62.9 wt% Al2O3); Bowen & Greig (1924) showed the stable compound
is mullite (71.8 wt%), so those numbers are topologically unusable. The model's mullite
melting behaviour (congruent vs peritectic, and its temperature) is a prediction reported
against the literature controversy (Aksay & Pask: peritectic ~2101 K; Klug: congruent
~2163 K).
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
from mqmqa.dbbuild import ExcessTerm

M_SIO2, M_AL2O3 = 60.084, 101.961


def wt_al2o3_to_x(wt):
    n_al = 2.0 * wt / M_AL2O3
    n_si = (100.0 - wt) / M_SIO2
    return n_al / (n_al + n_si)


T_EUT, X_EUT = 1883.15, wt_al2o3_to_x(13.0)
ATOMS = {"SiO2": 3.0, "AlO1.5": 2.5}


class Model:
    def __init__(self, dat_path):
        self.db = mqmqa.Database.read(str(dat_path))
        self.p = self.db.phase_index("SIO2-ALO1.5-LIQUID")
        self._cache = {}

    def g_liq(self, x, T):
        """Absolute liquid Gibbs per mole of cation units at AlO1.5 fraction x."""
        if T not in self._cache:
            inp = eq.build_inputs(self.db, self.p, T, components=["SI", "AL", "O"])
            gm, _ = dbbuild._binary_activity_solver(inp, ATOMS["SiO2"], ATOMS["AlO1.5"])
            self._cache[T] = gm
        atoms = (1.0 - x) * ATOMS["SiO2"] + x * ATOMS["AlO1.5"]
        return self._cache[T](x) * atoms

    @staticmethod
    def g_solid(name, T):
        """Solid Gibbs per mole of cation units, and its x position."""
        n_si, n_al, cf = build_dat.SOLIDS[name]
        A, B, C, D, E, F, G05 = build_dat.solid_gibbs_coeffs_sqrt(
            cf["dHf"], cf["S298"], cf["a"], cf["b"], cf["c"], cf["d"])
        g = (A + B * T + C * T * math.log(T) + D * T * T + E * T ** 3 + F / T
             + G05 * math.sqrt(T))
        units = n_si + n_al
        return g / units, n_al / units


def eutectic_T(model, lo_name, hi_name, T_lo=1500.0, T_hi=2400.0):
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
    # refine the touch composition on a dense local grid (the coarse scan quantizes x)
    _, x0 = depth(T)
    g1, x1 = model.g_solid(lo_name, T)
    g2, x2 = model.g_solid(hi_name, T)
    xs = np.linspace(max(x1 + 1e-4, x0 - 0.05), min(x2 - 1e-4, x0 + 0.05), 160)
    chord = g1 + (g2 - g1) * (xs - x1) / (x2 - x1)
    vals = np.array([model.g_liq(float(x), T) for x in xs]) - chord
    return T, float(xs[vals.argmin()])


def congruent_T(model, name, T_lo=1500.0, T_hi=2600.0):
    _, x = model.g_solid(name, 1800.0)

    def f(T):
        gs, _ = model.g_solid(name, T)
        return model.g_liq(x, T) - gs

    lo, hi = T_lo, T_hi
    if f(lo) * f(hi) > 0:
        return None
    for _ in range(26):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if f(lo) * f(mid) > 0 else (lo, mid)
    return 0.5 * (lo + hi)


def mullite_classification(model):
    """Congruent vs peritectic: at mullite's would-be congruent point, does the
    corundum-liquid construction already undercut it?"""
    Tc = congruent_T(model, "Al6Si2O13")
    if Tc is None:
        return None, "no melting found below 2600 K"
    g_m, x_m = model.g_solid("Al6Si2O13", Tc - 1.0)
    g_c, _ = model.g_solid("Al2O3_corundum", Tc - 1.0)
    # tangent from corundum (x=1) to the liquid curve, evaluated at mullite's x
    slopes = [(model.g_liq(float(x), Tc - 1.0) - g_c) / (x - 1.0)
              for x in np.linspace(0.30, 0.72, 40)]
    tangent_at_m = g_c + max(slopes) * (x_m - 1.0)
    if tangent_at_m < g_m:
        return Tc, "peritectic (corundum + liquid undercut mullite at its melting point)"
    return Tc, "congruent"


def evaluate(terms, label):
    dat = build_dat.build(terms)
    m = Model(dat)
    print(f"--- {label} ---")
    T, x = eutectic_T(m, "SiO2_cristobalite", "Al6Si2O13")
    print(f"  eut cristobalite/mullite: T {'none' if T is None else f'{T:7.1f}'} K "
          f"(meas {T_EUT})  x {'--' if x is None else f'{x:.3f}'} (meas {X_EUT:.3f})")
    T2, x2 = eutectic_T(m, "Al6Si2O13", "Al2O3_corundum")
    print(f"  mullite/corundum invariant: T {'none' if T2 is None else f'{T2:7.1f}'} K "
          f"x {'--' if x2 is None else f'{x2:.3f}'}  [prediction]")
    Tc, verdict = mullite_classification(m)
    print(f"  mullite melting: {'none' if Tc is None else f'{Tc:7.1f}'} K, {verdict}  "
          f"[prediction; lit.: peritectic ~2101 K (Aksay-Pask) vs congruent ~2163 K (Klug)]")
    return m


# Fitted 2026-08-26 to the silica-side eutectic (T, x), hit exactly. The silica-local
# chi_Si^5 form is the family's silica-gap lever; a global positive term was tried and
# rejected (it drags the eutectic composition silica-ward and overheats the mullite
# liquidus). No stable liquid demixing at 1900-2300 K (checked).
STORED = [9317.3, 33855.3]


def terms_from(vec):
    return [ExcessTerm(a=vec[0], b=0.0, p=0, q=0), ExcessTerm(a=vec[1], b=0.0, p=5, q=0)]


def residual(vec):
    m = Model(build_dat.build(terms_from(vec)))
    T, x = eutectic_T(m, "SiO2_cristobalite", "Al6Si2O13")
    res = [((T if T is not None else 800.0) - T_EUT) / 10.0,
           ((x - X_EUT) / 0.01) if x is not None else 10.0]
    print("  vec", np.round(vec, 1), "resid", np.round(res, 2))
    return np.asarray(res, float)


def main():
    if "--fit" in sys.argv:
        from scipy.optimize import least_squares
        sol = least_squares(residual, STORED if STORED[1] else [STORED[0], -10000.0],
                            diff_step=0.08, xtol=1e-9)
        print("fitted:", sol.x, "cost", sol.cost)
        vec = sol.x
    else:
        vec = STORED
    evaluate(terms_from(vec), f"L = {vec[0]:.1f} + {vec[1]:.1f} chi_Si")


if __name__ == "__main__":
    main()
