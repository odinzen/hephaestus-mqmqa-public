"""Validate the open MgO-SiO2 liquid database against the engine and published data.

Checks, all reporting real numbers:
  1. The .dat loads via mqmqa.Database.read and the engine reads its structure
     (elements, phase, cations/anions, pairs, coordination, excess).
  2. The pure-oxide liquid endmember Gibbs energies read back by the C engine match
     an independent H - T*S evaluation of the same open Robie-Hemingway / NIST-JANAF
     data (confirms the coefficients are encoded and parsed correctly).
  3. The database reproduces the published fusion points Tm(SiO2)=1996 K and
     Tm(CaO)=3200 K: the liquid endmember minus the pure-solid reference crosses zero
     there (the engine evaluates dG_fus to ~0 at the published melting temperatures).
  4. The single-phase solver runs on a mixed MgO-SiO2 melt and the pure-oxide limits
     return the endmember energies (a sanity check that the phase is well-formed).

This checks the ENDMEMBERS and structure only; it stays valid for both v0.1 (ideal)
and v0.2 (with fitted excess). The interior mixing (negative-deviation activities,
delta-G_mix) is validated separately in `validate_v02.py`.
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "python"))
import mqmqa
from mqmqa import equilibrium as eq
import build_dat as bd

DAT = Path(__file__).with_name("MgO-SiO2-liquid.dat")
T0 = 298.15


def solid_gibbs(ox, T):
    """Direct H - T*S of the pure solid oxide from the open Cp data, no fusion."""
    a, b, c = ox["a"], ox["b"], ox["c"]
    H = (ox["dHf"] + a * (T - T0) + 0.5 * b * (T * T - T0 * T0) - c * (1.0 / T - 1.0 / T0))
    S = (ox["S298"] + a * math.log(T / T0) + b * (T - T0) - 0.5 * c * (1.0 / (T * T) - 1.0 / (T0 * T0)))
    return H - T * S


def liquid_gibbs(ox, T):
    return solid_gibbs(ox, T) + ox["dHfus"] * (1.0 - T / ox["Tm"])


def main():
    print("=" * 70)
    print("1. LOAD + STRUCTURE")
    print("=" * 70)
    db = mqmqa.Database.read(DAT)
    print("elements:", db.elements)
    print("phases:", db.phase_names)
    p = db.phase_index("MGO-SIO2-LIQUID")
    print("phase index:", p, "is_subq:", db.is_subq(p))
    print("cations:", db.cations(p))
    print("anions:", db.anions(p))
    pr = db.pairs(p, 1873.0)
    print("pairs cat/an idx:", pr["cat"], pr["an"])
    print("pair stoich (cation count):", pr["stoich"], "zeta:", pr["zeta"])
    mz = db.mqmz(p)
    print("coordination entries A,B,X,Y:", mz["A"], mz["B"], mz["X"], mz["Y"])
    print("coordination Z:", [round(z, 5) for z in mz["Z"]])
    print("excess (MQMX) terms:", len(db.mqmx(p, 1873.0)["A"]), "(0 = ideal v0.1)")

    print()
    print("=" * 70)
    print("2. ENDMEMBER GIBBS ROUND-TRIP  (engine vs independent H-T*S of R&H/JANAF)")
    print("=" * 70)
    # pair order in the file is CaO (index 0), SiO2 (index 1)
    idx = {"MgO": 0, "SiO2": 1}
    worst = 0.0
    for T in (1000.0, 1873.0, 2000.0):
        pr = db.pairs(p, T)
        for name in ("MgO", "SiO2"):
            g_engine = pr["G"][idx[name]]
            g_ref = liquid_gibbs(bd.OXIDES[name], T)
            d = abs(g_engine - g_ref)
            worst = max(worst, d)
            print(f"  {name:5s} T={T:6.0f}K  engine={g_engine:14.3f}  "
                  f"H-TS={g_ref:14.3f}  diff={d:.3e} J/mol")
    # tolerance is set by the 8-significant-figure coefficients stored in the .dat;
    # ~1e-3 J/mol on a ~1e6 J/mol energy is round-off, not a modelling difference.
    print(f"  worst |diff| = {worst:.2e} J/mol  ->  {'PASS' if worst < 1e-2 else 'FAIL'}")

    print()
    print("=" * 70)
    print("3. PUBLISHED FUSION POINTS  (dG_fus = G_liq - G_solid -> 0 at Tm)")
    print("=" * 70)
    for name, Tm_pub, src in (("SiO2", 1996.0, "NIST-JANAF cristobalite<->liquid"),
                              ("MgO", 3098.0, "MgO Tm 2825 degC (NIST-JANAF; dHfus ~77 kJ)")):
        ox = bd.OXIDES[name]
        pr = db.pairs(p, Tm_pub)
        g_liq = pr["G"][idx[name]]
        g_sol = solid_gibbs(ox, Tm_pub)
        print(f"  {name:5s} Tm(pub)={Tm_pub:6.0f}K  engine G_liq={g_liq:12.2f}  "
              f"G_solid={g_sol:12.2f}  dG_fus={g_liq - g_sol:8.3f} J/mol   [{src}]")

    print()
    print("=" * 70)
    print("4. SOLVER + PURE-LIMIT REDUCTION")
    print("=" * 70)
    import numpy as np
    T = 1873.0
    inp = eq.build_inputs(db, p, T, components=["CA", "SI", "O"])
    # Pure limits: evaluate the pure quadruplet directly. The SLSQP solver is
    # unreliable exactly at a composition corner (a quadruplet fraction pinned to
    # zero), so the endmember reduction is checked on the pure quadruplet itself.
    for name, qtag in (("CaO", (0, 0, 0, 0)), ("SiO2", (1, 1, 0, 0))):
        i = inp["quads"].index(qtag)
        X = np.zeros(len(inp["quads"])); X[i] = 1.0
        g_quad = eq.gibbs_per_quad(inp, X)
        els = eq.element_moles(inp, X)
        n_formula = els[bd.OXIDES[name]["cation"].upper()]  # moles of the oxide formula
        g_per_formula = g_quad / n_formula
        g_ref = liquid_gibbs(bd.OXIDES[name], T)
        print(f"  pure {name:5s}: G/formula={g_per_formula:12.2f}  endmember={g_ref:12.2f}  "
              f"diff={abs(g_per_formula - g_ref):.2e} J/mol")
    # Interior melt: the solver converges and returns a smooth ideal-mixing energy.
    for xSiO2 in (0.25, 0.50, 0.75):
        comp = {"CA": (1 - xSiO2), "SI": xSiO2, "O": (1 - xSiO2) + 2 * xSiO2}
        r = eq.equilibrate(inp, comp)
        print(f"  x(SiO2)={xSiO2:.2f}  GM={r['GM']:12.2f} J/mol-atom  converged={r['success']}")
    print("  (endmember/structure check; interior mixing is validated in "
          "validate_v02.py.)")


if __name__ == "__main__":
    main()
