"""Fit KCl-MgCl2: liquid excess + KMgCl3 formation enthalpy to the measured invariants.

Targets (three parameters, three targets):
  KMgCl3 congruent melting: 761.65 K (Perry & Fletcher 1993)
  KCl-side eutectic: 697.55 K at x(MgCl2) = 0.375 (Xu 2018; Perry & Fletcher's
    699.15 K K2MgCl4/K3Mg2Cl7 eutectic is the same feature within source spread -
    the narrow K2MgCl4/K3Mg2Cl7 window is not resolved in v0.1)

Validation (not fitted): Xu 2018 eutectic fusion enthalpy 207 J/g = 17.04 kJ/mol of
mixture. Reported as prediction: the MgCl2-side eutectic.
"""
import importlib.util
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))

# Load build_dat by path under a unique name: a bare `import build_dat` collides
# with the other systems' build_dat.py in the shared test process (sys.modules).
_spec = importlib.util.spec_from_file_location("kcl_mgcl2_build_dat", HERE / "build_dat.py")
build_dat = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_dat)

import mqmqa
from mqmqa import dbbuild
from mqmqa import equilibrium as eq
from mqmqa.dbbuild import ExcessTerm, solid_gibbs_coeffs

T_CONG, T_EUT, X_EUT = 761.65, 697.55, 0.375
DH_EUT_MEAS = 207.0 * (0.625 * 74.551 + 0.375 * 95.211) / 1000.0   # 17.04 kJ/mol mixture
ATOMS = {"KCl": 2.0, "MgCl2": 3.0}


class Model:
    def __init__(self, dat_path):
        self.db = mqmqa.Database.read(str(dat_path))
        self.p = self.db.phase_index("KCL-MGCL2-LIQUID")
        self._cache = {}

    def g_liq(self, x, T):
        """Liquid Gibbs per mole of salt units at MgCl2 fraction x."""
        if T not in self._cache:
            inp = eq.build_inputs(self.db, self.p, T, components=["K", "MG", "CL"])
            gm, _ = dbbuild._binary_activity_solver(inp, ATOMS["KCl"], ATOMS["MgCl2"])
            self._cache[T] = gm
        atoms = (1 - x) * ATOMS["KCl"] + x * ATOMS["MgCl2"]
        return self._cache[T](x) * atoms

    @staticmethod
    def g_solid(name, T, dhf_ox):
        if name == "KCl_solid":
            cf, units, x = (build_dat.KCL.dHf, build_dat.KCL.S298, build_dat.KCL.a,
                            build_dat.KCL.b, build_dat.KCL.c), 1, 0.0
        elif name == "MgCl2_solid":
            cf, units, x = (build_dat.MGCL2.dHf, build_dat.MGCL2.S298, build_dat.MGCL2.a,
                            build_dat.MGCL2.b, build_dat.MGCL2.c), 1, 1.0
        else:  # KMgCl3 = 2 salt units
            cf, units, x = (build_dat.KCL.dHf + build_dat.MGCL2.dHf + dhf_ox,
                            build_dat.KMC_S298, *build_dat.KMC_CP), 2, 0.5
        A, B, C, D, E, F = solid_gibbs_coeffs(*cf)
        g = A + B * T + C * T * math.log(T) + D * T * T + E * T ** 3 + F / T
        return g / units, x


def eutectic(model, dhf_ox, lo_name, hi_name, T_lo=550.0, T_hi=1050.0):
    def depth(T):
        g1, x1 = model.g_solid(lo_name, T, dhf_ox)
        g2, x2 = model.g_solid(hi_name, T, dhf_ox)
        xs = np.linspace(x1 + 1e-3, x2 - 1e-3, 40)
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
    _, x0 = depth(T)
    g1, x1 = model.g_solid(lo_name, T, dhf_ox)
    g2, x2 = model.g_solid(hi_name, T, dhf_ox)
    xs = np.linspace(max(x1 + 1e-4, x0 - 0.05), min(x2 - 1e-4, x0 + 0.05), 160)
    chord = g1 + (g2 - g1) * (xs - x1) / (x2 - x1)
    vals = np.array([model.g_liq(float(x), T) for x in xs]) - chord
    return T, float(xs[vals.argmin()])


