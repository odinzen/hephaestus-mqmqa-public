"""v0.4 fit: MgO-SiO2 liquid with the silica-rich miscibility gap.

The v0.2 model (central negative-deviation excess) cannot make the silica-rich
liquid-liquid gap (Greig 1927: conjugate liquids x_SiO2 ~ 0.59 and ~0.99, monotectic
1968 K). v0.4 adds the model-form term that places it.

WHAT THE LEVER ACTUALLY IS (mapped in v04_explore.py, correcting the earlier
coordination hypothesis):

  - SiO2-specific coordination Z / zeta is a GAUGE no-op for the ideal single-anion
    (Mg,Si/O) mixing - it creates no asymmetry by itself. Scaling the SiO2 quad Z only
    ever moves an EXCESS-driven gap toward the MgO corner, never toward silica. So
    "non-charge-proportional Z places the silica gap" is FALSE for this binary.
  - The lever that reaches the silica corner is a SILICA-WEIGHTED EXCESS: a Q-code term
    on (Mg,Si,O,O) with exponent q on chi_Si (the (0,q) term).
    A single (0,q) term, L>0, opens a spinodal whose silica edge marches outward with q
    ((0,3)->0.81, (0,5)->0.89, (0,6)->0.92). Because chi_Si^q ~ 0 for x_SiO2 < ~0.55,
    the term is nearly orthogonal to the central v0.2 excess: it opens the gap without
    disturbing the forsterite/enstatite region.

So v0.4 = v0.2 (central) + one silica-weighted term (0,5), with the symmetric g00
enthalpy re-tuned to hold forsterite melting (the silica term slightly destabilises the
liquid at x=1/3). Two anchors fix the two re-fit coefficients:

  1. forsterite Mg2SiO4 congruent melting = 2163 K          -> g00 enthalpy (a00)
  2. gap MgO-side conjugate (binodal) = 0.59 at 1968 K       -> silica term L_si

g10 (chi_Mg skew) and the g00 entropy b00 are carried over from v0.2 unchanged. The
gap composition is essentially independent of a00 and the melting of L_si, so the two
solve almost separably.
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

COMPONENTS = pdg.COMPONENTS
# carried over from v0.2 (data/mgo-sio2/PROVENANCE.md, v0.2 section)
G00_B = -3.5875          # excess entropy slope, J/mol/K
G10 = 30163.1            # chi_Mg skew, J/mol
Q_SI = 5                 # silica-network exponent on chi_Si (fitted form)
T_FORST, X_FORST = 2163.0, 1.0 / 3.0
T_MONO = 1968.0          # Greig monotectic
X_GAP_MG = 0.59          # MgO-side conjugate liquid at the monotectic (Greig)


def build_db(a00, L_si):
    excess = [dict(code="Q", li=[1, 2, 3, 3], exp=[0, 0, 0, 0],
                   coeffs=[a00, G00_B, 0, 0, 0, 0]),
              dict(code="Q", li=[1, 2, 3, 3], exp=[1, 0, 0, 0],
                   coeffs=[G10, 0, 0, 0, 0, 0]),
              dict(code="Q", li=[1, 2, 3, 3], exp=[0, Q_SI, 0, 0],
                   coeffs=[L_si, 0, 0, 0, 0, 0])]
    path = HERE / "_v04_scaffold.dat"
    path.write_text(bd.build(excess, version="v0.4"), encoding="ascii")
    db = mqmqa.Database.read(str(path))
    return db, db.phase_index("MGO-SIO2-LIQUID"), excess


def forsterite_T(db, p, lo=1600.0, hi=2800.0):
    def f(T):
        inp = eq.build_inputs(db, p, T, components=COMPONENTS)
        return (pdg.liquid_gibbs_per_formula_unit(inp, X_FORST, T)
                - pdg.solid_gibbs_per_formula_unit("M2S(forsterite)", T)[0])
    if f(lo) * f(hi) > 0:
        return None
    for _ in range(60):
        m = 0.5 * (lo + hi)
        lo, hi = (m, hi) if f(lo) * f(m) > 0 else (lo, m)
    return 0.5 * (lo + hi)


def gap(db, p, T, xlo=0.35, xhi=0.995, n=150):
    """Two-liquid binodal (common-tangent gap) from the lower convex hull of
    delta_g_mix(x); returns (x_left, x_right) or None."""
    inp = eq.build_inputs(db, p, T, components=COMPONENTS)
    xs = np.linspace(xlo, xhi, n)
    g = np.array([act.delta_g_mix(inp, float(x)) for x in xs])
    H = []
    for x, y in zip(xs, g):
        while len(H) >= 2 and ((H[-1][0]-H[-2][0])*(y-H[-2][1])
                               - (H[-1][1]-H[-2][1])*(x-H[-2][0])) <= 0:
            H.pop()
        H.append((x, y))
    hx = [h[0] for h in H]
    gg = [(hx[i], hx[i+1]) for i in range(len(hx)-1) if hx[i+1]-hx[i] > 0.03]
    return gg[0] if gg else None


def fit(a0=-79000.0, L0=100000.0, iters=2, nbis=18):
    """Nested 1-D solves: L_si for the gap edge, a00 for forsterite melting. They are
    nearly independent (chi_Si^5 ~ 0 at x=1/3; the gap edge barely depends on a00), so
    a few alternations of coarse bisection converge to well within the data scatter."""
    a00, L_si = a0, L0
    for _ in range(iters):
        # L_si: bisect so the MgO-side gap edge = X_GAP_MG at T_MONO (more L -> edge left)
        lo, hi = 70000.0, 140000.0
        for _ in range(nbis):
            m = 0.5 * (lo + hi)
            db, p, _ = build_db(a00, m)
            gp = gap(db, p, T_MONO)
            edge = gp[0] if gp else 0.0
            lo, hi = (m, hi) if edge > X_GAP_MG else (lo, m)
        L_si = 0.5 * (lo + hi)
        # a00: bisect so forsterite congruent = T_FORST. Deeper (more negative) a00
        # lowers Tc, so if Tc is too HIGH search the lower (more negative) half.
        lo, hi = -90000.0, -70000.0
        for _ in range(nbis):
            m = 0.5 * (lo + hi)
            db, p, _ = build_db(m, L_si)
            Tc = forsterite_T(db, p) or 0.0
            lo, hi = (lo, m) if Tc > T_FORST else (m, hi)
        a00 = 0.5 * (lo + hi)
    return a00, L_si


def main(write=True):
    a00, L_si = fit()
    db, p, excess = build_db(a00, L_si)
    Tc = forsterite_T(db, p)
    gp = gap(db, p, T_MONO)

    print("=" * 72)
    print("v0.4 fit  (MgO-SiO2: central liquid + silica-rich miscibility gap)")
    print("=" * 72)
    print(f"  g00 = {a00:+.1f} {G00_B:+.4f}*T   g10 = {G10:+.1f}   "
          f"g_si(0,{Q_SI}) = {L_si:+.1f}   J/mol")
    print()
    print(f"  forsterite congruent melting = {Tc:.0f} K   (target 2163)")
    print(f"  silica gap (binodal) at {T_MONO:.0f} K = "
          f"{gp[0]:.3f}-{gp[1]:.3f}   (Greig 0.59-0.99)")

    # gap dome vs T (monotectic ~1968; consolute = where it closes)
    print("\n  gap(T):")
    for T in (1800, 1900, 1968, 2100, 2300, 2450):
        g2 = gap(db, p, float(T))
        print(f"    T={T}: {f'{g2[0]:.3f}-{g2[1]:.3f}' if g2 else 'closed'}")

    # enstatite still peritectic?
    import phase_hull as hull
    _, xC, Tmax, kind, _ = hull.classify_compound(db, p, "MS(enstatite)")
    print(f"\n  enstatite: {kind}  at {Tmax:.0f} K  (measured peritectic ~1830)")

    # implied dH_mix (central liquid depth; cf v0.2 MLIP anchors)
    def dh(x, T=2100.0, dT=50.0):
        def gg(TT):
            inp = eq.build_inputs(db, p, TT, components=COMPONENTS)
            return act.delta_g_mix(inp, x)
        return gg(T) - T * (gg(T+dT) - gg(T-dT)) / (2*dT)
    print(f"  dH_mix(x=1/3)={dh(X_FORST)/1000:+.1f}  dH_mix(x=1/2)={dh(0.5)/1000:+.1f} "
          f"kJ/mol-oxide  (v0.2 MLIP: -24.5 / -22.4)")

    if write:
        out = HERE / "MgO-SiO2-liquid.dat"
        out.write_text(bd.build(excess, version="v0.4"), encoding="ascii")
        print(f"\n  wrote {out} (v0.4)")
    return a00, L_si


if __name__ == "__main__":
    main()
