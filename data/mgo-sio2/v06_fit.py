"""v0.6: add a temperature-dependent silica excess term to bring the two-liquid
monotectic down, refit simultaneously with everything v0.5 already matched.

v0.5 matched the four condensed invariants AND the measured liquid enthalpy, but left
the silica-rich two-liquid dome far too tall (consolute >3500 K), so cristobalite
preempted the silica liquid at ~2600 K vs the measured 1968 K monotectic. Direct tests
showed the dome height is set by the excess MAGNITUDE, not the coordination numbers
(composition-dependent Z does NOT lower it) - so the fix is a T-dependent silica term
L_si = a_si + b_si*T (b_si < 0), which weakens the silica-rich immiscibility as T rises
and pulls the dome down. This is a parameter, not an engine change.

Fit the five parameters (a00, b00, a10, a_si, b_si) simultaneously to: the four condensed
invariants, the MLIP/calorimetry dH_mix, the gap MgO-side conjugate (0.59), and a low
two-liquid dome (penalise the gap persisting above 2200 K).

CONCLUSION (v0.6 is NOT shipped): the T-dependent term lowers the monotectic from ~2600 K
to ~2180 K, but it plateaus ~200 K above the measured 1968 K and only gets there by
degrading the physically-anchored quantities - dH_mix(x=1/2) drifts -22.4 -> -14.1, the
periclase-forsterite eutectic to +55 K. Trading the measured enthalpy for the diagram is
the move rejected for the v0.5 liquid, so v0.5 is retained as the shipped model and this
script stands as the record of the monotectic study. The genuine fix is anion speciation
(a second/associate anion), a real engine extension, not this parameter crutch.
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
COMPONENTS = pdg.COMPONENTS
DH13, DH12 = -24.5, -22.4
T_DOME = 2200.0            # the gap should be closed by here (dome top near/below the data)


def build_db(pp):
    a00, b00, a10, a_si, b_si = pp
    excess = [dict(code="Q", li=[1, 2, 3, 3], exp=[0, 0, 0, 0],
                   coeffs=[a00, b00, 0, 0, 0, 0]),
              dict(code="Q", li=[1, 2, 3, 3], exp=[1, 0, 0, 0],
                   coeffs=[a10, 0, 0, 0, 0, 0]),
              dict(code="Q", li=[1, 2, 3, 3], exp=[0, vf.Q_SI, 0, 0],
                   coeffs=[a_si, b_si, 0, 0, 0, 0])]
    import os
    path = HERE / f"_v06_scaffold_{os.getpid()}.dat"
    path.write_text(bd.build(excess, version="v0.6"), encoding="ascii")
    db = mqmqa.Database.read(str(path))
    return db, db.phase_index("MGO-SIO2-LIQUID"), excess


def dh_mix(db, p, x, T=2100.0, dT=40.0):
    g = lambda TT: act.delta_g_mix(eq.build_inputs(db, p, TT, components=COMPONENTS), x)
    G = g(T); S = -(g(T + dT) - g(T - dT)) / (2 * dT)
    return (G + T * S) / 1000.0


def residuals(pp):
    db, p, _ = build_db(pp)
    r = vf.all_invariants(db, p)
    out = []
    for key, tgt in vf.TARGETS:
        v = r[key]
        out.append((v - tgt) / 100.0 if v else vf.PENALTY)
    gp = r["gap_mono"]
    out.append(((gp[0] - vf.X_GAP_MG) / 0.05) if gp else vf.PENALTY)
    out.append((dh_mix(db, p, 1.0 / 3.0) - DH13) / 10.0)
    out.append((dh_mix(db, p, 0.5) - DH12) / 10.0)
    # dome: the two-liquid gap should be closed by T_DOME; penalise its width if not
    gd = vf.gap(db, p, T_DOME)
    out.append((gd[1] - gd[0]) / 0.10 if gd else 0.0)
    return np.asarray(out, float)


def fit(p0, verbose=True):
    vf.RES = vf.FAST
    n = [0]
    def fun(pp):
        n[0] += 1
        res = residuals(pp)
        if verbose:
            print(f"  eval {n[0]:3d} cost={0.5*float(res@res):7.3f} a00={pp[0]:8.0f} "
                  f"b00={pp[1]:+6.2f} a10={pp[2]:7.0f} a_si={pp[3]:8.0f} b_si={pp[4]:+7.1f}")
        return res
    sol = least_squares(fun, p0, diff_step=0.03, max_nfev=140,
                        x_scale=[5e4, 5.0, 5e4, 1e5, 1e2])
    return sol.x


def monotectic(db, p):
    for T in np.arange(2600, 1600, -20.0):
        g = vf.gap(db, p, float(T))
        if g is None:
            continue
        inp = eq.build_inputs(db, p, float(T), components=COMPONENTS)
        gL = pdg.liquid_gibbs_per_formula_unit(inp, g[1], float(T))
        gC = pdg.solid_gibbs_per_formula_unit("SiO2(cristobalite)", float(T))[0]
        if gC < gL:
            return T
    return None


def report(pp):
    vf.RES = vf.FINE
    db, p, _ = build_db(pp)
    r = vf.all_invariants(db, p)
    rows = [("forsterite congruent", r["forsterite"], vf.T_FORST),
            ("periclase-forst eutectic", r["peri_forst_eut"], vf.T_PERI_FORST_EUT),
            ("enstatite peritectic", r["enst_peri"], vf.T_ENST_PERI),
            ("enstatite-crist eutectic", r["encr_eut"], vf.T_ENCR_EUT)]
    print("\n  v0.6 final model:")
    for name, v, tgt in rows:
        print(f"    {name:28s} {v:6.0f} K  meas {tgt:5.0f}  dT {v-tgt:+5.0f}" if v
              else f"    {name}: none")
    gp = r["gap_mono"]
    print(f"    silica gap @1968K            {gp[0]:.3f}-{gp[1]:.3f}" if gp else "    gap none")
    print(f"    two-liquid monotectic       ~{monotectic(db,p):.0f} K  meas 1968")
    print(f"    dH_mix(1/3)={dh_mix(db,p,1/3.):+.1f}  dH_mix(1/2)={dh_mix(db,p,0.5):+.1f}"
          f"  (MLIP {DH13}/{DH12})")
    return r


if __name__ == "__main__":
    # start from v0.5 params + a strong negative silica slope
    b0 = -200.0
    p0 = [-110881.48, -3.78, 88436.12, 138675.0 - b0 * 1968.0, b0]
    if "--fit" in sys.argv:
        pp = fit(p0)
        print("\n  fitted:", [round(float(x), 2) for x in pp])
    else:
        pp = p0
    report(pp)