def congruent(model, dhf_ox, T_lo=600.0, T_hi=1000.0):
    def f(T):
        gs, x = model.g_solid("KMgCl3", T, dhf_ox)
        return model.g_liq(0.5, T) - gs

    lo, hi = T_lo, T_hi
    if f(lo) * f(hi) > 0:
        return None
    for _ in range(24):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if f(lo) * f(mid) > 0 else (lo, mid)
    return 0.5 * (lo + hi)


def h_of_g(gfun, T, h=0.5):
    return gfun(T) - T * (gfun(T + h) - gfun(T - h)) / (2 * h)


def eutectic_fusion_enthalpy(model, dhf_ox, x=X_EUT, T=T_EUT):
    """kJ per mole of (KCl, MgCl2) mixture: liquid minus the KCl_s + KMgCl3 mix."""
    f_kmc = x / 0.5                    # lever between KCl_s (0) and KMgCl3 (0.5), salt units
    h_liq = h_of_g(lambda t: model.g_liq(x, t), T)
    h_sol = ((1 - f_kmc) * h_of_g(lambda t: model.g_solid("KCl_solid", t, dhf_ox)[0], T)
             + f_kmc * h_of_g(lambda t: model.g_solid("KMgCl3", t, dhf_ox)[0], T))
    return (h_liq - h_sol) / 1000.0


def evaluate(vec, label):
    dhf_ox, a00, a10 = vec
    terms = [ExcessTerm(a=a00, b=0.0, p=0, q=0), ExcessTerm(a=a10, b=0.0, p=1, q=0)]
    m = Model(build_dat.build(dhf_ox, terms))
    print(f"--- {label} ---")
    Tc = congruent(m, dhf_ox)
    print(f"  KMgCl3 congruent: {'none' if Tc is None else f'{Tc:6.1f}'} K (meas {T_CONG})")
    T, x = eutectic(m, dhf_ox, "KCl_solid", "KMgCl3")
    print(f"  KCl-side eutectic: {'none' if T is None else f'{T:6.1f}'} K at x "
          f"{'--' if x is None else f'{x:.3f}'} (meas {T_EUT}, {X_EUT})")
    T2, x2 = eutectic(m, dhf_ox, "KMgCl3", "MgCl2_solid")
    print(f"  Mg-side eutectic: {'none' if T2 is None else f'{T2:6.1f}'} K at x "
          f"{'--' if x2 is None else f'{x2:.3f}'}  [prediction]")
    dh = eutectic_fusion_enthalpy(m, dhf_ox)
    print(f"  eutectic fusion enthalpy: {dh:.2f} kJ/mol vs Xu 2018 {DH_EUT_MEAS:.2f} (not fitted)")
    return m


# Fitted 2026-08-26 (with KMC_DS_OX = +26.2 baked into build_dat); see PROVENANCE.md.
STORED = [build_dat.KMC_DHF_OX, build_dat.LIQ_A00, build_dat.LIQ_A10]


def residual(vec):
    dhf_ox, a00, a10 = vec
    terms = [ExcessTerm(a=a00, b=0.0, p=0, q=0), ExcessTerm(a=a10, b=0.0, p=1, q=0)]
    m = Model(build_dat.build(dhf_ox, terms))
    Tc = congruent(m, dhf_ox)
    T, x = eutectic(m, dhf_ox, "KCl_solid", "KMgCl3")
    res = [((Tc if Tc is not None else 300.0) - T_CONG) / 5.0,
           ((T if T is not None else 300.0) - T_EUT) / 5.0,
           ((x - X_EUT) / 0.01) if x is not None else 10.0]
    print("  vec", np.round(vec), "resid", np.round(res, 2))
    return np.asarray(res, float)


def main():
    if "--fit" in sys.argv:
        from scipy.optimize import least_squares
        sol = least_squares(residual, STORED, diff_step=0.08, xtol=1e-9)
        print("fitted:", np.round(sol.x, 1), "cost", round(sol.cost, 4))
        vec = list(sol.x)
    else:
        vec = STORED
    evaluate(vec, f"dHf_ox={vec[0]:.0f}, L={vec[1]:.0f}{vec[2]:+.0f}*chi_K")


if __name__ == "__main__":
    main()
