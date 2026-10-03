"""Assess the magnesiowustite excess (L0, L1) against dataset.py, with the shipped olivine
(Robie-Hemingway endmembers, Wood & Kleppa 1981 excess) held fixed.

Run:  python assess.py [--fit]
"""
import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq, least_squares

HERE = Path(__file__).resolve().parent


def _load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


mw = _load("mw_model", HERE.parent / "magnesiowustite.py")
em = _load("mw_ol_em", HERE.parents[1] / "olivine" / "endmembers.py")
ds = _load("mw_dataset", HERE / "dataset.py")
R = mw.R
OL_L0, OL_L1 = 3000.0 * 4.184, 1000.0 * 4.184      # olivine, Wood & Kleppa 1981


def mu_ex_mw(x, T):
    """Fe-Mg exchange potential of magnesiowustite, per cation."""
    d = (1 - 2 * x) * (mw.L0 + mw.L1 * (2 * x - 1)) + 2 * mw.L1 * x * (1 - x)
    return mw.g_end("FEO", T) - mw.g_end("MGO", T) + R * T * math.log(x / (1 - x)) + d


def mu_ex_ol(x, T):
    d = (1 - 2 * x) * (OL_L0 + OL_L1 * (2 * x - 1)) + 2 * OL_L1 * x * (1 - x)
    return (em.gibbs("fayalite", T) - em.gibbs("forsterite", T) + 2 * R * T * math.log(x / (1 - x)) + d) / 2


def residuals(pp, detail=False):
    mw.L0, mw.L1 = float(pp[0]), float(pp[1])
    T, rows = ds.T, []
    for x, aF, aM, x_ol in ds.TABLE9:
        gF, gM = mw.ln_gamma(x, T)
        rows.append((f"a(FeO) x={x:.2f}", (math.log(x) + gF - math.log(aF)) / ds.SIG_LN_A,
                     f"{x * math.exp(gF):.3f}/{aF:.2f}"))
        rows.append((f"a(MgO) x={x:.2f}", (math.log(1 - x) + gM - math.log(aM)) / ds.SIG_LN_A,
                     f"{(1 - x) * math.exp(gM):.3f}/{aM:.2f}"))
        t = mu_ex_mw(x, T)
        xo = brentq(lambda z: mu_ex_ol(z, T) - t, 1e-6, 1 - 1e-6, xtol=1e-10)
        rows.append((f"olivine at mw {x:.2f}", (xo - x_ol) / ds.SIG_X_OL, f"{xo:.3f}/{x_ol:.2f}"))
    res = np.array([r for _, r, _ in rows])
    return (res, rows) if detail else res


def report(pp):
    res, rows = residuals(pp, detail=True)
    for tag, r, info in rows:
        print(f"    {tag:24s} {info:14s} r={r:+6.2f}")
    print(f"\n  total cost = {0.5 * float(res @ res):.3f}   RMS residual = {np.sqrt(np.mean(res ** 2)):.2f}")


if __name__ == "__main__":
    p0 = [mw.L0, mw.L1]
    pp = least_squares(residuals, p0 if any(p0) else [12000.0, 1000.0]).x if "--fit" in sys.argv else p0
    report(pp)
    print("\n  params: L0 =", round(float(pp[0]), 1), " L1 =", round(float(pp[1]), 1))
