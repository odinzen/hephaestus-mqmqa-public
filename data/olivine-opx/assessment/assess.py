"""Assess the two-site orthopyroxene (orthopyroxene.py) against dataset.py.

Parameters: EXCH_H, EXCH_S, RECIP, W_M1, W_M2, FS_DHF_SHIFT, FS_HT_B. Olivine is the shipped
one-site CEF (Robie-Hemingway endmembers, Wood & Kleppa 1981 excess); quartz is the R&H
table. Pure Python on the model's own Gibbs function; the database files the builders write
from the same module are checked against it and against pycalphad in the tests.

Run:  python assess.py [--fit]
"""
import csv
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


opx = _load("opx_model", HERE.parent / "orthopyroxene.py")
em = opx.em
ds = _load("opx_dataset", HERE / "dataset.py")    # by path: other folders have a dataset.py

R = opx.R
NAMES = ["EXCH_H", "EXCH_S", "RECIP", "W_M1", "W_M2", "FS_DHF_SHIFT", "FS_HT_B"]
SCALE = [1e4, 5.0, 1e4, 1e4, 1e4, 3e3, 5.0]
OL_L0, OL_L1 = 3000.0 * 4.184, 1000.0 * 4.184       # olivine, Wood & Kleppa 1981


def _quartz():
    rows = []
    with open(HERE / "rh1995_quartz.csv", newline="") as fh:
        for r in csv.DictReader(line for line in fh if not line.startswith("#")):
            T = float(r["T_K"])
            rows.append((T, float(r["dfH298_kJ"]) * 1e3 + T * float(r["HT_minus_H298_over_T"])
                         - T * float(r["S"])))
    return np.array(rows)


QZ = _quartz()


def g_quartz(T):
    return float(np.interp(T, QZ[:, 0], QZ[:, 1]))


def set_params(pp):
    for n, v in zip(NAMES, pp):
        setattr(opx, n, float(v))


def dg_ol(x, T):
    """dG/dx of olivine per M2SiO4 (2 cations), x = Fe/(Fe+Mg)."""
    d = em.gibbs("fayalite", T) - em.gibbs("forsterite", T)
    ideal = 2 * R * T * math.log(x / (1 - x))
    ex = (1 - 2 * x) * (OL_L0 + OL_L1 * (2 * x - 1)) + x * (1 - x) * 2 * OL_L1
    return d + ideal + ex


def dg_opx(X, T, h=1e-5):
    return (opx.equilibrium(X + h, T)[0] - opx.equilibrium(X - h, T)[0]) / (2 * h)


def olivine_partner(X_px, T):
    target = dg_opx(X_px, T)
    return brentq(lambda x: dg_ol(x, T) - target, 1e-6, 1 - 1e-6, xtol=1e-10)


def h_state(x, y1, T):
    """Enthalpy per M2Si2O6 of the order state y1 at bulk x, against the endmembers."""
    y2 = 2 * x - y1
    h = 1e-3
    H = {n: opx.g_end(n, T) - T * (opx.g_end(n, T + h) - opx.g_end(n, T - h)) / (2 * h)
         for n in opx.ENDMEMBERS}
    hm = (y1 * y2 * H["FE:FE"] + y1 * (1 - y2) * H["FE:MG"] + (1 - y1) * y2 * H["MG:FE"]
          + (1 - y1) * (1 - y2) * H["MG:MG"] + opx.W_M1 * y1 * (1 - y1) + opx.W_M2 * y2 * (1 - y2))
    return hm - (1 - x) * H["MG:MG"] - x * H["FE:FE"]


def dh_mix_frozen(x, T):
    """Enthalpy of mixing per M2Si2O6 in the order state equilibrated at T."""
    return h_state(x, opx.equilibrium(x, T)[1], T)


def residuals(pp, detail=False):
    set_params(pp)
    rows = []
    for tc, xb, x1, _x2 in ds.SITES:
        _, y1, _ = opx.equilibrium(xb, tc + 273.15)
        rows.append((f"site {tc} C x={xb:.3f} M1", (y1 - x1) / ds.SIG_SITE, f"{y1:.3f}/{x1:.3f}"))
    for x_ol, x_px, how in ds.TIELINES:
        xo = olivine_partner(x_px, ds.T_TIE)
        rows.append((f"tie px {x_px:.2f} ({how})", (xo - x_ol) / ds.SIG_TIE, f"ol {xo:.3f}/{x_ol:.2f}"))
    for tc, pk in ds.BOHLEN:
        T = tc + 273.15
        dg = em.gibbs("fayalite", T) + g_quartz(T) - opx.g_end("FE:FE", T)
        tgt = -ds.DV_BOHLEN * pk * 1000.0
        rows.append((f"Bohlen {tc} C", (dg - tgt) / ds.SIG_BOHLEN, f"{dg:.0f}/{tgt:.0f}"))
    dh = dh_mix_frozen(0.5, ds.T_CAL)
    rows.append(("dH_mix x=0.5 (1393 K order)", (dh - ds.DH_MIX_HALF) / ds.SIG_DH_MIX,
                 f"{dh:.0f}/{ds.DH_MIX_HALF:.0f}"))
    y1_hot = opx.equilibrium(ds.X_DIS, ds.T_DIS)[1]
    dh_dis = h_state(ds.X_DIS, y1_hot, ds.T_DIS) - h_state(ds.X_DIS, y1_hot - ds.DY_DIS, ds.T_DIS)
    rows.append(("dH disorder En52.5 (dY 0.25)", (dh_dis - ds.DH_DIS) / ds.SIG_DH_DIS,
                 f"{dh_dis:.0f}/{ds.DH_DIS:.0f}"))
    rows.append(("ferrosilite dHf prior", opx.FS_DHF_SHIFT / ds.SIG_FS_SHIFT, f"{opx.FS_DHF_SHIFT:.0f}"))
    res = np.array([r for _, r, _ in rows])
    return (res, rows) if detail else res


def fit(p0):
    scale = np.array(SCALE)
    sol = least_squares(lambda u: residuals(u * scale), np.asarray(p0) / scale, diff_step=1e-3)
    return sol.x * scale


def report(pp):
    res, rows = residuals(pp, detail=True)
    for tag, r, info in rows:
        print(f"    {tag:34s} {info:18s} r={r:+6.2f}")
    print(f"\n  total cost = {0.5 * float(res @ res):.3f}   RMS residual = {np.sqrt(np.mean(res ** 2)):.2f}")


if __name__ == "__main__":
    p0 = [getattr(opx, n) for n in NAMES]
    for arg in sys.argv:
        if arg.startswith("--p0="):
            p0 = [float(v) for v in arg[5:].split(",")]
    pp = fit(p0) if "--fit" in sys.argv else p0
    report(pp)
    print("\n  params:", dict(zip(NAMES, [round(float(v), 4) for v in pp])))
