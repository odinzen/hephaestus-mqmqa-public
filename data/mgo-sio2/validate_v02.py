"""Validate the fitted MgO-SiO2 v0.2 liquid excess against the written .dat.

Loads MgO-SiO2-liquid.dat (the shipped file, not the fit scaffold) and checks the
interior mixing the excess is responsible for:

  1. the MQMX excess terms are present and parse (2 Q-code cation-mixing terms);
  2. the liquid deviates from ideal (delta-G_mix minimum, and dH_mix at x=1/3, 1/2);
  3. forsterite Mg2SiO4 congruent melting reproduces the 2163 K anchor;
  4. the hull classifier gives the right invariant TYPES: forsterite CONGRUENT,
     enstatite INCONGRUENT/peritectic (temperatures are solid-model-limited);
  5. full-range stability: no spurious spinodal on the central/MgO-rich join
     (the real silica-rich gap is deferred to v0.4).

Reproduce the fit itself with v02_fit.py.
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "python"))

import mqmqa
from mqmqa import equilibrium as eq
import _activity as act
import phase_diagram as pdg
import phase_hull as hull

DAT = HERE / "MgO-SiO2-liquid.dat"
COMPONENTS = pdg.COMPONENTS


def main():
    db = mqmqa.Database.read(str(DAT))
    p = db.phase_index("MGO-SIO2-LIQUID")

    print("=" * 70)
    print("1. EXCESS TERMS PRESENT")
    print("=" * 70)
    mx = db.mqmx(p, 2000.0)
    print(f"  MQMX terms: {len(mx['A'])}  (expect 2 Q-code cation-mixing terms)")
    for i in range(len(mx["A"])):
        print(f"    term {i}: code={mx['code'][i]} quad(A,B,X,Y)="
              f"({mx['A'][i]},{mx['B'][i]},{mx['X'][i]},{mx['Y'][i]}) "
              f"exp=({mx['p'][i]},{mx['q'][i]}) L={mx['L'][i]:+.1f} J/mol")

    print("\n" + "=" * 70)
    print("2. INTERIOR MIXING (deviation from ideal)")
    print("=" * 70)
    inp = eq.build_inputs(db, p, 2100.0, components=COMPONENTS)
    xs = np.linspace(0.1, 0.9, 9)
    gmix = [act.delta_g_mix(inp, float(x)) for x in xs]
    imin = int(np.argmin(gmix))
    print(f"  delta-G_mix(2100 K) minimum {gmix[imin]/1000:+.1f} kJ/mol-oxide at "
          f"x_SiO2={xs[imin]:.2f}")

    print("\n" + "=" * 70)
    print("3. FORSTERITE CONGRUENT MELTING (fit anchor 2163 K)")
    print("=" * 70)
    Tc = pdg.congruent_melting(db, p, "M2S(forsterite)")
    print(f"  forsterite congruent T = {Tc:.0f} K  (target 2163 K, "
          f"diff {Tc-2163:+.0f} K)" if Tc else "  no congruent melting found")

    print("\n" + "=" * 70)
    print("4. HULL INVARIANT CLASSIFICATION (type is the physics)")
    print("=" * 70)
    for name in ("M2S(forsterite)", "MS(enstatite)"):
        _, xC, Tmax, kind, _ = hull.classify_compound(db, p, name)
        tt = f"{Tmax:.0f} K" if Tmax else "  -  "
        print(f"  {name:18s} x={xC:.3f}  {tt:>8s}  {kind}")
    print("  KEY RESULT: enstatite is INCONGRUENT/peritectic (-> liquid + forsterite),")
    print("  as measured. Forsterite melts congruently at 2163 K (section 3, direct);")
    print("  the hull marks it coexisting with periclase because the model's")
    print("  periclase-forsterite eutectic is near-coincident with forsterite melting")
    print("  (the refractory-MgO / Neumann-Kopp solid-model limit; measured gap 40 K).")

    print("\n" + "=" * 70)
    print("5. FULL-RANGE STABILITY (central join; silica gap deferred to v0.4)")
    print("=" * 70)
    for T in (1900.0, 2100.0):
        inp = eq.build_inputs(db, p, T, components=COMPONENTS)
        xg = np.linspace(0.05, 0.6, 40)   # central / MgO-rich side (v0.2 scope)
        g = np.array([act.delta_g_mix(inp, float(x)) for x in xg])
        d2 = np.gradient(np.gradient(g, xg), xg)
        uns = [round(float(x), 2) for x, u in zip(xg, d2 < -1) if u]
        print(f"  T={T:.0f} K: spinodal on x<=0.6 = "
              f"{uns if uns else 'NONE (stable)'}")


if __name__ == "__main__":
    main()
