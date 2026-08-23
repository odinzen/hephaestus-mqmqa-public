"""v0.7: reproduce the silica-rich monotectic using the published term structure.

Our Q-code excess variable was verified to equal the equivalent fraction Y_SiO2 = 2x/(1+x)
exactly (the same variable the 1993 Wu/Eriksson/Pelton/Blander MgO-SiO2 optimization uses),
so NO engine change is needed - only the right term structure. A Q-code (0,q) term equals
L * Y_SiO2^q; a (1,0) term equals L * (1-Y). We drop the old (1,0) skew and use pure
Y-power terms so omega(Y) and eta(Y) match the paper's polynomials:

    Delta_g = omega(Y) - eta(Y)*T,   with each term L = a + b*T on (0,q):
      omega(Y) = a00 + a01*Y + a07*Y^7        (const + linear ordering + high-power silica)
      eta(Y)   = -(b00 + b01*Y + b07*Y^7)     (large positive eta on the silica side lowers
                                                the two-liquid dome without touching omega)

omega negative at low/mid Y gives the ordering (deep enthalpy at the orthosilicate Y=1/2);
omega swinging positive near the silica corner (the +a07*Y^7 term) gives the immiscibility;
the eta terms (b, i.e. the T-dependence) pull the dome temperature down. This is exactly
the published device. Fit all six coefficients to the invariants + both gap conjugates +
a low dome + the measured mixing enthalpy.

VERIFIED HERE: our Q-code (0,q) excess variable EQUALS the equivalent fraction Y_SiO2 =
2x/(1+x) to machine precision, so this is the paper's exact variable and NO engine change is
needed. CONCLUSION: the monotectic is a coefficient-fitting limit, not a model-form one. With a
single common-anion liquid a WIDE gap (0.59-0.99) needs a strong positive silica excess, which
near pure silica (vanishing ideal entropy) is stable to very high T, so the whole two-liquid
region floats at ~2425-3175 K; the eta term narrows/collapses the gap rather than sliding it
down, and higher powers push the right conjugate to 0.999 without lowering the monotectic.
Threading a wide gap onto a low (1968 K) monotectic needs the published expert-fitted
omega(Y)/eta(Y) coefficients (the moat), which we do not copy. v0.5 is retained as the model.
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
T_DOME = 2100.0


def build_db(pp):
    a00, b00, a01, b01, a05, b05 = pp
    excess = [dict(code="Q", li=[1, 2, 3, 3], exp=[0, 0, 0, 0], coeffs=[a00, b00, 0, 0, 0, 0]),
              dict(code="Q", li=[1, 2, 3, 3], exp=[0, 1, 0, 0], coeffs=[a01, b01, 0, 0, 0, 0]),
              dict(code="Q", li=[1, 2, 3, 3], exp=[0, 5, 0, 0], coeffs=[a05, b05, 0, 0, 0, 0])]
    import os
    path = HERE / f"_v07_{os.getpid()}.dat"
    path.write_text(bd.build(excess, version="v0.7"), encoding="ascii")
    db = mqmqa.Database.read(str(path))
    return db, db.phase_index("MGO-SIO2-LIQUID"), excess


def dh_mix(db, p, x, T=2100.0, dT=40.0):
    g = lambda TT: act.delta_g_mix(eq.build_inputs(db, p, TT, components=COMP), x)
    return (g(T) - T * (g(T + dT) - g(T - dT)) / (2 * dT)) / 1000.0


def residuals(pp):
    db, p, _ = build_db(pp)
    r = vf.all_invariants(db, p)
    out = []
    for key, tgt in vf.TARGETS:
        v = r[key]
        out.append((v - tgt) / 100.0 if v else vf.PENALTY)
    gp = r["gap_mono"]
    if gp:
        out.append((gp[0] - 0.59) / 0.03)
        out.append((gp[1] - 0.99) / 0.03)
    else:
        out += [vf.PENALTY, vf.PENALTY]
    out.append((dh_mix(db, p, 1 / 3.) - DH13) / 5.0)
    out.append((dh_mix(db, p, 0.5) - DH12) / 6.0)
    gd = vf.gap(db, p, T_DOME)
    out.append((gd[1] - gd[0]) / 0.06 if gd else 0.0)
    return np.asarray(out, float)


def fit(p0):
    vf.RES = vf.FAST
    n = [0]
    def fun(pp):
        n[0] += 1
        res = residuals(pp)
        print(f"  eval {n[0]:3d} cost={0.5*float(res@res):7.3f}  a00={pp[0]:8.0f} b00={pp[1]:+6.1f} "
              f"a01={pp[2]:9.0f} b01={pp[3]:+6.1f} a07={pp[4]:9.0f} b07={pp[5]:+6.1f}")
        return res
    sol = least_squares(fun, p0, diff_step=0.03, max_nfev=160,
                        x_scale=[1e5, 5.0, 1e5, 5e1, 5e5, 1e2])
    return sol.x


def monotectic(db, p):
    prev = None
    for T in np.arange(2600, 1700, -25.0):
        xs = np.linspace(0.40, 0.999, 200)
        inp = eq.build_inputs(db, p, float(T), components=COMP)
        pts = [(float(x), pdg.liquid_gibbs_per_formula_unit(inp, float(x), float(T)), "L") for x in xs]
        pts.append((1.0, pdg.solid_gibbs_per_formula_unit("SiO2(cristobalite)", float(T))[0], "C"))
        pts = sorted(pts); H = []
        for x, g, lab in pts:
            while len(H) >= 2:
                (x1, g1, _), (x2, g2, _) = H[-2], H[-1]
                if (x2 - x1) * (g - g1) - (g2 - g1) * (x - x1) <= 1e-6: H.pop()
                else: break
            H.append((x, g, lab))
        has_LL = any(H[i+1][0]-H[i][0] > 0.05 and H[i][0] > 0.45 and H[i][2] == "L" and H[i+1][2] == "L"
                     for i in range(len(H)-1))
        if prev is True and not has_LL:
            return T + 12.5
        prev = has_LL
    return None


def report(pp, write=False):
    vf.RES = vf.FINE
    db, p, excess = build_db(pp)
    r = vf.all_invariants(db, p)
    print("\n  v0.7 model:")
    for name, key, tgt in [("forsterite", "forsterite", vf.T_FORST),
                           ("peri-forst eut", "peri_forst_eut", vf.T_PERI_FORST_EUT),
                           ("enstatite peri", "enst_peri", vf.T_ENST_PERI),
                           ("En-Crs eut", "encr_eut", vf.T_ENCR_EUT)]:
        v = r[key]
        print(f"    {name:16s} {v:6.0f} K  meas {tgt}  dT {v-tgt:+5.0f}" if v else f"    {name}: none")
    gp = r["gap_mono"]
    print(f"    gap@1968 {gp[0]:.3f}-{gp[1]:.3f}" if gp else "    gap none")
    mono = monotectic(db, p)
    print(f"    monotectic ~{mono} K  (meas 1968)")
    print(f"    dH_mix(1/3)={dh_mix(db,p,1/3.):+.1f} dH_mix(1/2)={dh_mix(db,p,0.5):+.1f} (MLIP {DH13}/{DH12})")
    if write:
        out = HERE / "MgO-SiO2-liquid.dat"
        out.write_text(bd.build(excess, version="v0.7"), encoding="ascii")
        print("  wrote", out)
    return r


if __name__ == "__main__":
    # start = the EXACT v0.5 model rewritten in the Y basis: v0.5 was
    # g00=-110881-3.78T (0,0) + g10=+88436 (1,0). Since (1,0)=L*(1-Y)=L - L*Y, that is
    # (0,0): -110881+88436 = -22445 (-3.78T), plus (0,1): -88436, plus (0,5): +138675.
    # b05/b01 start NONZERO (a large positive silica eta already) so the finite-difference
    # gradient does not collapse at a zero start; the fit refines from a partly-lowered dome.
    p0 = [-22445.0, -3.78, -88436.0, -10.0, 138675.0, -150.0]
    pp = fit(p0) if "--fit" in sys.argv else p0
    report(pp, write=("--write" in sys.argv))
    print("\n  params:", [round(float(x), 1) for x in pp])
