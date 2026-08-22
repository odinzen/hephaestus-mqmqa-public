"""v0.4 exploration: what actually places the MgO-SiO2 silica-rich miscibility gap?

v0.2 established that a charge-proportional-Z cation-mixing excess cannot put the
liquid-liquid gap at the silica corner (Greig 1927: conjugate liquids x_SiO2 ~ 0.59
and ~0.99, monotectic 1968 K). This maps which model handle does place it.

CONCLUSION (refuting the earlier "SiO2-specific coordination" hypothesis):
  - Under a single O anion, the pure SiO2 quadruplet Z is locked by stoichiometry to
    Z_Si = 2*Z_O; scaling that quad's (Z_Si, Z_O, zeta) together is a GAUGE no-op - the
    endmember AND the ideal delta_g_mix are exactly invariant. The pair zeta_SiO2 alone
    is likewise a no-op. So coordination creates NO asymmetry here (sections 1-2).
  - With a fixed positive excess, coordination reshapes the gap but only MgO-ward
    (scaling Z_Si up), never toward silica (section 3). Coordination is not the lever.
  - The lever is a SILICA-WEIGHTED EXCESS: a Q-code (0,q) term (chi_Si^q), L > 0, whose
    spinodal silica edge marches outward with q ((0,3)->0.81, (0,5)->0.89, (0,6)->0.92)
    (sections 4-5). This is what v04_fit.py uses.

No proprietary parameters: the excess is our own fit to the open Greig gap, on the
published MQMQA framework (Pelton-Chartrand-Eriksson 2001).
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
import validate as val

COMPONENTS = ["MG", "SI", "O"]


def build_db(z_si=None, z_o_si=None, zeta_si=None, excess=None):
    path = HERE / "_v04_scaffold.dat"
    path.write_text(bd.build(excess, z_si=z_si, z_o_si=z_o_si, zeta_si=zeta_si),
                    encoding="ascii")
    db = mqmqa.Database.read(str(path))
    return db, db.phase_index("MGO-SIO2-LIQUID")


def pure_integrity(db, p, T=2000.0):
    """Pure SiO2 quad: G/formula vs endmember, and the O:Si element ratio (must be 2)."""
    inp = eq.build_inputs(db, p, T, components=COMPONENTS)
    i = inp["quads"].index((1, 1, 0, 0))
    X = np.zeros(len(inp["quads"])); X[i] = 1.0
    g_quad = eq.gibbs_per_quad(inp, X)
    els = eq.element_moles(inp, X)
    g_per_formula = g_quad / els["SI"]
    g_ref = val.liquid_gibbs(bd.OXIDES["SiO2"], T)
    o_si = els["O"] / els["SI"]
    return abs(g_per_formula - g_ref), o_si


def gmix_curve(db, p, T, L=None, xlo=0.05, xhi=0.98, n=80):
    inp = eq.build_inputs(db, p, T, components=COMPONENTS)
    if L is not None:
        act.set_excess_L(inp, L)
    xs = np.linspace(xlo, xhi, n)
    g = np.array([act.delta_g_mix(inp, float(x)) for x in xs])
    d2 = np.gradient(np.gradient(g, xs), xs)
    uns = [round(float(x), 3) for x, u in zip(xs, d2 < 0) if u]
    return xs, g, uns


def main():
    print("=" * 74)
    print("1. INTEGRITY vs zeta_SiO2 (pure SiO2: G/formula error, O:Si ratio must be 2)")
    print("=" * 74)
    for zs in (1.3774438, 1.8, 2.4, 3.0, 4.0):
        db, p = build_db(zeta_si=zs)
        dG, o_si = pure_integrity(db, p)
        print(f"  zeta_SiO2={zs:.3f}: |dG SiO2/formula|={dG:.2e} J/mol   O:Si={o_si:.4f}")

    print("\n" + "=" * 74)
    print("2. IDEAL (no excess) delta_g_mix + spinodal vs zeta_SiO2, 1968 K")
    print("=" * 74)
    print("   (does a SiO2-specific zeta ALONE open a silica-rich gap, and where?)")
    for zs in (1.3774438, 1.8, 2.2, 2.75, 3.5, 4.5, 6.0):
        db, p = build_db(zeta_si=zs)
        xs, g, uns = gmix_curve(db, p, 1968.0)
        imin = int(np.argmin(g))
        span = f"{min(uns):.2f}-{max(uns):.2f}" if uns else "none"
        print(f"  zeta={zs:5.2f}: dGmix min {g[imin]/1000:+6.1f} kJ at x={xs[imin]:.2f}   "
              f"spinodal(x): {span}")

    print("\n" + "=" * 74)
    print("3. EXCESS + COORDINATION: does Z reshape where a POSITIVE excess opens a gap?")
    print("=" * 74)
    print("   Fixed symmetric positive excess L=[+50000,0]; scan SiO2 Z scale f")
    print("   (z_si=2.7549*f, z_o_si=1.3774*f, ratio 2 kept). The excess chi uses Z, so")
    print("   even the 'gauge' Z direction should now move the gap.")
    Lpos = [50000.0, 0.0]
    onepar = [dict(code="Q", li=[1, 2, 3, 3], exp=[0, 0, 0, 0], coeffs=[0.0]*6)]
    for f in (0.3, 0.5, 0.7, 1.0, 1.5, 3.0):
        db, p = build_db(z_si=2.7548876 * f, z_o_si=1.3774438 * f, excess=onepar)
        xs, g, uns = gmix_curve(db, p, 1968.0, L=Lpos)
        span = f"{min(uns):.2f}-{max(uns):.2f}" if uns else "none"
        print(f"  f={f:4.1f}: spinodal(x): {span}")

    print("\n" + "=" * 74)
    print("4. SILICA-WEIGHTED EXCESS (charge-prop Z): can chi_Si^q reach the corner?")
    print("=" * 74)
    print("   single (0,q) term, scan magnitude; where is the spinodal + its silica edge?")
    for q in (1, 2, 3):
        for L in (100000.0, 200000.0, 400000.0):
            db, p = build_db(excess=[
                dict(code="Q", li=[1, 2, 3, 3], exp=[0, q, 0, 0], coeffs=[0.0]*6)])
            xs, g, uns = gmix_curve(db, p, 1968.0, L=[L])
            span = f"{min(uns):.2f}-{max(uns):.2f}" if uns else "none"
            print(f"  (0,{q}) L=+{L/1000:.0f}k: spinodal(x): {span}")

    print("\n" + "=" * 74)
    print("5. COMBINED: MgO-rich-suppressing skew + silica-weighted positive (best reach)")
    print("=" * 74)
    print("   two terms: g00 (symmetric) + (0,q) silica-weighted; hunt max silica edge")
    twopar = [dict(code="Q", li=[1, 2, 3, 3], exp=[0, 0, 0, 0], coeffs=[0.0]*6),
              dict(code="Q", li=[1, 2, 3, 3], exp=[0, 2, 0, 0], coeffs=[0.0]*6)]
    for L in ([-40000.0, 300000.0], [-60000.0, 400000.0], [-80000.0, 600000.0]):
        db, p = build_db(excess=twopar)
        xs, g, uns = gmix_curve(db, p, 1968.0, L=L)
        span = f"{min(uns):.2f}-{max(uns):.2f}" if uns else "none"
        print(f"  L={L}: spinodal(x): {span}")


if __name__ == "__main__":
    main()
