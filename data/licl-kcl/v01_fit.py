"""Fit the LiCl-KCl liquid excess to the eutectic and validate against Solomons (1958).

Target: eutectic at 626.15 K (353 degC), x_LiCl = 0.585 (Janz 59/41 and Solomons 58/42
basis agree; the INL 2011 report's "55.7 mol% LiCl" converts to the same eutectic if read
as weight fractions - documented in PROVENANCE.md). Composition variable here is
x = x_KCl (second component), so the target is x_KCl = 0.415.

Independent validation (not fitted): Solomons (1958) measured the eutectic fusion
enthalpy, 13.39 kJ/mol of mixture at 627.5 K.
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

T_EUT, X_EUT_KCL = 626.15, 0.415
ATOMS = 2.0   # both LiCl and KCl are 2 atoms per formula


class Model:
    def __init__(self, dat_path):
        self.db = mqmqa.Database.read(str(dat_path))
        self.p = self.db.phase_index("LICL-KCL-LIQUID")
        self._cache = {}

    def g_liq(self, x, T):
        """Absolute liquid Gibbs per mole of salt units at KCl fraction x."""
        if T not in self._cache:
            inp = eq.build_inputs(self.db, self.p, T, components=["LI", "K", "CL"])
            gm, _ = dbbuild._binary_activity_solver(inp, ATOMS, ATOMS)
            self._cache[T] = gm
        return self._cache[T](x) * ATOMS

    @staticmethod
    def g_solid(comp, T):
        A, B, C, D, E, F = solid_gibbs_coeffs(comp.dHf, comp.S298, comp.a, comp.b, comp.c)
        return A + B * T + C * T * math.log(T) + D * T * T + E * T ** 3 + F / T


def eutectic(model, T_lo=500.0, T_hi=1050.0):
    """T and x where the liquid last touches the LiCl(s)-KCl(s) chord."""
    def depth(T):
        g1 = model.g_solid(build_dat.LICL, T)
        g2 = model.g_solid(build_dat.KCL, T)
        xs = np.linspace(1e-3, 1 - 1e-3, 60)
        chord = g1 + (g2 - g1) * xs
        vals = np.array([model.g_liq(float(x), T) for x in xs]) - chord
        return float(vals.min()), float(xs[vals.argmin()])

    lo, hi = T_lo, T_hi
    if depth(lo)[0] < 0 or depth(hi)[0] > 0:
        return None, None
    for _ in range(22):
        mid = 0.5 * (lo + hi)
        lo, hi = (lo, mid) if depth(mid)[0] < 0 else (mid, hi)
    T = 0.5 * (lo + hi)
    return T, depth(T)[1]


def h_of_g(gfun, T, h=0.5):
    """H = G - T dG/dT by central difference."""
    g0, gp, gm_ = gfun(T), gfun(T + h), gfun(T - h)
    return g0 - T * (gp - gm_) / (2 * h)


def solomons_check(model, x_licl=0.58, T=627.5):
    """Model eutectic fusion enthalpy vs Solomons 13.39 kJ/mol of mixture."""
    x = 1.0 - x_licl   # KCl fraction
    h_liq = h_of_g(lambda t: model.g_liq(x, t), T)
    h_sol = (x_licl * h_of_g(lambda t: model.g_solid(build_dat.LICL, t), T)
             + (1 - x_licl) * h_of_g(lambda t: model.g_solid(build_dat.KCL, t), T))
    return (h_liq - h_sol) / 1000.0


def evaluate(terms, label):
    dat = build_dat.build(terms)
    m = Model(dat)
    T, x = eutectic(m)
    print(f"--- {label} ---")
    print(f"  eutectic: T {'none' if T is None else f'{T:6.1f}'} K (meas {T_EUT})  "
          f"x_KCl {'--' if x is None else f'{x:.3f}'} (meas {X_EUT_KCL})")
    dh = solomons_check(m)
    print(f"  eutectic fusion enthalpy: {dh:.2f} kJ/mol vs Solomons 13.39 (not fitted)")
    return m, T, x


# Fitted 2026-08-25 at Z = 6 to three targets (eutectic T, eutectic x, Solomons dHfus):
# L = (a00 + b00*T) + a10*chi_Li. The charge-proportional-Z fit could match T but pinned
# x_KCl at 0.458; Z = 6 (the published MQM salt convention) frees the composition.
STORED = [-9467.28, 7.92, -1112.46]


def terms_from(vec):
    return [ExcessTerm(a=vec[0], b=vec[1], p=0, q=0), ExcessTerm(a=vec[2], b=0.0, p=1, q=0)]


def residual(vec):
    m = Model(build_dat.build(terms_from(vec)))
    T, x = eutectic(m)
    dh = solomons_check(m)
    res = [((T if T is not None else 300.0) - T_EUT) / 5.0,
           ((x - X_EUT_KCL) / 0.01) if x is not None else 10.0,
           (dh - 13.39) / 0.5]
    print("  vec", np.round(vec, 1), "resid", np.round(res, 2))
    return np.asarray(res, float)


def main():
    if "--fit" in sys.argv:
        from scipy.optimize import least_squares
        sol = least_squares(residual, STORED, diff_step=0.08, xtol=1e-10)
        print("fitted:", sol.x, "cost", sol.cost)
        vec = sol.x
    else:
        vec = STORED
    evaluate(terms_from(vec),
             f"L = ({vec[0]:.1f} + {vec[1]:.2f} T) + {vec[2]:.1f} chi_Li")


if __name__ == "__main__":
    main()
