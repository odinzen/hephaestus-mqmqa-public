"""Build the open MgO-SiO2 liquid-slag MQMQA database (ChemSage SUBQ .dat).

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
    "MgO": dict(
        # dHf/S298 = CODATA key values (-601.5 kJ/mol, 26.95 J/mol/K); Cp a,b,c fit to
        # the NIST-JANAF periclase Cp tabulation (298-2000 K, max resid 0.32 J/mol/K).
        # MgO melting is well established (unlike CaO): Tm = 3098 K (2825 degC), dHfus
        # ~ 77 kJ/mol (NIST-JANAF).
        dHf=-601500.0, S298=26.95, a=48.2425, b=3.906019e-3, c=-1.1082e6,
        Tm=3098.0, dHfus=77000.0,
        n_cat=1, n_an=2, cation="Mg", anion="O", stoich_el={"Mg": 1.0, "O": 1.0},
    ),
    "SiO2": dict(
        dHf=-908400.0, S298=43.4, a=72.75, b=1.300e-3, c=-4.132e6,
        Tm=1996.0, dHfus=9581.0,
        n_cat=1, n_an=2, cation="Si", anion="O", stoich_el={"Si": 1.0, "O": 2.0},
    ),
}

ELEMENTS = [("Mg", 24.305), ("Si", 28.085), ("O", 15.9994)]

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
               (cations 1..n_cat, anions n_cat+1..; for Mg+2/Si+4 cation mixing
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


def build(excess=None, version=None, z_si=None, z_o_si=None, zeta_si=None,
          z_mixed=None, dcp_fus_sio2=None):
    """SiO2 pure-quadruplet coordination overrides (the v0.4 lever). Defaults (None)
    give the charge-proportional base (Z_Si=2.7549, Z_O=1.3774, zeta=1.3774) used in
    v0.1-v0.2. Setting z_si / z_o_si / zeta_si independently makes SiO2 non-charge-
    proportional to place the silica-rich miscibility gap. Note: scaling all three by a
    common factor is a gauge no-op; only the RATIOS relative to the MgO quad matter."""
    L = []
    ap = L.append

    ver = version or ("v0.2" if excess else "v0.1")
    ap(f" System MgO-SiO2  open oxide-slag database {ver}"
       "  (provenance: data/mgo-sio2/PROVENANCE.md)")
    # number of MQMZ coordination rows: 2 pure quads, +1 if the mixed (Mg,Si)/O
    # quadruplet coordination is given explicitly (the Pelton short-range-order lever).
    n_mqmz = 3 if z_mixed is not None else 2
    # header: n_el, n_soln, [soln species-count per phase], n_stoich
    ap(f"    {len(ELEMENTS)}    1    2    0")
    ap(" " + "                       ".join(e[0] for e in ELEMENTS))
    ap("   " + "              ".join(f"{m:.9f}" for _, m in ELEMENTS))
    # Gibbs term basis and excess term basis: indices 1..6 = (1, T, T*lnT, T^2, T^3, 1/T)
    ap("    6   1   2   3   4   5   6")
    ap("    6   1   2   3   4   5   6")

    # --- the single solution phase ---
    ap(" MgO-SiO2-liquid")
    ap(" SUBQ")
    ap(f"   2   {n_mqmz}")  # n_pairs, n_quads (MQMZ rows)

    order = ["MgO", "SiO2"]
    for name in order:
        ox = OXIDES[name]
        se = ox["stoich_el"]
        stoich_el = [se.get(el, 0.0) for el, _ in ELEMENTS]
        coeffs = liquid_gibbs_coeffs(ox)
        # optional heat-capacity of fusion for SiO2 (v0.1-v0.9 used dCp_fus = 0). Liquid
        # silica has a higher Cp than cristobalite (~86 vs ~74 J/mol/K), so a positive
        # dCp_fus makes the silica-rich liquid more stable above Tm - lowering where
        # cristobalite preempts the silica-rich immiscible liquid. Constant dCp_fus adds
        # dCp*[(T-Tm) - T*ln(T/Tm)] to G_liq: A += -dCp*Tm, B += dCp*(1+ln Tm), C += -dCp.
        if name == "SiO2" and dcp_fus_sio2:
            Tm = ox["Tm"]
            coeffs = list(coeffs)
            coeffs[0] += -dcp_fus_sio2 * Tm
            coeffs[1] += dcp_fus_sio2 * (1.0 + math.log(Tm))
            coeffs[2] += -dcp_fus_sio2
        ap(f" {name}")
        # eq_type=1 (plain Gibbs, no additional terms), n_intervals=1, then n_el stoich
        ap("   1   1   " + "   ".join(f"{s:.1f}" for s in stoich_el))
        ap(_coeff_line(6000.0, coeffs))
        # five quadruplet-stoichiometry values: [n_cation, n_anion, 0, 0, 0]
        ap("  " + "   ".join(f"{v:.5f}" for v in
                             [se.get(ox["cation"], 0.0), se.get(ox["anion"], 0.0), 0.0, 0.0, 0.0]))
        # pair zeta: the anion-coordination base value (divalent O convention);
        # SiO2 may override it (v0.4 non-charge-proportional lever)
        zeta = (zeta_si if (name == "SiO2" and zeta_si is not None) else 1.3774438)
        ap(f"  {zeta:.7f}")

    # --- cation / anion sublattice definitions ---
    ap("   2   1")  # n_cat, n_an
    ap(" Mg+2                     Si+4")
    ap(" O")
    ap("  2.00000      4.00000")  # cation charges
    ap("   1   1")                # cation groups
    ap("  2.00000")               # anion charge (positive magnitude)
    ap("   1")                    # anion group
    # pair (cation,anion) linear labels, in the pair order above: MgO=(Mg,O), SiO2=(Si,O)
    ap("   1   2")  # cation index of each pair
    ap("   1   1")  # anion index of each pair

    # --- MQMZ coordination entries (pure quadruplets only; mixed ones derived) ---
    # linear indices: cations 1..2, anion 3. MgO stays charge-proportional; SiO2's
    # cation Z (z_si) and its O-slot Z (z_o_si) can be overridden (the v0.4 lever).
    z_mg = 2 * Z_PER_CHARGE
    z_o = 2 * Z_PER_CHARGE
    zsi = 4 * Z_PER_CHARGE if z_si is None else z_si
    zosi = 2 * Z_PER_CHARGE if z_o_si is None else z_o_si
    ap(f"   1   1   3   3   {z_mg:.7f}   {z_mg:.7f}   {z_o:.7f}   {z_o:.7f}")
    ap(f"   2   2   3   3   {zsi:.7f}   {zsi:.7f}   {zosi:.7f}   {zosi:.7f}")
    # explicit mixed-cation quadruplet (Mg,Si / O,O): z_mixed = (zMg, zSi, zO_A, zO_B).
    # This overrides the value the engine would otherwise derive from the pure pairs,
    # and is the Pelton lever that sets the composition of maximum short-range ordering.
    if z_mixed is not None:
        zmg_x, zsi_x, zoa_x, zob_x = z_mixed
        ap(f"   1   2   3   3   {zmg_x:.7f}   {zsi_x:.7f}   {zoa_x:.7f}   {zob_x:.7f}")

    # --- excess (MQMX): none in v0.1 (ideal), fitted Q terms in v0.2. ---
    if excess:
        L.extend(_mqmx_block(excess))
    else:
        ap("   0")

    return "\n".join(L) + "\n"


if __name__ == "__main__":
    out = Path(__file__).with_name("MgO-SiO2-liquid.dat")
    out.write_text(build(), encoding="ascii")
    print(f"wrote {out}")
    for name in ("MgO", "SiO2"):
        print(name, "liquid G coeffs [A,B,C,D,E,F] =",
              [round(x, 6) for x in liquid_gibbs_coeffs(OXIDES[name])])
