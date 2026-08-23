"""v0.8: fit the two-liquid dome to the measured monotectic AND consolute.

The missing constraint all along was the CONSOLUTE (dome height). Data gathered from the
literature (Belmonte et al. 2017 Chem. Geol. 461, matching the Hageman & Oonk 1986
equilibration/quench experiment; monotectic from Greig 1927):
    monotectic  T = 1968 K, conjugates x_SiO2 = 0.59 (MgO-rich) and 0.99 (silica-rich)
    consolute   T = 2244 K, critical  x_SiO2 = 0.84
So the real dome is WIDE but SHORT - it closes only 276 K above the monotectic. Our v0.5
excess (omega only) gives a dome that is wide but ~1000 K too TALL (consolute ~3175 K).
The height is set by the excess temperature-dependence (eta); a strong eta closes the dome
fast. With the consolute now a hard target, fit omega (gap width/composition) and eta (dome
height) together, in the Y_SiO2 basis (our Q-code (0,q) term = L*Y_SiO2^q, verified).

Excess (all Q-code on (Mg,Si,O,O), L = a + b*T):
    (0,0): a00 + b00*T      (0,1): a01 + b01*T      (0,5): a05 + b05*T
Targets: the 4 condensed invariants, both monotectic conjugates at 1968 K, the consolute
temperature (2244 K) and its composition (0.84), and the measured mixing enthalpy.
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
T_MONO, T_CONS, X_CONS = 1968.0, 2244.0, 0.84


def build_db(pp):
    a00, b00, a01, b01, a05, b05 = pp
    excess = [dict(code="Q", li=[1, 2, 3, 3], exp=[0, 0, 0, 0], coeffs=[a00, b00, 0, 0, 0, 0]),
              dict(code="Q", li=[1, 2, 3, 3], exp=[0, 1, 0, 0], coeffs=[a01, b01, 0, 0, 0, 0]),
              dict(code="Q", li=[1, 2, 3, 3], exp=[0, 5, 0, 0], coeffs=[a05, b05, 0, 0, 0, 0])]
    import os
    path = HERE / f"_v08_{os.getpid()}.dat"
    path.write_text(bd.build(excess, version="v0.8"), encoding="ascii")
    db = mqmqa.Database.read(str(path))
    return db, db.phase_index("MGO-SIO2-LIQUID"), excess


def dh_mix(db, p, x, T=2100.0, dT=40.0):
    g = lambda TT: act.delta_g_mix(eq.build_inputs(db, p, TT, components=COMP), x)
    return (g(T) - T * (g(T + dT) - g(T - dT)) / (2 * dT)) / 1000.0


def consolute(db, p, lo=1980.0, hi=3400.0):
    """Temperature at which the isolated-liquid binodal closes, and the critical
    composition just below it. Coarse scan then refine."""
    Tclose, xc = None, None
    T = lo
    last = vf.gap(db, p, lo)
    while T <= hi:
        g = vf.gap(db, p, T)
        if g is None:
            Tclose = T
            if last:
                xc = 0.5 * (last[0] + last[1])
            break
        last = g
        T += 40.0
    return Tclose, xc


def residuals(pp):
    db, p, _ = build_db(pp)
    r = vf.all_invariants(db, p)
    out = []
    for key, tgt in vf.TARGETS:
        v = r[key]
        out.append((v - tgt) / 100.0 if v else vf.PENALTY)
    gm = vf.gap(db, p, T_MONO)                 # monotectic conjugates (isolated binodal)
    if gm:
        out.append((gm[0] - 0.59) / 0.03)
        out.append((gm[1] - 0.99) / 0.03)
    else:
        out += [vf.PENALTY, vf.PENALTY]
    Tc, xc = consolute(db, p)                   # dome height + critical composition
    if Tc:
        out.append((Tc - T_CONS) / 60.0)
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
        print(f"  eval {n[0]:3d} cost={0.5*float(res@res):7.3f}  a00={pp[0]:8.0f} b00={pp[1]:+6.1f} "
              f"a01={pp[2]:9.0f} b01={pp[3]:+6.1f} a05={pp[4]:9.0f} b05={pp[5]:+6.1f}")
        return res
    sol = least_squares(fun, p0, diff_step=0.03, max_nfev=170,
                        x_scale=[1e5, 5.0, 1e5, 5e1, 5e5, 1e2])
    return sol.x


def report(pp, write=False):
    vf.RES = vf.FINE
    db, p, excess = build_db(pp)
    r = vf.all_invariants(db, p)
    print("\n  v0.8 model:")
    for name, key, tgt in [("forsterite", "forsterite", vf.T_FORST),
                           ("peri-forst eut", "peri_forst_eut", vf.T_PERI_FORST_EUT),
                           ("enstatite peri", "enst_peri", vf.T_ENST_PERI),
                           ("En-Crs eut", "encr_eut", vf.T_ENCR_EUT)]:
        v = r[key]
        print(f"    {name:16s} {v:6.0f} K  meas {tgt}  dT {v-tgt:+5.0f}" if v else f"    {name}: none")
    gm = vf.gap(db, p, T_MONO)
    Tc, xc = consolute(db, p)
    print(f"    monotectic gap@1968 {gm[0]:.3f}-{gm[1]:.3f}  (meas 0.59/0.99)" if gm else "    gap none")
    print(f"    consolute ~{Tc} K at x~{xc:.2f}  (meas 2244 K, 0.84)" if Tc else "    consolute: none")
    print(f"    dH_mix(1/3)={dh_mix(db,p,1/3.):+.1f} dH_mix(1/2)={dh_mix(db,p,0.5):+.1f} (MLIP {DH13}/{DH12})")
    if write:
        (HERE / "MgO-SiO2-liquid.dat").write_text(bd.build(excess, version="v0.8"), encoding="ascii")
        print("  wrote MgO-SiO2-liquid.dat")
    return r


if __name__ == "__main__":
    # start from the v0.5 model in the Y basis, with a moderate nonzero silica eta (b05)
    # so the dome starts partly lowered and the finite-difference gradient does not collapse.
    p0 = [-22445.0, -3.78, -88436.0, -5.0, 138675.0, -8.0]
    pp = fit(p0) if "--fit" in sys.argv else p0
    report(pp, write=("--write" in sys.argv))
    print("\n  params:", [round(float(x), 1) for x in pp])
