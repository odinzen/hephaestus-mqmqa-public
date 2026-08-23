"""v0.10: fit the STABLE two-liquid field (with cristobalite in the hull), not the
isolated binodal. The isolated binodal closes at the right height, but cristobalite
preempts most of it (the long cristobalite -> MgO-rich-liquid tie-line), leaving a thin
stable sliver. The physically meaningful targets are the STABLE monotectic (1968 K, where
cristobalite cuts in) and the STABLE consolute (2240 K), with the stable conjugates.

Start from v0.9 (which already has a thin stable field, so the optimizer begins where the
stable dome EXISTS and the objective is differentiable). 8 params: (0,0),(0,1),(0,3),(0,7).
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
T_MONO, T_CONS = 1968.0, 2240.0
X_ML, X_SL = 0.62, 0.98            # stable conjugates at the monotectic (data range 0.60-0.66 / ~0.99)


def build_db(pp):
    a00, b00, a01, b01, a03, b03, a07, b07 = pp
    excess = [dict(code="Q", li=[1, 2, 3, 3], exp=[0, 0, 0, 0], coeffs=[a00, b00, 0, 0, 0, 0]),
              dict(code="Q", li=[1, 2, 3, 3], exp=[0, 1, 0, 0], coeffs=[a01, b01, 0, 0, 0, 0]),
              dict(code="Q", li=[1, 2, 3, 3], exp=[0, 3, 0, 0], coeffs=[a03, b03, 0, 0, 0, 0]),
              dict(code="Q", li=[1, 2, 3, 3], exp=[0, 7, 0, 0], coeffs=[a07, b07, 0, 0, 0, 0])]
    import os
    path = HERE / f"_v10_{os.getpid()}.dat"
    path.write_text(bd.build(excess, version="v0.10"), encoding="ascii")
    db = mqmqa.Database.read(str(path))
    return db, db.phase_index("MGO-SIO2-LIQUID"), excess


def dh_mix(db, p, x, T=2100.0, dT=40.0):
    g = lambda TT: act.delta_g_mix(eq.build_inputs(db, p, TT, components=COMP), x)
    return (g(T) - T * (g(T + dT) - g(T - dT)) / (2 * dT)) / 1000.0


def _stable_LL(db, p, T, nx=170):
    """Stable two-liquid segment on the silica side at T (hull with cristobalite), or None."""
    xs = np.linspace(0.40, 0.999, nx)
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
    for i in range(len(H) - 1):
        if H[i+1][0] - H[i][0] > 0.05 and H[i][0] > 0.45 and H[i][2] == "L" and H[i+1][2] == "L":
            return (H[i][0], H[i+1][0])
    return None


def stable_dome(db, p):
    """(monotectic T, consolute T, conjugates at monotectic) of the STABLE L-L field."""
    lo = hi = conj = None
    for T in np.arange(1880.0, 2440.0, 20.0):
        s = _stable_LL(db, p, T)
        if s:
            if lo is None:
                lo, conj = T, s
            hi = T
    return lo, hi, conj


def residuals(pp):
    db, p, _ = build_db(pp)
    r = vf.all_invariants(db, p)
    out = []
    for key, tgt in vf.TARGETS:
        v = r[key]
        out.append((v - tgt) / 100.0 if v else vf.PENALTY)
    lo, hi, conj = stable_dome(db, p)
    if lo and hi and conj:
        out.append((lo - T_MONO) / 60.0)
        out.append((hi - T_CONS) / 60.0)
        out.append((conj[0] - X_ML) / 0.04)
        out.append((conj[1] - X_SL) / 0.04)
    else:
        out += [vf.PENALTY, vf.PENALTY, vf.PENALTY, vf.PENALTY]
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
    sol = least_squares(fun, p0, diff_step=0.03, max_nfev=200,
                        x_scale=[1e5, 5, 1e5, 5e1, 3e5, 1e2, 6e5, 1e2])
    return sol.x


def report(pp, write=False):
    vf.RES = vf.FINE
    db, p, excess = build_db(pp)
    r = vf.all_invariants(db, p)
    print("\n  v0.10 model:")
    for name, key, tgt in [("forsterite", "forsterite", vf.T_FORST),
                           ("peri-forst eut", "peri_forst_eut", vf.T_PERI_FORST_EUT),
                           ("enstatite peri", "enst_peri", vf.T_ENST_PERI),
                           ("En-Crs eut", "encr_eut", vf.T_ENCR_EUT)]:
        v = r[key]
        print(f"    {name:16s} {v:6.0f} K  meas {tgt}  dT {v-tgt:+5.0f}" if v else f"    {name}: none")
    lo, hi, conj = stable_dome(db, p)
    if lo:
        print(f"    STABLE two-liquid {int(lo)}-{int(hi)} K  (meas monotectic 1968, consolute 2240)")
        print(f"    conjugates @monotectic {conj[0]:.3f}-{conj[1]:.3f}  (meas ~0.62/0.98)")
    else:
        print("    STABLE two-liquid: none (fully preempted)")
    print(f"    dH_mix(1/3)={dh_mix(db,p,1/3.):+.1f} dH_mix(1/2)={dh_mix(db,p,0.5):+.1f} (MLIP {DH13}/{DH12})")
    if write:
        (HERE / "MgO-SiO2-liquid.dat").write_text(bd.build(excess, version="v0.10"), encoding="ascii")
        print("  wrote MgO-SiO2-liquid.dat")
    return r


if __name__ == "__main__":
    p0 = [-24081.3, -10.1, -73231.4, 1.7, -12890.4, 40.9, 167434.1, -62.7]  # v0.9 result
    pp = fit(p0) if "--fit" in sys.argv else p0
    report(pp, write=("--write" in sys.argv))
    print("\n  params:", [round(float(x), 1) for x in pp])
