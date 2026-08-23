"""v0.9: widen the two-liquid gap to the measured conjugates while holding the low dome.

v0.8 (with the consolute now a hard target) brought the dome from ~3175 K down to ~2340 K
(measured 2244) with the calorimetry and invariants intact - but the gap at the monotectic
came out too narrow (0.67-0.967 vs the measured ~0.60/0.99). Widening the base needs a
BROAD silica term (reaching the MgO-rich conjugate ~0.60) plus a SHARP one (pushing the
silica edge to ~0.99); each carries its own enthalpy (omega) and entropy (eta) so the dome
stays low. Silica side = (0,3) broad + (0,7) sharp, on top of the (0,0)+(0,1) central
(= the v0.5 ordering in the verified Y_SiO2 basis).

Data targets (all 1-atm, condensed):
    monotectic 1968 K, conjugates x_SiO2 = 0.60 and 0.99 (Greig 1927 / Ol'shanskii 1951,
        Hudon-Baker 2002 selected 0.604/0.989)
    consolute  2240 K, x_SiO2 = 0.84 (Hageman & Oonk 1986, rapid-quench; Belmonte 2017)
    + the four condensed invariants + the MLIP/calorimetry dH_mix.
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
import phase_diagram as pdg
import v05_fit as vf
from mqmqa import equilibrium as eq
import _activity as act

pdg.USE_COMPOUND_CP = False
COMP = pdg.COMPONENTS
DH13, DH12 = -24.5, -22.4
T_MONO, X_ML, X_SL = 1968.0, 0.60, 0.99
T_CONS, X_CONS = 2240.0, 0.84


def build_db(pp):
    a00, b00, a01, b01, a03, b03, a07, b07 = pp
    excess = [dict(code="Q", li=[1, 2, 3, 3], exp=[0, 0, 0, 0], coeffs=[a00, b00, 0, 0, 0, 0]),
              dict(code="Q", li=[1, 2, 3, 3], exp=[0, 1, 0, 0], coeffs=[a01, b01, 0, 0, 0, 0]),
              dict(code="Q", li=[1, 2, 3, 3], exp=[0, 3, 0, 0], coeffs=[a03, b03, 0, 0, 0, 0]),
              dict(code="Q", li=[1, 2, 3, 3], exp=[0, 7, 0, 0], coeffs=[a07, b07, 0, 0, 0, 0])]
    import os
    path = HERE / f"_v09_{os.getpid()}.dat"
    path.write_text(bd.build(excess, version="v0.9"), encoding="ascii")
    db = mqmqa.Database.read(str(path))
    return db, db.phase_index("MGO-SIO2-LIQUID"), excess


def dh_mix(db, p, x, T=2100.0, dT=40.0):
    g = lambda TT: act.delta_g_mix(eq.build_inputs(db, p, TT, components=COMP), x)
    return (g(T) - T * (g(T + dT) - g(T - dT)) / (2 * dT)) / 1000.0


def consolute(db, p, lo=1980.0, hi=3200.0):
    Tclose, xc, last = None, None, vf.gap(db, p, lo)
    T = lo
    while T <= hi:
        g = vf.gap(db, p, T)
        if g is None:
            Tclose = T
            if last:
                xc = 0.5 * (last[0] + last[1])
            break
        last = g
        T += 35.0
    return Tclose, xc


def residuals(pp):
    db, p, _ = build_db(pp)
    r = vf.all_invariants(db, p)
    out = []
    for key, tgt in vf.TARGETS:
        v = r[key]
        out.append((v - tgt) / 100.0 if v else vf.PENALTY)
    gm = vf.gap(db, p, T_MONO)
    if gm:
        out.append((gm[0] - X_ML) / 0.025)
        out.append((gm[1] - X_SL) / 0.025)
    else:
        out += [vf.PENALTY, vf.PENALTY]
    Tc, xc = consolute(db, p)
    if Tc:
        out.append((Tc - T_CONS) / 50.0)
        out.append((xc - X_CONS) / 0.05 if xc else 0.0)
    else:
        out += [vf.PENALTY, 0.0]
    out.append((dh_mix(db, p, 1 / 3.) - DH13) / 5.0)
    out.append((dh_mix(db, p, 0.5) - DH12) / 6.0)
    return np.asarray(out, float)


def fit(p0):
    vf.RES = vf.FAST
    n = [0]
    def fun(pp):
        n[0] += 1
        res = residuals(pp)
        print(f"  eval {n[0]:3d} cost={0.5*float(res@res):7.3f}  " + " ".join(f"{v:8.0f}" for v in pp))
        return res
    sol = least_squares(fun, p0, diff_step=0.03, max_nfev=220,
                        x_scale=[1e5, 5, 1e5, 5e1, 3e5, 1e2, 6e5, 1e2])
    return sol.x


def report(pp, write=False):
    vf.RES = vf.FINE
    db, p, excess = build_db(pp)
    r = vf.all_invariants(db, p)
    print("\n  v0.9 model:")
    for name, key, tgt in [("forsterite", "forsterite", vf.T_FORST),
                           ("peri-forst eut", "peri_forst_eut", vf.T_PERI_FORST_EUT),
                           ("enstatite peri", "enst_peri", vf.T_ENST_PERI),
                           ("En-Crs eut", "encr_eut", vf.T_ENCR_EUT)]:
        v = r[key]
        print(f"    {name:16s} {v:6.0f} K  meas {tgt}  dT {v-tgt:+5.0f}" if v else f"    {name}: none")
    gm = vf.gap(db, p, T_MONO)
    Tc, xc = consolute(db, p)
    print(f"    monotectic gap@1968 {gm[0]:.3f}-{gm[1]:.3f}  (meas 0.60/0.99)" if gm else "    gap none")
    print(f"    consolute ~{Tc} K at x~{xc:.2f}  (meas 2240 K, 0.84)" if Tc else "    consolute none")
    print(f"    dH_mix(1/3)={dh_mix(db,p,1/3.):+.1f} dH_mix(1/2)={dh_mix(db,p,0.5):+.1f} (MLIP {DH13}/{DH12})")
    if write:
        (HERE / "MgO-SiO2-liquid.dat").write_text(bd.build(excess, version="v0.9"), encoding="ascii")
        print("  wrote MgO-SiO2-liquid.dat")
    return r


if __name__ == "__main__":
    # start from the v0.8 result (6-param) re-expressed with a split silica side:
    # its (0,5) a05=+148730,b05=-25 seeded across a broad (0,3) + sharp (0,7).
    p0 = [-32000.0, -3.5, -70000.0, 1.7, 60000.0, -12.0, 160000.0, -30.0]
    pp = fit(p0) if "--fit" in sys.argv else p0
    report(pp, write=("--write" in sys.argv))
    print("\n  params:", [round(float(x), 1) for x in pp])
