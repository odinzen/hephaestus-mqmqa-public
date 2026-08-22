"""Lower-convex-hull phase-diagram sweep that CLASSIFIES the MgO-SiO2 invariants.

Mirrors data/cao-sio2/phase_hull.py. At each temperature the stable state is the lower
convex hull of the liquid G(x) curve plus the fixed-composition solids; sweeping T and
reading how the hull changes classifies each compound's melting as CONGRUENT (melts to
a liquid of its own composition) or INCONGRUENT/PERITECTIC (decomposes to another solid
+ liquid before it could congruently melt), and locates eutectics. Energies per mole of
oxide formula unit.

This is the honest phase module: it assumes nothing about melting type. Absolute
temperatures remain limited by the solid model (Neumann-Kopp Cp, refractory MgO
endmember, no silica-rich gap) - the point here is correct invariant CLASSIFICATION.
For MgO-SiO2 the target is: forsterite CONGRUENT, enstatite INCONGRUENT/peritectic.
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

XS = np.linspace(0.02, 0.98, 60)
COMPONENTS = pdg.COMPONENTS


def load(dat):
    db = mqmqa.Database.read(str(dat))
    return db, db.phase_index("MGO-SIO2-LIQUID")


def liquid_pts(db, p, T):
    inp = eq.build_inputs(db, p, T, components=COMPONENTS)
    return [(float(x), pdg.liquid_gibbs_per_formula_unit(inp, float(x), T), "L")
            for x in XS]


def solid_pts(T, exclude=None):
    pts = []
    for name in pdg.SOLIDS:
        if name == exclude:
            continue
        g, x = pdg.solid_gibbs_per_formula_unit(name, T)
        pts.append((x, g, name))
    return pts


def lower_hull(pts):
    pts = sorted(pts, key=lambda q: q[0])
    h = []
    for x, g, lab in pts:
        while len(h) >= 2:
            (x1, g1, _), (x2, g2, _) = h[-2], h[-1]
            if (x2 - x1) * (g - g1) - (g2 - g1) * (x - x1) <= 1e-9:
                h.pop()
            else:
                break
        h.append((x, g, lab))
    return h


def hull_bracket(hull, x):
    for i in range(len(hull) - 1):
        if hull[i][0] <= x <= hull[i + 1][0]:
            return hull[i], hull[i + 1]
    return hull[0], hull[-1]


def compound_is_stable(db, p, name, T):
    """Is solid `name` below the hull of everything else at its composition?"""
    g_c, xC = pdg.solid_gibbs_per_formula_unit(name, T)
    others = liquid_pts(db, p, T) + solid_pts(T, exclude=name)
    hull = lower_hull(others)
    left, right = hull_bracket(hull, xC)
    if abs(right[0] - left[0]) < 1e-9:
        g_hull = left[1]
    else:
        f = (xC - left[0]) / (right[0] - left[0])
        g_hull = left[1] + f * (right[1] - left[1])
    return g_c < g_hull - 1.0, (left[2], right[2])


def classify_compound(db, p, name, lo=1400.0, hi=2500.0):
    xC = pdg.SOLIDS[name][1] / (pdg.SOLIDS[name][0] + pdg.SOLIDS[name][1])
    Ts = np.linspace(hi, lo, 130)
    Tmax, coex = None, None
    for T in Ts:
        st, pair = compound_is_stable(db, p, name, T)
        if st:
            Tmax, coex = T, pair
            break
    if Tmax is None:
        return name, xC, None, "never stable (metastable vs neighbours)", None
    left, right = coex
    if left == "L" and right == "L":
        kind = "CONGRUENT (-> liquid)"
    elif left == "L" or right == "L":
        other = right if left == "L" else left
        kind = f"INCONGRUENT / peritectic (-> liquid + {other})"
    else:
        kind = f"solid-solid ({left} + {right}) - decomposes, no melt"
    return name, xC, Tmax, kind, coex


def eutectic(db, p, n1, n2, lo=1300.0, hi=2500.0):
    x1 = pdg.SOLIDS[n1][1] / (pdg.SOLIDS[n1][0] + pdg.SOLIDS[n1][1])
    x2 = pdg.SOLIDS[n2][1] / (pdg.SOLIDS[n2][0] + pdg.SOLIDS[n2][1])
    xa, xb = sorted((x1, x2))
    xs = np.linspace(xa + 0.02, xb - 0.02, 25)

    def margin(T):
        g1 = pdg.solid_gibbs_per_formula_unit(n1, T)[0]
        g2 = pdg.solid_gibbs_per_formula_unit(n2, T)[0]
        inp = eq.build_inputs(db, p, T, components=COMPONENTS)
        gl = np.array([pdg.liquid_gibbs_per_formula_unit(inp, float(x), T) for x in xs])
        tie = g1 + (g2 - g1) * (xs - x1) / (x2 - x1)
        return (gl - tie).min()

    if margin(lo) > 0 and margin(hi) > 0:
        return None
    for _ in range(40):
        m = 0.5 * (lo + hi)
        lo, hi = (m, hi) if (margin(lo) < 0) == (margin(m) < 0) else (lo, m)
    return 0.5 * (lo + hi)


if __name__ == "__main__":
    dat = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "MgO-SiO2-liquid.dat"
    db, p = load(dat)
    print(f"Hull invariant classification from {dat.name}")
    print("=" * 70)
    print("Compound melting (type is the physics; T is solid-model-limited):")
    known = {"M2S(forsterite)": "CONGRUENT 2163 K",
             "MS(enstatite)": "INCONGRUENT / peritectic ~1830 K"}
    for name in ("M2S(forsterite)", "MS(enstatite)"):
        _, xC, Tmax, kind, _ = classify_compound(db, p, name)
        tt = f"{Tmax:6.0f} K" if Tmax else "   -  "
        print(f"  {name:18s} x={xC:.3f}  {tt}  {kind}")
        print(f"                       known: {known[name]}")
    print("\nEutectics (hull common-tangent):")
    for n1, n2 in (("MgO(periclase)", "M2S(forsterite)"),
                   ("MS(enstatite)", "SiO2(cristobalite)")):
        Te = eutectic(db, p, n1, n2)
        print(f"  {n1} + {n2}: {Te:.0f} K" if Te else f"  {n1} + {n2}: none")
