"""Fit NaCl-MgCl2: the liquid excess to the single measured eutectic.

Target (two parameters, two targets): the NaCl-MgCl2 eutectic 718.15 K (445 degC) at
x(MgCl2) = 0.42 (DLR 2021 review, Table 1; compiled experimental value).

Soft cross-check (not fitted): Duemmler 2022 AIMD heat capacity of the molten eutectic,
75 J/mol/K at 42.7 mol% MgCl2, 1100 K. Reported as a prediction alongside the model's
own eutectic-liquid Cp.
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))

# Load build_dat by path under a unique name (a bare import collides with the other
# systems' build_dat.py in the shared test process; see kcl-mgcl2/v01_fit.py).
_spec = importlib.util.spec_from_file_location("nacl_mgcl2_build_dat", HERE / "build_dat.py")
build_dat = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_dat)

import mqmqa
from mqmqa import dbbuild
from mqmqa import equilibrium as eq
from mqmqa.dbbuild import ExcessTerm, solid_gibbs_coeffs

T_EUT, X_EUT = 718.15, 0.42
ATOMS = {"NaCl": 2.0, "MgCl2": 3.0}


class Model:
    def __init__(self, dat_path):
        self.db = mqmqa.Database.read(str(dat_path))
        self.p = self.db.phase_index("NACL-MGCL2-LIQUID")
        self._cache = {}

    def g_liq(self, x, T):
        """Liquid Gibbs per mole of salt units at MgCl2 fraction x."""
        if T not in self._cache:
            inp = eq.build_inputs(self.db, self.p, T, components=["NA", "MG", "CL"])
            gm, _ = dbbuild._binary_activity_solver(inp, ATOMS["NaCl"], ATOMS["MgCl2"])
            self._cache[T] = gm
        return self._cache[T](x) * ((1 - x) * ATOMS["NaCl"] + x * ATOMS["MgCl2"])

    @staticmethod
    def g_solid(name, T):
        if name == "NaCl_solid":
            cf, x = (build_dat.NACL.dHf, build_dat.NACL.S298, build_dat.NACL.a,
                     build_dat.NACL.b, build_dat.NACL.c), 0.0
        else:  # MgCl2_solid
            cf, x = (build_dat.MGCL2.dHf, build_dat.MGCL2.S298, build_dat.MGCL2.a,
                     build_dat.MGCL2.b, build_dat.MGCL2.c), 1.0
        import math
        A, B, C, D, E, F = solid_gibbs_coeffs(*cf)
        return A + B * T + C * T * math.log(T) + D * T * T + E * T ** 3 + F / T, x


def eutectic(model, T_lo=500.0, T_hi=1000.0):
    def depth(T):
        g1, x1 = model.g_solid("NaCl_solid", T)
        g2, x2 = model.g_solid("MgCl2_solid", T)
        xs = np.linspace(x1 + 1e-3, x2 - 1e-3, 60)
        chord = g1 + (g2 - g1) * (xs - x1) / (x2 - x1)
        vals = np.array([model.g_liq(float(x), T) for x in xs]) - chord
        return float(vals.min()), float(xs[vals.argmin()])

    lo, hi = T_lo, T_hi
    if depth(lo)[0] < 0 or depth(hi)[0] > 0:
        return None, None
    for _ in range(24):
        mid = 0.5 * (lo + hi)
        lo, hi = (lo, mid) if depth(mid)[0] < 0 else (mid, hi)
    T = 0.5 * (lo + hi)
    _, x0 = depth(T)
    xs = np.linspace(max(1e-4, x0 - 0.05), min(1 - 1e-4, x0 + 0.05), 200)
    g1, _ = model.g_solid("NaCl_solid", T)
    g2, _ = model.g_solid("MgCl2_solid", T)
    chord = g1 + (g2 - g1) * xs
    vals = np.array([model.g_liq(float(x), T) for x in xs]) - chord
    return T, float(xs[vals.argmin()])


def cp_liquid(model, x, T, h=1.0):
    """-T d2G/dT2 of the liquid, per mole of salt units (J/mol/K)."""
    g0 = model.g_liq(x, T)
    gp = model.g_liq(x, T + h)
    gm = model.g_liq(x, T - h)
    return -T * (gp - 2 * g0 + gm) / (h * h)


def evaluate(vec, label):
    a00, a10 = vec
    m = Model(build_dat.build(_terms(vec)))
    print(f"--- {label} ---")
    T, x = eutectic(m)
    print(f"  eutectic: {'none' if T is None else f'{T:6.1f}'} K at x(MgCl2) "
          f"{'--' if x is None else f'{x:.3f}'} (meas {T_EUT}, {X_EUT})")
    cp = cp_liquid(m, 0.427, 1100.0)
    print(f"  eutectic-liquid Cp: {cp:.1f} J/mol/K vs Duemmler 2022 AIMD 75 (not fitted)")
    return m


def _terms(vec):
    a00, a10 = vec
    terms = [ExcessTerm(a=a00, b=0.0, p=0, q=0)]
    if a10:
        terms.append(ExcessTerm(a=a10, b=0.0, p=1, q=0))
    return terms


# Fitted 2026-08-26; see PROVENANCE.md.
STORED = [build_dat.LIQ_A00, build_dat.LIQ_A10]


def residual(vec):
    m = Model(build_dat.build(_terms(vec)))
    T, x = eutectic(m)
    res = [((T if T is not None else 300.0) - T_EUT) / 5.0,
           ((x - X_EUT) / 0.01) if x is not None else 20.0]
    print("  vec", np.round(vec), "resid", np.round(res, 2))
    return np.asarray(res, float)


def main():
    if "--fit" in sys.argv:
        from scipy.optimize import least_squares
        sol = least_squares(residual, STORED, diff_step=0.06, xtol=1e-9)
        print("fitted:", np.round(sol.x, 1), "cost", round(sol.cost, 4))
        vec = list(sol.x)
    else:
        vec = STORED
    evaluate(vec, f"L={vec[0]:.0f}{vec[1]:+.0f}*chi_Na")


if __name__ == "__main__":
    main()
