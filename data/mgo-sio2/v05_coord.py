"""Probe: can an explicit mixed-quadruplet coordination (the Pelton short-range-order
lever) reshape the ideal MgO-SiO2 mixing in our engine, and is it non-gauge?

Charge-proportional gives Z_Mg = 1.37744, Z_Si = 2.75489, Z_O = 1.37744; the engine
derives the mixed (Mg,Si)/O quad from the pure pairs. Here we set that mixed quad
EXPLICITLY and watch the ideal (no-excess) delta_g_mix and the activities.
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

COMPONENTS = ["MG", "SI", "O"]
BASE = 1.3774438
ZMG0, ZSI0, ZO0 = 2 * BASE / 2, 4 * BASE / 2, 2 * BASE / 2  # 1.37744, 2.75489, 1.37744


def build(z_mixed):
    import os
    path = HERE / f"_v05_coord_{os.getpid()}.dat"
    path.write_text(bd.build(z_mixed=z_mixed), encoding="ascii")
    db = mqmqa.Database.read(str(path))
    return db, db.phase_index("MGO-SIO2-LIQUID")


def profile(db, p, T=2100.0, n=41):
    xs = np.linspace(0.02, 0.98, n)
    inp = eq.build_inputs(db, p, T, components=COMPONENTS)
    g = np.array([act.delta_g_mix(inp, float(x)) for x in xs])
    imin = int(np.argmin(g))
    # activity of SiO2 at x=1/3 as an ordering fingerprint (ideal solution -> a=x)
    return xs[imin], g[imin] / 1000.0


def pure_ok(db, p, T=2000.0):
    """Pure-endmember integrity: SiO2 quad G per formula vs endmember, O:Si ratio."""
    inp = eq.build_inputs(db, p, T, components=COMPONENTS)
    i = inp["quads"].index((1, 1, 0, 0))
    X = np.zeros(len(inp["quads"])); X[i] = 1.0
    gq = eq.gibbs_per_quad(inp, X)
    els = eq.element_moles(inp, X)
    import validate as val
    return abs(gq / els["SI"] - val.liquid_gibbs(bd.OXIDES["SiO2"], T)), els["O"] / els["SI"]


if __name__ == "__main__":
    print("default charge-prop mixed quad = (%.4f, %.4f, %.4f, %.4f)"
          % (ZMG0, ZSI0, ZO0, ZO0))
    print("\nsanity: explicit mixed = charge-prop values must reproduce the derived case")
    db, p = build((ZMG0, ZSI0, ZO0, ZO0))
    dG, osi = pure_ok(db, p)
    xmin, gmin = profile(db, p)
    print(f"  pure SiO2 |dG/formula|={dG:.2e}  O:Si={osi:.4f}  "
          f"ideal dGmix min {gmin:+.2f} kJ at x_SiO2={xmin:.3f}")

    print("\nvary the mixed-quad cation ratio Z_Mg:Z_Si (anion fixed); watch the ideal")
    print("delta_g_mix minimum move = the short-range-order lever (non-gauge if it moves):")
    for zmg, zsi in [(ZMG0, ZSI0), (ZMG0, 4.0), (ZMG0, 6.0), (2.0, 2.0),
                     (1.0, 3.0), (3.0, 1.5), (0.9, 4.5)]:
        db, p = build((zmg, zsi, ZO0, ZO0))
        dG, osi = pure_ok(db, p)
        xmin, gmin = profile(db, p)
        print(f"  Z_Mg={zmg:.3f} Z_Si={zsi:.3f}: ideal dGmix min {gmin:+6.2f} kJ "
              f"at x_SiO2={xmin:.3f}   (pure O:Si={osi:.3f}, |dGpure|={dG:.1e})")
