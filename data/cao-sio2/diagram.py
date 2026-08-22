"""CaO-SiO2 binary invariants (eutectics, congruent melts) from a fitted .dat.

Stable state at (x, T) = lower convex hull of the liquid G(x) curve (from the MQMQA
engine) plus the fixed-composition solids (phase_diagram.SOLIDS). Two invariants:

  congruent melting of a compound = T where G_liq(x_compound) == G_solid(compound).
  eutectic between solids S1, S2   = T where the liquid curve is tangent to the
    straight S1-S2 tie line, i.e. min_x [G_liq(x) - tieline_{S1,S2}(x)] crosses 0.
    Above that T a stable liquid exists between S1 and S2; below it only S1+S2.

All energies per mole of oxide formula unit. Pass the .dat to test on the command
line (defaults to the shipped CaO-SiO2-liquid.dat).
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


def load(datpath):
    db = mqmqa.Database.read(str(datpath))
    p = db.phase_index("CAO-SIO2-LIQUID")
    return db, p


def g_liq(db, p, x, T):
    inp = eq.build_inputs(db, p, T, components=["CA", "SI", "O"])
    return pdg.liquid_gibbs_per_formula_unit(inp, x, T)


def congruent_T(db, p, name, lo=1400.0, hi=2600.0):
    x = pdg.SOLIDS[name][1] / (pdg.SOLIDS[name][0] + pdg.SOLIDS[name][1])
    f = lambda T: g_liq(db, p, x, T) - pdg.solid_gibbs_per_formula_unit(name, T)[0]
    if f(lo) * f(hi) > 0:
        return None
    for _ in range(60):
        m = 0.5 * (lo + hi)
        lo, hi = (m, hi) if f(lo) * f(m) > 0 else (lo, m)
    return 0.5 * (lo + hi)


def eutectic(db, p, n1, n2, lo=1300.0, hi=2600.0):
    x1 = pdg.SOLIDS[n1][1] / (pdg.SOLIDS[n1][0] + pdg.SOLIDS[n1][1])
    x2 = pdg.SOLIDS[n2][1] / (pdg.SOLIDS[n2][0] + pdg.SOLIDS[n2][1])
    xa, xb = sorted((x1, x2))
    xs = np.linspace(xa + 0.02, xb - 0.02, 25)

    def margin(T):
        gs1 = pdg.solid_gibbs_per_formula_unit(n1, T)[0]
        gs2 = pdg.solid_gibbs_per_formula_unit(n2, T)[0]
        gl = np.array([g_liq(db, p, float(x), T) for x in xs])
        tie = gs1 + (gs2 - gs1) * (xs - x1) / (x2 - x1)
        d = gl - tie
        i = int(np.argmin(d))
        return d[i], xs[i]

    if margin(lo)[0] > 0 and margin(hi)[0] > 0:
        return None, None
    for _ in range(45):
        m = 0.5 * (lo + hi)
        lo, hi = (m, hi) if (margin(lo)[0] < 0) == (margin(m)[0] < 0) else (lo, m)
    Te = 0.5 * (lo + hi)
    return Te, margin(Te)[1]


# published invariants (K), classic CaO-SiO2 diagram / Abdul 2023 Table 9
PUBLISHED = {
    "CS(pseudowoll) congruent": 1817.0,
    "C2S(gamma) congruent": 2403.0,
    "CS-C3S2 eutectic": 1733.0,       # 1460 C
    "CS-SiO2 eutectic": 1709.0,       # 1436 C (tridymite; we carry cristobalite)
}


def main():
    datpath = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "CaO-SiO2-liquid.dat"
    db, p = load(datpath)
    print(f"invariants from {datpath.name}")
    print("=" * 62)

    for name, tag in (("CS(pseudowoll)", "CS(pseudowoll) congruent"),
                      ("C2S(gamma)", "C2S(gamma) congruent")):
        T = congruent_T(db, p, name)
        pub = PUBLISHED[tag]
        s = f"{T:6.0f} K" if T else "  none"
        d = f"{T-pub:+5.0f}" if T else "   -"
        print(f"  {tag:26s} engine {s}   pub {pub:6.0f} K   diff {d}")

    for n1, n2, tag in (("CS(pseudowoll)", "C3S2(rankinite)", "CS-C3S2 eutectic"),
                        ("CS(pseudowoll)", "SiO2(cristobalite)", "CS-SiO2 eutectic")):
        Te, xe = eutectic(db, p, n1, n2)
        pub = PUBLISHED[tag]
        if Te:
            print(f"  {tag:26s} engine {Te:6.0f} K (x_SiO2~{xe:.2f})   "
                  f"pub {pub:6.0f} K   diff {Te-pub:+5.0f}")
        else:
            print(f"  {tag:26s} engine   none found")


if __name__ == "__main__":
    main()
