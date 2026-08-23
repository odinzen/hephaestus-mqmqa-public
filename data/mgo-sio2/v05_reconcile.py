"""The reconciliation test: can ONE liquid match the phase-diagram invariants AND the
independently-measured mixing enthalpy (MLIP + Charlu-Newton-Kleppa), instead of the
v0.5 fit's 2x-too-deep liquid?

Same engine, charge-proportional Z (which already places max short-range order at the
orthosilicate, per Pelton Part I: X_SiO2^maxSRO = Z_Mg/(Z_Mg+Z_Si) = 1/3 when Z_Si=2*Z_Mg).
Same Pelton-structured excess: Delta_g expanded in the quasichemical quadruplet fractions
(our chi = X_ii/(X_ii+X_ij+X_jj) IS Pelton's pair-fraction expansion Eq 17), a (0,0)
constant + a (1,0) MgO-side term + a (0,q) silica-side term. The ONLY change from v05_fit
is that dH_mix(x=1/3) and dH_mix(x=1/2) are now FIT TARGETS (toward the MLIP anchors),
not free. If the optimizer satisfies both the invariants and dH_mix, the tension is
resolved; if dH_mix cannot come down while the invariants stay matched, it is a real
model-form limit.
"""
import sys
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "python"))

import phase_diagram as pdg
import v05_fit as vf
from mqmqa import equilibrium as eq
import _activity as act

pdg.USE_COMPOUND_CP = False          # Neumann-Kopp solids (the better-matching choice)
COMPONENTS = pdg.COMPONENTS

# MLIP + calorimetry liquid mixing enthalpy anchors (v0.2 PROVENANCE)
DH13, DH12 = -24.5, -22.4


def dh_mix(db, p, x, T=2100.0, dT=40.0):
    g = lambda TT: act.delta_g_mix(eq.build_inputs(db, p, TT, components=COMPONENTS), x)
    G = g(T)
    S = -(g(T + dT) - g(T - dT)) / (2 * dT)
    return (G + T * S) / 1000.0


def residuals(q):
    a00, b00, a10, L_si = q
    pp = [a00, b00, a10, 0.0, L_si]
    db, p, _ = vf.build_db(pp)
    r = vf.all_invariants(db, p)
    out = []
    for key, tgt in vf.TARGETS:
        v = r[key]
        out.append((v - tgt) / 100.0 if v else vf.PENALTY)
    gp = r["gap_mono"]
    out.append(((gp[0] - vf.X_GAP_MG) / 0.05) if gp else vf.PENALTY)
    # NEW: the measured liquid enthalpy is now a target (weight ~ per 10 kJ)
    out.append((dh_mix(db, p, 1.0 / 3.0) - DH13) / 10.0)
    out.append((dh_mix(db, p, 0.5) - DH12) / 10.0)
    return np.asarray(out, float)


def run(p0, tag, dhw=1.0):
    vf.RES = vf.FAST
    n = [0]
    def fun(q):
        n[0] += 1
        res = residuals(q).copy()
        res[-2:] *= dhw                      # scale the dH weight
        c = 0.5 * float(res @ res)
        print(f"  {tag} eval {n[0]:3d} cost={c:7.3f} a00={q[0]:8.0f} b00={q[1]:+7.2f} "
              f"a10={q[2]:8.0f} Lsi={q[3]:8.0f}")
        return res
    sol = least_squares(fun, p0, diff_step=0.03, max_nfev=110,
                        x_scale=[5e4, 5.0, 5e4, 5e4])
    return sol.x


def report(q):
    pp = [q[0], q[1], q[2], 0.0, q[3]]
    vf.RES = vf.FINE
    db, p, _ = vf.build_db(pp)
    r = vf.all_invariants(db, p)
    print("\n  final model:")
    rows = [("forsterite congruent", r["forsterite"], vf.T_FORST),
            ("periclase-forst eutectic", r["peri_forst_eut"], vf.T_PERI_FORST_EUT),
            ("enstatite peritectic", r["enst_peri"], vf.T_ENST_PERI),
            ("enstatite-crist eutectic", r["encr_eut"], vf.T_ENCR_EUT)]
    for name, v, tgt in rows:
        print(f"    {name:28s} {v:6.0f} K  meas {tgt:5.0f}  dT {v-tgt:+5.0f}" if v
              else f"    {name}: none")
    gp = r["gap_mono"]
    print(f"    silica gap @1968K            {gp[0]:.3f}-{gp[1]:.3f}" if gp else "    gap: none")
    print(f"    dH_mix(1/3)={dh_mix(db,p,1/3.):+6.1f}  dH_mix(1/2)={dh_mix(db,p,0.5):+6.1f}"
          f"  kJ/mol-oxide  (MLIP {DH13}/{DH12})")
    return r


# the reconciled v0.5 optimum (reproduce by passing --fit; otherwise this is used to
# write the shipped database). g00 = a00 + b00*T, g10 = a10, g_si = L_si at q=5.
V05_PARAMS = [-110881.48, -3.78, 88436.12, 138675.18]


def write_dat(q):
    a00, b00, a10, L_si = q
    excess = [dict(code="Q", li=[1, 2, 3, 3], exp=[0, 0, 0, 0],
                   coeffs=[a00, b00, 0, 0, 0, 0]),
              dict(code="Q", li=[1, 2, 3, 3], exp=[1, 0, 0, 0],
                   coeffs=[a10, 0, 0, 0, 0, 0]),
              dict(code="Q", li=[1, 2, 3, 3], exp=[0, vf.Q_SI, 0, 0],
                   coeffs=[L_si, 0, 0, 0, 0, 0])]
    import build_dat as bd
    out = HERE / "MgO-SiO2-liquid.dat"
    out.write_text(bd.build(excess, version="v0.5"), encoding="ascii")
    return out


if __name__ == "__main__":
    if "--fit" in sys.argv:
        q = run([-128197.0, 21.39, 19480.0, 92928.0], "recon")
        print("\n  fitted params:", [round(float(x), 2) for x in q])
    else:
        q = V05_PARAMS
    report(q)
    if "--write" in sys.argv:
        print("\n  wrote", write_dat(q), "(v0.5 reconciled)")
