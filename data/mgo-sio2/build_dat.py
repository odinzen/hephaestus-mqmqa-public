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
        # Fusion: NIST-JANAF 4th ed. (as copied by Barin 1995 p. 1014), Tm = 3105 K and dHfus =
        # 77.822 kJ/mol; JANAF's dHfus is an estimate (no calorimetry of liquid MgO exists).
        # Until 2026-10-02: 3098 K (McNally et al. 1961) with 77.0 kJ.
        dHf=-601500.0, S298=26.95, a=48.2425, b=3.906019e-3, c=-1.1082e6,
        Tm=3105.0, dHfus=77822.0,
        n_cat=1, n_an=2, cation="Mg", anion="O", stoich_el={"Mg": 1.0, "O": 1.0},
    ),
    "SiO2": dict(
        dHf=-905588.5, S298=50.8333, a=72.75, b=1.300e-3, c=-4.132e6,
        dHf_ref=-908400.0, S298_ref=43.4,   # see dbbuild STARTER_OXIDES
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
    """Solid coefficients plus the fusion contribution dHfus*(1 - T/Tm), and, when the oxide has a
    dCp_fus, a liquid heat capacity that much above the crystal's at every T, with dHfus and the
    fusion entropy kept at Tm: dG = dCp*[(T - Tm) - T*ln(T/Tm)]."""
    A, B, C, D, E, F = solid_gibbs_coeffs(ox["dHf"], ox["S298"], ox["a"], ox["b"], ox["c"])
    A += ox["dHfus"]
    B += -ox["dHfus"] / ox["Tm"]
    dcp = ox.get("dCp_fus", 0.0)
    if dcp:
        A += -dcp * ox["Tm"]
        B += dcp * (1.0 + math.log(ox["Tm"]))
        C += -dcp
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


# Liquid MgO's heat capacity above the crystal's (J/mol/K), assessed with the liquid under a prior
# from first-principles MD, liquid Cp = 78 +- 15 J/mol/K near Tm (de Koker & Stixrude 2009,
# doi:10.1111/j.1365-246X.2009.04142.x). Replaces, 2026-10-02, a free below-Tm slope (MGO_LIQ_BETA)
# whose fitted 8.7 J/K meant a fusion enthalpy near 50 kJ that no independent source supports.
# Every file with an MgO liquid reads it through OXIDES["MgO"]["dCp_fus"].
MGO_LIQ_DCP = 25.957685524103354
OXIDES["MgO"]["dCp_fus"] = MGO_LIQ_DCP

# The assessed liquid (2026-10-05 three-way fit "N1", assessment/joint3.py): this binary, the
# CaO-MgO-SiO2 face (Bowen 1914) and the FeO-MgO-SiO2 liquidus and solidus fitted together, with
# the measured forsterite fusion enthalpy in the binary data. Silica powers 0, 1, 3, 5, 7 and 2 plus
# one MgO-power term (Y_MgO^4), each a + b*T, with MGO_LIQ_DCP, MGSI_SRO_X and the two ternary term
# sets co-assessed; enstatite held at its stored correction. Shortfalls stated in PROVENANCE.md.
# (q, a, b) for L*Y_SiO2^q, or (p, q, a, b) with a Y_MgO^p factor as well.
# The ternary builders read it from here. Order follows assess.TERMS.
ASSESSED_EXCESS = [(0, -50536.046375251244, -5.5393249882077304),
                   (1, 1173.2857124046132, 13.142679832474492),
                   (3, 24479.546571656694, -8.843915154319394),
                   (5, 117449.05911765934, -26.197403061410647),
                   (7, 35345.96040085945, 0.8427975671457254),
                   (2, -48935.899736512205, 0.8464954407271559),
                   (4, 0, -36463.30689937065, -17.09968387771942)]


# Composition (x_SiO2) of maximum Mg-Si short-range order in the liquid, set through the
# coordination numbers of the (Mg,Si/O,O) quadruplet. 1/3 (forsterite) is the
# charge-proportional default and is written without an explicit mixed row.
MGSI_SRO_X = 0.3375317604753538


def mgsi_mixed_z(x_sro=None):
    """(Z_Mg, Z_Si, Z_O, Z_O) of the (Mg,Si/O,O) quadruplet ordering most at x_SiO2 = x_sro, with
    the quadruplet charge balance 2/Z_Mg + 4/Z_Si = 4/Z_O kept; None at the default."""
    x = MGSI_SRO_X if x_sro is None else x_sro
    if abs(x - 1.0 / 3.0) < 1e-12:
        return None
    z_o = 2 * Z_PER_CHARGE
    r = x / (1.0 - x)                      # Z_Mg / Z_Si
    z_mg = (2.0 + 4.0 * r) * z_o / 4.0
    return (z_mg, z_mg / r, z_o, z_o)


# An excess term may carry a heat capacity dcp (J/mol/K) as well, centred here so that a and b keep
# their meaning as the term's enthalpy and entropy at this temperature (the same form as dCp_fus).
XS_CP_T0 = 2000.0


def excess_coeffs(a, b, dcp=0.0):
    """Six excess coefficients of a + b*T + dcp*[(T - T0) - T*ln(T/T0)], T0 = XS_CP_T0."""
    if not dcp:
        return [a, b, 0, 0, 0, 0]
    return [a - dcp * XS_CP_T0, b + dcp * (1.0 + math.log(XS_CP_T0)), -dcp, 0, 0, 0]


def assessed_terms():
    """ASSESSED_EXCESS as (p, q, a, b, dcp). An entry is (q, a, b) for a silica-power term,
    (p, q, a, b) with an MgO power p as well, or (p, q, a, b, dcp) with an excess heat capacity."""
    out = []
    for t in ASSESSED_EXCESS:
        t = (0, *t) if len(t) == 3 else tuple(t)
        out.append(t + (0.0,) * (5 - len(t)))
    return out


def assessed_excess(li=(1, 2, 3, 3)):
    """ASSESSED_EXCESS as Q terms on the quadruplet li (MgO first, SiO2 second)."""
    return [dict(code="Q", li=list(li), exp=[p, q, 0, 0], coeffs=excess_coeffs(a, b, dcp))
            for p, q, a, b, dcp in assessed_terms()]


def build(excess=None, version=None, z_si=None, z_o_si=None, zeta_si=None,
          z_mixed=None, dcp_fus_sio2=None, mgo_liq_dcp=None):
    """SiO2 pure-quadruplet coordination overrides (the v0.4 lever). Defaults (None)
    give the charge-proportional base (Z_Si=2.7549, Z_O=1.3774, zeta=1.3774) used in
    v0.1-v0.2. Setting z_si / z_o_si / zeta_si independently makes SiO2 non-charge-
    proportional to place the silica-rich miscibility gap. Note: scaling all three by a
    common factor is a gauge no-op; only the RATIOS relative to the MgO quad matter."""
    L = []
    ap = L.append

    # None means the assessed liquid; pass [] for an ideal one
    excess = assessed_excess() if excess is None else excess
    # None: the assessed Mg-Si ordering; False: charge-proportional (no explicit mixed row)
    z_mixed = mgsi_mixed_z() if z_mixed is None else (z_mixed or None)
    ver = version or ("v0.3" if excess else "v0.1")
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
        if name == "MgO" and mgo_liq_dcp is not None:
            ox = dict(ox, dCp_fus=mgo_liq_dcp)
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
        intervals = [(6000.0, coeffs)]
        ap(f" {name}")
        # eq_type=1 (plain Gibbs, no additional terms), n_intervals, then n_el stoich
        ap(f"   1   {len(intervals)}   " + "   ".join(f"{s:.1f}" for s in stoich_el))
        for tmax, cf in intervals:
            ap(_coeff_line(tmax, cf))
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
        # full precision: the row's charge balance holds only to the digits written, and at
        # seven decimals its 1.5e-8 error put pycalphad and the engine 1-2 mJ apart
        ap(f"   1   2   3   3   {zmg_x:.15f}   {zsi_x:.15f}   {zoa_x:.15f}   {zob_x:.15f}")

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
