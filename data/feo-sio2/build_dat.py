"""Build the open FeO-SiO2 liquid-slag MQMQA database (ChemSage SUBQ .dat), v0.1.

The Fe-side counterpart of data/mgo-sio2, and the second binary the FeO-MgO-SiO2 ternary
slag needs. Iron-saturated (all iron is Fe2+ / FeO; no Fe3+), matching Bowen & Schairer's
iron-crucible phase-equilibrium conditions.

v0.1 is IDEAL (endmember-only): the two pure-oxide liquid endmembers FeO(liq) and SiO2(liq)
assembled entirely from open pure-substance data, no fitted excess. Its interior mixing is a
documented placeholder pending an open-data optimization (needs FeO-SiO2 melt activities or
an MLIP enthalpy anchor - see PROVENANCE.md).

Endmember Gibbs G_liq(T) = G_solid(T) + dHfus*(1 - T/Tm), with the solid heat capacity in
Haas-Fisher form Cp = a + b*T + c*T^-2 integrated to the six ChemSage coefficients on the
term basis (1, T, T*lnT, T^2, T^3, 1/T).
"""
import math
from pathlib import Path

T0 = 298.15

# --- open published pure-oxide data (per-number citation in PROVENANCE.md) ---
OXIDES = {
    "FeO": dict(
        # NIST-JANAF (Chase 1998): dHf(298) = -272.044 kJ/mol, S(298) = 60.752 J/mol/K.
        # Cp a,b,c fit to the JANAF FeO(crystal) tabulation 298-1500 K (max resid 0.35).
        # FeO melting Tm = 1650 K, dHfus = 24.058 kJ/mol (JANAF).
        dHf=-272044.0, S298=60.752, a=50.66300, b=8.711283e-3, c=-3.13381e5,
        Tm=1650.0, dHfus=24058.0,
        cation="Fe", anion="O", charge=2.0, stoich_el={"Fe": 1.0, "O": 1.0}, quad=(1.0, 1.0),
    ),
    "SiO2": dict(  # identical to data/mgo-sio2 (Robie-Hemingway solid; NIST-JANAF fusion)
        dHf=-908400.0, S298=43.4, a=72.75, b=1.300e-3, c=-4.132e6,
        Tm=1996.0, dHfus=9581.0,
        cation="Si", anion="O", charge=4.0, stoich_el={"Si": 1.0, "O": 2.0}, quad=(1.0, 2.0),
    ),
}

ELEMENTS = [("Fe", 55.845), ("Si", 28.085), ("O", 15.9994)]
Z_PER_CHARGE = 1.3774438 / 2.0
ORDER = ["FeO", "SiO2"]


def solid_gibbs_coeffs(dHf, S298, a, b, c):
    """Six ChemSage coefficients of the solid Gibbs energy for Cp = a + b*T + c*T^-2."""
    A = dHf - a * T0 - 0.5 * b * T0 * T0 + c / T0
    B = a - S298 + a * math.log(T0) + b * T0 - 0.5 * c / (T0 * T0)
    return [A, B, -a, -0.5 * b, 0.0, -0.5 * c]


def liquid_gibbs_coeffs(ox):
    A, B, C, D, E, F = solid_gibbs_coeffs(ox["dHf"], ox["S298"], ox["a"], ox["b"], ox["c"])
    return [A + ox["dHfus"], B - ox["dHfus"] / ox["Tm"], C, D, E, F]


def _fmt(x):
    return f"{x:.12E}"


def _mqmx_block(excess):
    """Serialize MQMX excess parameters (ChemSage layout the reader parses). Each dict:
    code 'Q'/'G', li the four 1-based quadruplet species [A,B,X,Y] (cation-mixing Fe+Si on
    O = [1,2,3,3]), exp the four exponents [p,q,0,0], coeffs the six term-basis coefficients."""
    out = []
    for ex in excess:
        out.append("   1")  # per-parameter nonzero mixing-type flag
        out.append(" " + ex["code"] + "   " + "   ".join(str(i) for i in ex["li"])
                   + "   " + "   ".join(str(e) for e in ex["exp"]))
        out.append("  " + "   ".join("0.00000000" for _ in range(6)))
        out.append("  " + "   ".join("0.00000000" for _ in range(6)))
        out.append("   0   0   " + "   ".join(_fmt(c) for c in ex["coeffs"]))
    out.append("   0")  # terminate the excess block
    return out


def build(excess=None, version=None):
    L = []
    ap = L.append
    ver = version or ("v0.2" if excess else "v0.1")
    ap(f" System FeO-SiO2  open iron-silicate slag database {ver} (provenance: data/feo-sio2/PROVENANCE.md)")
    ap(f"    {len(ELEMENTS)}    1    2    0")            # n_el, n_soln, count, n_stoich
    ap(" " + "                       ".join(e[0] for e in ELEMENTS))
    ap("   " + "              ".join(f"{m:.9f}" for _, m in ELEMENTS))
    ap("    6   1   2   3   4   5   6")
    ap("    6   1   2   3   4   5   6")

    ap(" FeO-SiO2-liquid")
    ap(" SUBQ")
    ap("   2   2")                                       # n_pairs, n_quads (MQMZ rows)
    for name in ORDER:
        ox = OXIDES[name]
        se = ox["stoich_el"]
        stoich_el = [se.get(el, 0.0) for el, _ in ELEMENTS]
        ap(f" {name}")
        ap("   1   1   " + "   ".join(f"{s:.1f}" for s in stoich_el))
        ap("  6000.0000   " + "   ".join(_fmt(v) for v in liquid_gibbs_coeffs(ox)))
        ap("  " + "   ".join(f"{v:.5f}" for v in [ox["quad"][0], ox["quad"][1], 0.0, 0.0, 0.0]))
        ap("  1.3774438")                                # anion-coordination base (divalent O)

    ap("   2   1")                                       # n_cat, n_an
    ap(" Fe+2                     Si+4")
    ap(" O")
    ap("  2.00000      4.00000")                         # cation charges
    ap("   1   1")                                       # cation groups
    ap("  2.00000")                                      # anion charge magnitude
    ap("   1")                                           # anion group
    ap("   1   2")                                       # pair cation indices
    ap("   1   1")                                       # pair anion indices

    z_fe, z_o = 2 * Z_PER_CHARGE, 2 * Z_PER_CHARGE
    z_si = 4 * Z_PER_CHARGE
    ap(f"   1   1   3   3   {z_fe:.7f}   {z_fe:.7f}   {z_o:.7f}   {z_o:.7f}")
    ap(f"   2   2   3   3   {z_si:.7f}   {z_si:.7f}   {z_o:.7f}   {z_o:.7f}")
    if excess:
        L.extend(_mqmx_block(excess))
    else:
        ap("   0")                                       # ideal v0.1 (no excess)
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    out = Path(__file__).with_name("FeO-SiO2-liquid.dat")
    out.write_text(build(), encoding="ascii")
    print(f"wrote {out}")
    for name in ORDER:
        print(name, "liquid G coeffs =", [round(x, 4) for x in liquid_gibbs_coeffs(OXIDES[name])])
