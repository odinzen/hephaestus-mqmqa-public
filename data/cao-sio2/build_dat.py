"""Build the open CaO-SiO2 liquid-slag MQMQA database (ChemSage SUBQ .dat).

Every number written here traces to a published, open source (see PROVENANCE.md):
pure-oxide liquid endmembers from Robie & Hemingway (1995, USGS Bull. 2131, public
domain) for the solid heat capacities and reference data, and NIST-JANAF (Chase 1998,
open) for the fusion temperatures and enthalpies. No fitted or optimized excess
parameters are used; this v0.1 is an ideal quasichemical liquid (endmember-only), so
its interior mixing is a documented placeholder pending an open-data optimization.

The endmember Gibbs energy of each pure liquid oxide is assembled as

    G_liq(T) = G_solid(T) + dHfus * (1 - T/Tm)              (dCp_fus = 0, a v0 choice)
    G_solid(T) = dHf(298) + [H(T)-H(298)] - T * [S(298) + S_conf(T)]

with the solid heat capacity in Haas-Fisher form Cp = a + b*T + c*T^-2. Integrating
gives the six ChemSage coefficients on the term basis (1, T, T*lnT, T^2, T^3, 1/T);
the derivation is checked against a direct H - T*S evaluation in validate.py.
"""

import math
from pathlib import Path

T0 = 298.15  # K, reference temperature for dHf and S298


# --- open published pure-oxide data (see PROVENANCE.md for the per-number citation) ---
# a, b, c are the Haas-Fisher solid Cp coefficients Cp = a + b*T + c*T^-2 (J/mol/K).
OXIDES = {
    "CaO": dict(
        # Tm corrected in v0.3: the v0.1 value 3200 K was the old JANAF estimate,
        # ~350 K too high (Abdul 2023 notes the "dramatic change in the melting point
        # of CaO in the recent reassessment"). 2845 K = 2572 degC, the modern value
        # (CRC Handbook). dHfus keeps the JANAF/MgO-analog estimate (still approximate).
        dHf=-635100.0, S298=38.1, a=51.85, b=2.444e-3, c=-9.340e5,
        Tm=2845.0, dHfus=79500.0,
        n_cat=1, n_an=2, cation="Ca", anion="O", stoich_el={"Ca": 1.0, "O": 1.0},
    ),
    "SiO2": dict(
        dHf=-908400.0, S298=43.4, a=72.75, b=1.300e-3, c=-4.132e6,
        Tm=1996.0, dHfus=9581.0,
        n_cat=1, n_an=2, cation="Si", anion="O", stoich_el={"Si": 1.0, "O": 2.0},
    ),
}

ELEMENTS = [("Ca", 40.078), ("Si", 28.085), ("O", 15.9994)]

# Charge-proportional coordination, the FactSage-style oxide convention (base factor
# 1.3774438 per divalent cation, i.e. Z = 0.68872 * charge). These are model-framework
# defaults, not optimized values (they carry no fitted physics); documented as such.
Z_PER_CHARGE = 1.3774438 / 2.0


def solid_gibbs_coeffs(dHf, S298, a, b, c):
    """Six ChemSage coefficients [A, B, C, D, E, F] of the SOLID Gibbs energy
    G_solid(T) = dHf(298) + INT_298^T Cp dT - T*(S298 + INT_298^T Cp/T dT), with
    Cp = a + b*T + c*T^-2, on the term basis (1, T, T*lnT, T^2, T^3, 1/T).
    """
    A = dHf - a * T0 - 0.5 * b * T0 * T0 + c / T0
    B = a - S298 + a * math.log(T0) + b * T0 - 0.5 * c / (T0 * T0)
    C = -a
    D = -0.5 * b
    E = 0.0
    F = -0.5 * c
    return [A, B, C, D, E, F]


def liquid_gibbs_coeffs(ox):
    """Solid coefficients plus the fusion contribution dHfus*(1 - T/Tm)."""
    A, B, C, D, E, F = solid_gibbs_coeffs(ox["dHf"], ox["S298"], ox["a"], ox["b"], ox["c"])
    A += ox["dHfus"]
    B += -ox["dHfus"] / ox["Tm"]
    return [A, B, C, D, E, F]


def _fmt(x):
    return f"{x:.8E}"


def _coeff_line(tmax, coeffs):
    return "  " + f"{tmax:.4f}" + "   " + "   ".join(_fmt(c) for c in coeffs)


