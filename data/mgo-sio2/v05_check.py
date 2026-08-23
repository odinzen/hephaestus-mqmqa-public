"""v0.5 diagnostics: is the fitted liquid physically reasonable, and where does the
FULL-diagram monotectic actually land? Decides whether the diagram match is legitimate
or an overfit that distorts the liquid away from the MLIP/calorimetry depth.
"""
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "python"))

import build_dat as bd
import mqmqa
from mqmqa import equilibrium as eq
import _activity as act
import phase_diagram as pdg
import v05_fit as v5

pdg.USE_COMPOUND_CP = True
COMPONENTS = pdg.COMPONENTS

V05 = [-161552.39, 13.686, 99868.22, 0.0, 143919.81]
V04 = [-79055.6, -3.5875, 30163.1, 0.0, 100958.1]


def dh_mix(db, p, x, T=2100.0, dT=40.0):
    """Liquid enthalpy of mixing per mole oxide unit: H = g - T dg/dT."""
    def g(TT):
        inp = eq.build_inputs(db, p, TT, components=COMPONENTS)
        return act.delta_g_mix(inp, x)
    return g(T) - T * (g(T + dT) - g(T - dT)) / (2 * dT)


def monotectic(db, p):
    """Full-diagram monotectic: highest T at which the two-liquid gap still exists as
    a stable feature below the cristobalite liquidus. We scan T and find where the gap
    (isolated binodal) is preempted by cristobalite - i.e. the cristobalite solid sits
    below the gap's left-conjugate liquid tangent. Report the gap-closing (consolute)
    and the cristobalite-preemption (true monotectic)."""
    # consolute: highest T the isolated binodal exists
    Tcons = None
    for T in np.arange(2000, 3400, 25.0):
        if v5.gap(db, p, float(T)) is None:
            Tcons = T
            break
    # true monotectic: highest T at which cristobalite is stable at the gap's right edge,
    # i.e. L1 + L2 + cristobalite three-phase. Approximate as the T where the cristobalite
    # solid G drops below the right-conjugate liquid G (cristobalite starts to preempt).
    Tmono = None
    for T in np.arange(2600, 1600, -20.0):
        gp = v5.gap(db, p, float(T))
        if gp is None:
            continue
        xr = gp[1]
        inp = eq.build_inputs(db, p, float(T), components=COMPONENTS)
        gL = pdg.liquid_gibbs_per_formula_unit(inp, xr, float(T))
        gC = pdg.solid_gibbs_per_formula_unit("SiO2(cristobalite)", float(T))[0]
        # cristobalite (x=1) preempts when its tangent undercuts the right conjugate;
        # crude proxy: cristobalite G per unit below the liquid at the right edge.
        if gC < gL:
            Tmono = T
            break
    return Tcons, Tmono


def main():
    for tag, pp in (("v0.4 (NK solids)", V04), ("v0.5 (Fix A+B)", V05)):
        # v0.4 depth must be read with NK solids off? No - dH_mix is a pure-liquid
        # quantity, independent of the solid model. Build with the given excess.
        db, p, _ = v5.build_db(pp)
        d13 = dh_mix(db, p, 1.0 / 3.0)
        d12 = dh_mix(db, p, 0.5)
        print(f"\n{tag}")
        print(f"  dH_mix(x=1/3) = {d13/1000:+6.1f}   dH_mix(x=1/2) = {d12/1000:+6.1f}  "
              f"kJ/mol-oxide   (v0.2 MLIP anchors: -24.5 / -22.4)")
        # gap dome
        print("  gap(T) isolated binodal:")
        for T in (1800, 1968, 2200, 2600, 3000):
            g = v5.gap(db, p, float(T))
            print(f"    {T} K: {f'{g[0]:.3f}-{g[1]:.3f}' if g else 'closed'}")
        Tcons, Tmono = monotectic(db, p)
        print(f"  consolute (isolated binodal closes) ~ {Tcons} K")
        print(f"  cristobalite-preemption proxy ~ {Tmono} K   (measured monotectic 1968)")


if __name__ == "__main__":
    main()
