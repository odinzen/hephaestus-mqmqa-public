"""Decisive test before any engine change: can a RICHER single-anion excess reconcile
the monotectic AND the measured enthalpy AND the invariants? FactSage's MgO-SiO2 model
is single-anion, so if it matches the monotectic, a richer excess here should too.

Excess: g00(a+bT) + g10*chi_Mg + silica side [ (a2+b2 T) chi_Si^2 + (a5+b5 T) chi_Si^5 ].
The two silica terms (broad q=2 + sharp q=5, each T-dependent) give the shape freedom to
try for a LOW, WIDE two-liquid dome (monotectic ~1968, conjugates 0.59/0.99) without
deepening the x=1/2 enthalpy. Targets: 4 invariants, both gap conjugates at 1968, gap
CLOSED by 2100 K (low dome), and dH_mix(1/3,1/2) at the MLIP anchors.

If this converges with low residual, no engine change is needed. If it cannot bring the
dome down without wrecking the enthalpy or the conjugates, that is strong evidence the
single-anion model form is the limit and a structural change is genuinely required.
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
    a00, b00, a10, a2, b2, a5, b5 = pp
    excess = [dict(code="Q", li=[1, 2, 3, 3], exp=[0, 0, 0, 0], coeffs=[a00, b00, 0, 0, 0, 0]),
              dict(code="Q", li=[1, 2, 3, 3], exp=[1, 0, 0, 0], coeffs=[a10, 0, 0, 0, 0, 0]),
              dict(code="Q", li=[1, 2, 3, 3], exp=[0, 2, 0, 0], coeffs=[a2, b2, 0, 0, 0, 0]),
              dict(code="Q", li=[1, 2, 3, 3], exp=[0, 5, 0, 0], coeffs=[a5, b5, 0, 0, 0, 0])]
    import os
    path = HERE / f"_v06r_{os.getpid()}.dat"
    path.write_text(bd.build(excess, version="v0.6r"), encoding="ascii")
    db = mqmqa.Database.read(str(path))
    return db, db.phase_index("MGO-SIO2-LIQUID")


def dh_mix(db, p, x, T=2100.0, dT=40.0):
    g = lambda TT: act.delta_g_mix(eq.build_inputs(db, p, TT, components=COMP), x)
    return (g(T) - T * (g(T + dT) - g(T - dT)) / (2 * dT)) / 1000.0


def residuals(pp):
    db, p = build_db(pp)
    r = vf.all_invariants(db, p)
    out = []
    for key, tgt in vf.TARGETS:
        v = r[key]
        out.append((v - tgt) / 100.0 if v else vf.PENALTY)
    gp = r["gap_mono"]                                   # gap at 1968 K
    if gp:
        out.append((gp[0] - 0.59) / 0.04)
        out.append((gp[1] - 0.99) / 0.04)
    else:
        out += [vf.PENALTY, vf.PENALTY]
    out.append((dh_mix(db, p, 1 / 3.) - DH13) / 8.0)
    out.append((dh_mix(db, p, 0.5) - DH12) / 8.0)
    gd = vf.gap(db, p, T_DOME)                           # dome should be closed by 2100 K
    out.append((gd[1] - gd[0]) / 0.08 if gd else 0.0)
    return np.asarray(out, float)


def fit(p0):
    vf.RES = vf.FAST
    n = [0]
    def fun(pp):
        n[0] += 1
        res = residuals(pp)
        print(f"  eval {n[0]:3d} cost={0.5*float(res@res):7.3f}  "
              + " ".join(f"{v:8.0f}" for v in pp))
        return res
    sol = least_squares(fun, p0, diff_step=0.03, max_nfev=180,
                        x_scale=[5e4, 5.0, 5e4, 1e5, 1e2, 1e5, 1e2])
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
        wide = [(H[i][0], H[i+1][0], H[i][2], H[i+1][2]) for i in range(len(H)-1)
                if H[i+1][0]-H[i][0] > 0.05 and H[i][0] > 0.45]
        has_LL = any(l == "L" and r == "L" for _, _, l, r in wide)
        if prev is True and not has_LL:
            return T + 12.5
        prev = has_LL
    return None


def report(pp):
    vf.RES = vf.FINE
    db, p = build_db(pp)
    r = vf.all_invariants(db, p)
    print("\n  richer-excess final model:")
    for name, key, tgt in [("forsterite", "forsterite", vf.T_FORST),
                           ("peri-forst eut", "peri_forst_eut", vf.T_PERI_FORST_EUT),
                           ("enstatite peri", "enst_peri", vf.T_ENST_PERI),
                           ("En-Crs eut", "encr_eut", vf.T_ENCR_EUT)]:
        v = r[key]
        print(f"    {name:16s} {v:6.0f} K  meas {tgt}  dT {v-tgt:+5.0f}" if v else f"    {name}: none")
    gp = r["gap_mono"]
    print(f"    gap@1968 {gp[0]:.3f}-{gp[1]:.3f}" if gp else "    gap none")
    print(f"    monotectic ~{monotectic(db,p)} K  (meas 1968)")
    print(f"    dH_mix(1/3)={dh_mix(db,p,1/3.):+.1f} dH_mix(1/2)={dh_mix(db,p,0.5):+.1f} (MLIP {DH13}/{DH12})")


if __name__ == "__main__":
    p0 = [-110881.0, -3.78, 88436.0, 40000.0, -20.0, 400000.0, -150.0]
    pp = fit(p0) if "--fit" in sys.argv else p0
    report(pp)
    print("\n  params:", [round(float(x), 1) for x in pp])
