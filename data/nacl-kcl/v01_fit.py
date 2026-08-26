"""Fit the NaCl-KCl liquid to the measured mixing enthalpy and validate the diagram.

Fitted: one Q-code term (enthalpy only, Z = 6) to Hersh & Kleppa (1965):
dH_mix = -547 J/mol of mixture at x = 0.5, 1083.15 K.
Built in: halite W = 2R*768.15 from the evaluated solvus consolute.
VALIDATION (not fitted): the liquidus minimum, evaluated at 931.15 K (Sangster &
Pelton 1987) - the model's minimum is a prediction from the endmembers + the two
fitted excesses.
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
from mqmqa._abi import _lib, _ffi

R = 8.3145
DH_MEAS, X_MEAS, T_MEAS = -547.0, 0.5, 1083.15
T_MINIMUM_MEAS = 931.15


class Model:
    def __init__(self, dat_path):
        self.db = mqmqa.Database.read(str(dat_path))
        self.p = self.db.phase_index("NACL-KCL-LIQUID")
        names = [_ffi.string(_lib.mqmqa_db_phase_name(self.db._db, i)).decode()
                 for i in range(_lib.mqmqa_db_num_phases(self.db._db))]
        self.hal = names.index("HALITE")
        self._cache = {}

    def g_liq(self, x, T):
        """Liquid Gibbs per mole of salt units at KCl fraction x."""
        if T not in self._cache:
            inp = eq.build_inputs(self.db, self.p, T, components=["NA", "K", "CL"])
            gm, _ = dbbuild._binary_activity_solver(inp, 2.0, 2.0)
            self._cache[T] = gm
        return self._cache[T](x) * 2.0

    def g_mix_liq(self, x, T):
        return self.g_liq(x, T) - (1 - x) * self.g_liq(1e-9, T) - x * self.g_liq(1 - 1e-9, T)

    def dh_mix(self, x, T, h=2.0):
        """Mixing enthalpy via H = -T^2 d(G/T)/dT, numeric."""
        f = lambda t: self.g_mix_liq(x, t) / t
        return -T * T * (f(T + h) - f(T - h)) / (2 * h)

    def g_hal(self, x, T):
        """Halite Gibbs per mole at KCl site fraction x (constituents [K, Na])."""
        Y = _ffi.new("double[]", [x, 1.0 - x, 1.0])
        return _lib.mqmqa_ph_cef_gibbs(self.db._db, self.hal, Y, T, 0)


def liquidus_minimum(model, T_lo=850.0, T_hi=1050.0):
    """T and x where the liquid surface first touches the halite surface (same x)."""
    xs = np.linspace(0.02, 0.98, 97)

    def gap(T):
        d = [model.g_liq(float(x), T) - model.g_hal(float(x), T) for x in xs]
        k = int(np.argmin(d))
        return d[k], float(xs[k])

    lo, hi = T_lo, T_hi
    if gap(lo)[0] < 0 or gap(hi)[0] > 0:
        return None, None
    for _ in range(24):
        mid = 0.5 * (lo + hi)
        lo, hi = (lo, mid) if gap(mid)[0] < 0 else (mid, hi)
    T = 0.5 * (lo + hi)
    return T, gap(T)[1]


def solvus_consolute(model):
    """Highest T with a concave region in the halite G curve."""
    xs = np.linspace(0.05, 0.95, 181)

    def concave(T):
        g = np.array([model.g_hal(float(x), T) for x in xs])
        return np.any(np.diff(g, 2) < 0)

    lo, hi = 500.0, 1000.0
    if not concave(lo) or concave(hi):
        return None
    for _ in range(22):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if concave(mid) else (lo, mid)
    return 0.5 * (lo + hi)


def evaluate(terms, label):
    m = Model(build_dat.build(terms))
    print(f"--- {label} ---")
    dh = m.dh_mix(X_MEAS, T_MEAS)
    print(f"  dH_mix(0.5, 1083 K): {dh:7.1f} J/mol (measured {DH_MEAS})")
    Tc = solvus_consolute(m)
    print(f"  solvus consolute: {'none' if Tc is None else f'{Tc:6.1f}'} K "
          f"(evaluated 768.2; built in via W = 2RTc)")
    Tm, xm = liquidus_minimum(m)
    print(f"  liquidus minimum: {'none' if Tm is None else f'{Tm:6.1f}'} K at x_KCl "
          f"{'--' if xm is None else f'{xm:.3f}'}  [VALIDATION: evaluated 931.2 K]")
    return m


# Fitted 2026-08-26 to the Hersh-Kleppa point (reproduced exactly); see PROVENANCE.md.
STORED = [-715.1]


def main():
    if "--fit" in sys.argv:
        from scipy.optimize import brentq
        f = lambda L: Model(build_dat.build([ExcessTerm(a=L, b=0.0, p=0, q=0)])).dh_mix(X_MEAS, T_MEAS) - DH_MEAS
        L = brentq(f, -8000.0, 0.0, xtol=0.1)
        print("fitted L =", round(L, 1))
        vec = [L]
    else:
        vec = STORED
    evaluate([ExcessTerm(a=vec[0], b=0.0, p=0, q=0)], f"L = {vec[0]:.1f} (Z = 6)")


if __name__ == "__main__":
    main()
