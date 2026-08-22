"""CaO-SiO2 binary phase diagram from the v0.2 liquid + open solid Gibbs functions.

This is the first multi-phase-equilibrium prototype: the stable state at each
(composition, temperature) is the lower convex hull (common-tangent construction)
of the liquid G(x) curve - computed from the v0.2 MQMQA engine - together with the
fixed-composition solid oxides and Ca-silicates. Sweeping temperature traces the
liquidus and the invariants (congruent melting points, eutectics).

Solid Gibbs energies are built by Neumann-Kopp on our OWN CaO and SiO2(cristobalite)
solid endmembers plus the compound's measured enthalpy and entropy of formation from
the oxides, so every solid sits on exactly the engine's endmember scale:

    G_compound(T) = n_CaO * G_CaO_solid(T) + n_SiO2 * G_SiO2_solid(T)
                    + dHf_ox - T * dSf_ox
    dSf_ox = S298_compound - n_CaO*S298_CaO - n_SiO2*S298_SiO2      (per formula)

with dHf_ox on the cristobalite reference (Abdul reports it vs alpha-quartz; the
small quartz->cristobalite enthalpy shift converts it). Neumann-Kopp (dCp_ox = 0) is
the standard, good approximation for silicate compounds; solid-solid polymorph
transitions are not yet resolved (a documented refinement, see notes).

Open sources (all measured/evaluated, no TDB parameters):
  - CaO, SiO2 endmembers: as in build_dat.py (Robie-Hemingway 1995, NIST-JANAF).
  - Compound dHf_ox(298), measured: Abdul et al. 2023, Cement & Concrete Research 174,
    107039 (CC-BY), Table A.2 (experimental fit dataset, primary calorimetry).
  - Compound S298: Abdul 2023 Table 7 (Haas et al. evaluated).
  - Pseudowollastonite fusion (Tm=1817 K, dHfus=57300 J/mol): Abdul 2023 Table 9
    (Adamkovicova 1980).  Published invariants for validation: Abdul 2023 Table 9.
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "python"))

import mqmqa
from mqmqa import equilibrium as eq
import build_dat as bd
import _activity as act

T0 = 298.15
S298_CAO, S298_SIO2 = bd.OXIDES["CaO"]["S298"], bd.OXIDES["SiO2"]["S298"]

# alpha-quartz -> cristobalite enthalpy shift (our SiO2 endmember is cristobalite;
# Abdul's dHf_ox is vs alpha-quartz). dHf(cristobalite) - dHf(quartz) ~ +2300 J/mol,
# so forming a compound from cristobalite releases 2300 J/mol-SiO2 more heat.
DHF_QZ_TO_CRIST = -2300.0


def solid_oxide_gibbs(ox, T):
    """Pure solid oxide Gibbs per formula unit (H - T*S from the R&H/JANAF Cp)."""
    a, b, c = ox["a"], ox["b"], ox["c"]
    H = ox["dHf"] + a * (T - T0) + 0.5 * b * (T * T - T0 * T0) - c * (1.0 / T - 1.0 / T0)
    S = (ox["S298"] + a * np.log(T / T0) + b * (T - T0)
         - 0.5 * c * (1.0 / (T * T) - 1.0 / (T0 * T0)))
    return H - T * S


# Solid phases: name -> (n_CaO, n_SiO2, dHf_ox_quartz[J/mol], S298[J/mol/K], note).
# x_SiO2 of the compound = n_SiO2 / (n_CaO + n_SiO2); formula units = n_CaO + n_SiO2.
SOLIDS = {
    "CaO(lime)":            (1, 0,        0.0,  S298_CAO, "endmember"),
    "SiO2(cristobalite)":   (0, 1,        0.0,  S298_SIO2, "endmember"),
    "CS(pseudowoll)":       (1, 1,   -81922.72, 85.2,  "cyclowollastonite; S298~woll+dStrans"),
    "C3S2(rankinite)":      (3, 2,  -229136.76, 210.6, "rankinite"),
    "C2S(gamma)":           (2, 1,  -136816.80, 120.5, "gamma-C2S; high-T alpha not resolved"),
    "C3S":                  (3, 1,  -112884.32, 168.6, "triclinic-C3S; stable ~1250-2070 C"),
}


def solid_gibbs_per_formula_unit(name, T):
    """Solid Gibbs per mole of OXIDE FORMULA UNIT (so it plots on the same x-G axes
    as the liquid), and its x_SiO2."""
    n_cao, n_sio2, dHf_ox_qz, S298, _ = SOLIDS[name]
    nunits = n_cao + n_sio2
    x = n_sio2 / nunits
    dHf_ox = dHf_ox_qz + DHF_QZ_TO_CRIST * n_sio2  # to cristobalite reference
    dSf_ox = S298 - n_cao * S298_CAO - n_sio2 * S298_SIO2
    g = (n_cao * solid_oxide_gibbs(bd.OXIDES["CaO"], T)
         + n_sio2 * solid_oxide_gibbs(bd.OXIDES["SiO2"], T)
         + dHf_ox - T * dSf_ox)
    return g / nunits, x


def liquid_gibbs_per_formula_unit(inp, x, T):
    """Absolute liquid Gibbs per mole of oxide formula unit at x_SiO2."""
    g_cao = act.g_pure_liquid(inp, "CaO")
    g_sio2 = act.g_pure_liquid(inp, "SiO2")
    return act.delta_g_mix(inp, x) + (1 - x) * g_cao + x * g_sio2


def _load():
    db = mqmqa.Database.read(str(HERE / "CaO-SiO2-liquid.dat"))
    p = db.phase_index("CAO-SIO2-LIQUID")
    return db, p


def congruent_melting(inp, name, T_lo=1400.0, T_hi=2600.0):
    """T where liquid at the compound composition equals the solid (bisection on
    G_liq - G_solid, both per formula unit)."""
    _n_cao, n_sio2, _, _, _ = SOLIDS[name]
    x = n_sio2 / (SOLIDS[name][0] + n_sio2)

    def f(T):
        gs, _ = solid_gibbs_per_formula_unit(name, T)
        return liquid_gibbs_per_formula_unit(inp, x, T) - gs

    lo, hi = T_lo, T_hi
    if f(lo) * f(hi) > 0:
        return None
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        (lo, hi) = (mid, hi) if f(lo) * f(mid) > 0 else (lo, mid)
    return 0.5 * (lo + hi)


def _dgfus_oxide(ox, T):
    return ox["dHfus"] * (1.0 - T / ox["Tm"])


def diagnose(db, p, name, Tm_pub):
    """At the published melting T, decompose G_liq - G_solid (per oxide formula unit)
    into the liquid mixing term, the pure-oxide fusion terms, and the compound
    formation term, to locate any inconsistency."""
    n_cao, n_sio2, dHf_ox_qz, S298, _ = SOLIDS[name]
    nunits = n_cao + n_sio2
    x = n_sio2 / nunits
    inp = eq.build_inputs(db, p, Tm_pub, components=["CA", "SI", "O"])

    gl = liquid_gibbs_per_formula_unit(inp, x, Tm_pub)
    gs, _ = solid_gibbs_per_formula_unit(name, Tm_pub)
    gap = gl - gs  # >0 means solid too stable / liquid won't melt

    dGmix = act.delta_g_mix(inp, x)  # per unit, liquid ref
    dgfus_ca = _dgfus_oxide(bd.OXIDES["CaO"], Tm_pub)
    dgfus_si = _dgfus_oxide(bd.OXIDES["SiO2"], Tm_pub)
    dHf_ox = dHf_ox_qz + DHF_QZ_TO_CRIST * n_sio2
    dSf_ox = S298 - n_cao * S298_CAO - n_sio2 * S298_SIO2
    dGf_ox = (dHf_ox - Tm_pub * dSf_ox) / nunits  # per unit

    # liquid ref -> solid-oxide ref for the melt (per unit)
    dGmix_solidref = dGmix + (n_cao / nunits) * dgfus_ca + (n_sio2 / nunits) * dgfus_si
    print(f"\n  {name}  (x_SiO2={x:.3f}, published Tm={Tm_pub:.0f} K)")
    print(f"    G_liq - G_solid at Tm = {gap:+8.0f} J/mol-unit  "
          f"({'liquid too UNstable; no melting' if gap > 0 else 'melts'})")
    print(f"    liquid mixing (liq ref)         dGmix       = {dGmix:8.0f}")
    print(f"    -> as solid-oxide ref           dGmix_sox   = {dGmix_solidref:8.0f}")
    print(f"    compound formation from oxides  dGf_ox      = {dGf_ox:8.0f}")
    print(f"    (for melting, dGmix_sox should ~equal dGf_ox; gap = "
          f"{dGmix_solidref - dGf_ox:+.0f})")


if __name__ == "__main__":
    db, p = _load()
    print("Solid phases and their compositions:")
    for name, (nc, ns, dHfq, S, note) in SOLIDS.items():
        x = ns / (nc + ns)
        print(f"  {name:20s} x_SiO2={x:.3f}  dHf_ox(qz)={dHfq:9.0f}  S298={S:6.1f}  [{note}]")

    print("\n" + "=" * 70)
    print("CONSISTENCY DIAGNOSIS at the published melting points")
    print("=" * 70)
    for name, Tm in (("CS(pseudowoll)", 1817.0), ("C2S(gamma)", 2403.0)):
        diagnose(db, p, name, Tm)
    print("\n  Reading: the liquid (from the v0.2 activity fit) is far less stable than")
    print("  the calorimetric compounds at their melting points, so nothing melts. The")
    print("  gap traces to the flagged CaO liquid endmember (Tm=3200 K -> large dgfus_CaO)")
    print("  and to the Stolyarova reference-state assumption (liquid vs solid oxide),")
    print("  which together set how deep the liquid mixing energy really is.")