def _mqmx_block(excess):
    """Serialize MQMX excess parameters in the ChemSage layout the reader parses.

    excess is a list of dicts, each:
        code   'Q' or 'G'
        li     the four 1-based quadruplet species indices [A, B, X, Y]
               (cations 1..n_cat, anions n_cat+1..; for Ca+2/Si+4 cation mixing
                on O this is [1, 2, 3, 3])
        exp    the four integer exponents [p, q, 0, 0]
        coeffs the six excess coefficients on the term basis (1,T,TlnT,T^2,T^3,1/T);
               usually [L0, 0, 0, 0, 0, 0] for a constant, or [a, b, 0, 0, 0, 0]
               for L = a + b*T.
    Each parameter is preceded by a nonzero mixing-type flag; a trailing 0 ends the
    block. Twelve zero metadata doubles and two zero mixing-constituent ints sit
    between the exponents and the coefficients, matching FactSage's format.
    """
    out = []
    for ex in excess:
        out.append("   1")  # nonzero mixing-type flag (per-parameter)
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
    ap(f" System CaO-SiO2  open oxide-slag database {ver}"
       "  (provenance: data/cao-sio2/PROVENANCE.md)")
    # header: n_el, n_soln, [soln species-count per phase], n_stoich
    ap(f"    {len(ELEMENTS)}    1    2    0")
    ap(" " + "                       ".join(e[0] for e in ELEMENTS))
    ap("   " + "              ".join(f"{m:.9f}" for _, m in ELEMENTS))
    # Gibbs term basis and excess term basis: indices 1..6 = (1, T, T*lnT, T^2, T^3, 1/T)
    ap("    6   1   2   3   4   5   6")
    ap("    6   1   2   3   4   5   6")

    # --- the single solution phase ---
    ap(" CaO-SiO2-liquid")
    ap(" SUBQ")
    ap("   2   2")  # n_pairs, n_quads

    order = ["CaO", "SiO2"]
    for name in order:
        ox = OXIDES[name]
        se = ox["stoich_el"]
        stoich_el = [se.get(el, 0.0) for el, _ in ELEMENTS]
        coeffs = liquid_gibbs_coeffs(ox)
        ap(f" {name}")
        # eq_type=1 (plain Gibbs, no additional terms), n_intervals=1, then n_el stoich
        ap("   1   1   " + "   ".join(f"{s:.1f}" for s in stoich_el))
        ap(_coeff_line(6000.0, coeffs))
        # five quadruplet-stoichiometry values: [n_cation, n_anion, 0, 0, 0]
        ap("  " + "   ".join(f"{v:.5f}" for v in
                             [se.get(ox["cation"], 0.0), se.get(ox["anion"], 0.0), 0.0, 0.0, 0.0]))
        # pair zeta: the anion-coordination base value (divalent O convention)
        ap(f"  {1.3774438:.7f}")

    # --- cation / anion sublattice definitions ---
    ap("   2   1")  # n_cat, n_an
    ap(" Ca+2                     Si+4")
    ap(" O")
    ap("  2.00000      4.00000")  # cation charges
    ap("   1   1")                # cation groups
    ap("  2.00000")               # anion charge (positive magnitude)
    ap("   1")                    # anion group
    # pair (cation,anion) linear labels, in the pair order above: CaO=(Ca,O), SiO2=(Si,O)
    ap("   1   2")  # cation index of each pair
    ap("   1   1")  # anion index of each pair

    # --- MQMZ coordination entries (pure quadruplets only; mixed ones derived) ---
    # linear indices: cations 1..2, anion 3
    z_ca = 2 * Z_PER_CHARGE
    z_si = 4 * Z_PER_CHARGE
    z_o = 2 * Z_PER_CHARGE
    ap(f"   1   1   3   3   {z_ca:.7f}   {z_ca:.7f}   {z_o:.7f}   {z_o:.7f}")
    ap(f"   2   2   3   3   {z_si:.7f}   {z_si:.7f}   {z_o:.7f}   {z_o:.7f}")

    # --- excess (MQMX): none in v0.1 (ideal), fitted Q terms in v0.2. ---
    if excess:
        L.extend(_mqmx_block(excess))
    else:
        ap("   0")

    return "\n".join(L) + "\n"


if __name__ == "__main__":
    out = Path(__file__).with_name("CaO-SiO2-liquid.dat")
    out.write_text(build(), encoding="ascii")
    print(f"wrote {out}")
    for name in ("CaO", "SiO2"):
        print(name, "liquid G coeffs [A,B,C,D,E,F] =",
              [round(x, 6) for x in liquid_gibbs_coeffs(OXIDES[name])])
