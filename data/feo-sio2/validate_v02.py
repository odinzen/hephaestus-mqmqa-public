"""Validate the fitted FeO-SiO2 v0.2 liquid (the excess, not just the endmembers).

Loads the WRITTEN FeO-SiO2-liquid.dat (so the fitted excess round-trips through the .dat
and the C reader) and checks:
  1. fayalite Fe2SiO4 CONGRUENT melting reproduces ~1478 K (Bowen & Schairer 1932).
  2. the liquid enthalpy of mixing at x=1/3, 1/2 matches the bias-corrected MLIP anchors.
  3. delta_g_mix is negative and single-welled across the join (no spurious miscibility
     gap - a cation-mixing excess should not open one on the iron-silicate side).
  4. component activities show the expected negative deviation from ideality.

Endmember/structure checks are in validate.py; this covers the interior mixing.
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
import v02_fit as fit

DAT = HERE / "FeO-SiO2-liquid.dat"
COMPONENTS = pdg.COMPONENTS


def main():
    db = mqmqa.Database.read(str(DAT))
    p = db.phase_index("FEO-SIO2-LIQUID")

    # excess L(T) is already baked into the .dat; read it straight (no set_L needed)
    def congruent(name, x, lo=1100.0, hi=2000.0):
        def f(T):
            inp = eq.build_inputs(db, p, T, components=COMPONENTS)
            gs, _ = pdg.solid_gibbs_per_formula_unit(name, T)
            return pdg.liquid_gibbs_per_formula_unit(inp, x, T) - gs
        if f(lo) * f(hi) > 0:
            return None
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            (lo, hi) = (mid, hi) if f(lo) * f(mid) > 0 else (lo, mid)
        return 0.5 * (lo + hi)

    def dh_mix(x, T=1700.0, dT=50.0):
        def g(TT):
            inp = eq.build_inputs(db, p, TT, components=COMPONENTS)
            return act.delta_g_mix(inp, x)
        return g(T) - T * (g(T + dT) - g(T - dT)) / (2 * dT)

    print("1) fayalite congruent melting")
    Tc = congruent("Fa(fayalite)", 1.0 / 3.0)
    print(f"   T = {Tc:.0f} K   (measured 1478 K, Bowen & Schairer 1932)")

    print("\n2) liquid enthalpy of mixing [kJ/mol-oxide]")
    for x, lab in ((1.0 / 3.0, "fayalite x=1/3"), (0.5, "metasilicate x=1/2")):
        print(f"   {lab}:  dH_mix = {dh_mix(x)/1000:+.1f}")

    print("\n3) delta_g_mix across the join (negative, single-welled = no spurious gap)")
    T = 1700.0
    inp = eq.build_inputs(db, p, T, components=COMPONENTS)
    xs = np.linspace(0.1, 0.9, 9)
    gm = [act.delta_g_mix(inp, float(x)) / 1000 for x in xs]
    print("   x_SiO2: " + "  ".join(f"{x:.1f}" for x in xs))
    print("   dGmix : " + "  ".join(f"{g:+.1f}" for g in gm) + "  kJ/mol-ox")
    # spinodal check: second derivative of delta_g_mix on a fine grid (a spurious gap
    # shows as d2 << 0). The ideal part is strongly convex; only a large positive excess
    # could open a gap. Use a wide FD step so the exact-1D-solve noise averages out.
    xf = np.linspace(0.08, 0.92, 43)
    gf = np.array([act.delta_g_mix(inp, float(x)) for x in xf])
    h = xf[1] - xf[0]
    d2 = (gf[2:] - 2 * gf[1:-1] + gf[:-2]) / h ** 2
    print(f"   min d2(dGmix)/dx2 = {d2.min():.0f} J/mol  (RT/x(1-x) ideal floor ~ {8.3145*T/0.25:.0f})")
    print(f"   single-welled (no spinodal): {'PASS' if d2.min() > -50.0 else 'FAIL (gap!)'}")

    print("\n4) activities at 1700 K (liquid reference)")
    for x in (0.2, 0.4, 0.6):
        a_feo, a_sio2 = act.activities(inp, x, T)
        print(f"   x_SiO2={x:.1f}  a(FeO)={a_feo:.3f}  a(SiO2)={a_sio2:.3f}")


if __name__ == "__main__":
    main()
