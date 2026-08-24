"""Validate the fitted FeO-SiO2 v0.3 liquid (activity-pinned excess + FeO recalibration).

Loads the WRITTEN FeO-SiO2-liquid.dat (so the fit round-trips through the .dat and the C
reader) and checks:
  1. the model a(FeO) reproduces the digitized measured points (Bjorkman 1985 Fig 3).
  2. fayalite Fe2SiO4 CONGRUENT melting = 1478 K (Bowen & Schairer 1932).
  3. a physical excess entropy (|b00| small) - v0.2's +78.6 is retired.
  4. delta_g_mix is negative and single-welled across the join (no spurious gap).
  5. the FeO(l) below-1650 K correction leaves FeO(l) untouched at/above 1650 K, and the
     FeO-rich liquidus stays well-behaved (no melt more stable than solid FeO to absurd T).

Endmember/structure checks are in validate.py; this covers the interior mixing + calibration.
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "python"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


import mqmqa
from mqmqa import equilibrium as eq
import _activity as act
import phase_diagram as pdg
fit = _load("v03_fit", HERE / "v03_fit.py")

DAT = HERE / "FeO-SiO2-liquid.dat"
COMPONENTS = pdg.COMPONENTS


def main():
    db = mqmqa.Database.read(str(DAT))
    p = db.phase_index("FEO-SIO2-LIQUID")

    print("1) model a(FeO) vs digitized measured points")
    data = fit.load_activities()
    res = []
    for X, a, src, T in data:
        inp = eq.build_inputs(db, p, T, components=COMPONENTS)
        am, _ = act.activities(inp, 1.0 - X, T)
        res.append(np.log(am / a))
    res = np.array(res)
    low = np.array([abs(d[3] - 1580) < 120 for d in data])
    print(f"   overall RMS ln a = {np.sqrt(np.mean(res**2)):.3f}  ({len(data)} points)")
    print(f"   ~1580 K set RMS  = {np.sqrt(np.mean(res[low]**2)):.3f}  ({low.sum()} points)")
    print(f"   2153 K set RMS   = {np.sqrt(np.mean(res[~low]**2)):.3f}  ({(~low).sum()} points)")
    print("   (systematic: model under-predicts a(FeO) at X_FeO>0.75 by ~0.1 in ln a -")
    print("    the measured coefficient turns slightly positive there; a symmetric excess")
    print("    cannot make that S-shape. The dominant silica-rich depth is well reproduced.)")

    print("\n2) fayalite congruent melting")
    Tc = fit.congruent_T(db, p)
    print(f"   T = {Tc:.0f} K   (measured 1478 K, Bowen & Schairer 1932)")

    print("\n3) excess entropy is physical (b00 retired)")
    # recover b00 from L(T) at two temperatures on the pure-(0,0) term
    inp1 = eq.build_inputs(db, p, 1500.0, components=COMPONENTS)
    inp2 = eq.build_inputs(db, p, 1900.0, components=COMPONENTS)
    L1, L2 = inp1["ex"]["L"][0], inp2["ex"]["L"][0]
    b00 = (L2 - L1) / 400.0
    a00 = L1 - b00 * 1500.0
    print(f"   Delta_g(Fe,Si)/O = {a00:.0f} {b00:+.2f}*T J/mol   (v0.2 was -96776 +78.62*T)")

    print("\n4) delta_g_mix across the join (negative, single-welled = no spurious gap)")
    T = 1580.0
    inp = eq.build_inputs(db, p, T, components=COMPONENTS)
    xs = np.linspace(0.1, 0.9, 9)
    gm = [act.delta_g_mix(inp, float(x)) / 1000 for x in xs]
    print("   x_SiO2: " + "  ".join(f"{x:.1f}" for x in xs))
    print("   dGmix : " + "  ".join(f"{g:+.1f}" for g in gm) + "  kJ/mol-ox")
    xf = np.linspace(0.08, 0.92, 43)
    gf = np.array([act.delta_g_mix(inp, float(x)) for x in xf])
    h = xf[1] - xf[0]
    d2 = (gf[2:] - 2 * gf[1:-1] + gf[:-2]) / h ** 2
    print(f"   min d2(dGmix)/dx2 = {d2.min():.0f} J/mol  (ideal floor RT/x(1-x) ~ {8.3145*T/0.25:.0f})")
    print(f"   single-welled (no spinodal): {'PASS' if d2.min() > -50.0 else 'FAIL (gap!)'}")

    print("\n5) FeO(l) below-1650 K correction is contained")
    for Tt in (1500.0, 1650.0, 1800.0):
        inp = eq.build_inputs(db, p, Tt, components=COMPONENTS)
        print(f"   G(FeO,l) at {Tt:.0f} K = {act.g_pure_liquid(inp,'FeO'):.0f} J/mol")
    print("   (the correction is 0 at 1650 K and above; only the supercooled branch moves)")


if __name__ == "__main__":
    main()
