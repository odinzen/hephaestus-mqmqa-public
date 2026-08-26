"""KCl-MgCl2 v0.1: the CSP-salt binary (liquid SUBQ + KCl, MgCl2, KMgCl3 solids).

Third salt system and the first with a DIVALENT cation. Endmembers from the TKV
evaluation (workspace Chlorides reference system; MgCl2 solid Cp is the ready-made
R&H Maier-Kelley model, 298-987 K). Coordination: Z = 6 for BOTH cations (the MQM salt
convention; the new per-component z_cat override), anion Z per pair from charge
neutrality (Cl gets 3 in the Mg pair, 6 in the K pair).

The double salt KMgCl3 carries Neumann-Kopp S298 and Cp; its formation enthalpy from
the endmember chlorides is FITTED (own-derived) to the measured invariants - Barin has
no K-Mg chloride sheets, so no evaluated compound thermochemistry exists in the
gathered set. The narrow K2MgCl4/K3Mg2Cl7 stability window near the eutectic is not
resolved in v0.1 (documented). See PROVENANCE.md.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))

from mqmqa import dbbuild
from mqmqa.dbbuild import BinaryExcess, Component, SystemSpec, solid_gibbs_coeffs

KCL = Component(
    name="KCl", cation="K", charge=1.0, n_cation=1.0, n_oxygen=1.0,
    dHf=-436558.0, S298=82.55, a=40.5254, b=2.498808e-2, c=2.9839e5,
    Tm=1044.0, dHfus=26317.0, z_cat=6.0,
    source="TKV; Cp own Maier-Kelley fit to Barin 1995 (shared with the other salt systems)")
MGCL2 = Component(
    name="MgCl2", cation="Mg", charge=2.0, n_cation=1.0, n_oxygen=2.0,
    dHf=-644796.0, S298=89.537, a=76.9, b=8.496e-3, c=-7.463e5,
    Tm=987.0, dHfus=43095.0, z_cat=6.0,
    source="TKV (dHf -644.796 kJ, S298 89.537, Tm 987 K, dHfus 43.095 kJ); Cp R&H "
           "Maier-Kelley model 298-987 K (workspace Chlorides reference system)")

# KMgCl3: Neumann-Kopp Cp from the endmember chlorides; formation enthalpy and entropy
# from the endmember chlorides are own-fitted (2026-08-26, four targets: congruent
# 761.65 K, eutectic 697.55 K at x 0.375, and the Xu 2018 eutectic fusion enthalpy
# 17.04 kJ/mol, all reproduced to ~0.3 K / 0.02 kJ). The fitted pair
# says KMgCl3 is ENTROPY-stabilized (dHf_ox -2.9 kJ, dS_ox +26.2 J/K) - the mullite
# pattern; independent solution calorimetry of KMgCl3 would pin the pair separately
# and is the v0.2 refinement.
KMC_DHF_OX = -2859.3
KMC_DS_OX = 26.2
KMC_S298 = KCL.S298 + MGCL2.S298 + KMC_DS_OX
KMC_CP = (KCL.a + MGCL2.a, KCL.b + MGCL2.b, KCL.c + MGCL2.c)

# Fitted liquid excess (v01_fit.py --fit): Delta_g(K,Mg)/Cl = LIQ_A00 + LIQ_A10*chi_K.
LIQ_A00 = -15895.0
LIQ_A10 = -88.5


def liquid_terms():
    from mqmqa.dbbuild import ExcessTerm
    return [ExcessTerm(a=LIQ_A00, b=0.0, p=0, q=0),
            ExcessTerm(a=LIQ_A10, b=0.0, p=1, q=0)]


def _stoich_block(name, dHf, S298, a, b, c, n_k, n_mg):
    A, B, C, D, E, F = solid_gibbs_coeffs(dHf, S298, a, b, c)
    elems = (float(n_k), float(n_mg), float(n_k + 2 * n_mg))     # K, Mg, Cl
    return [f" {name}",
            "   1   1   " + "   ".join(f"{e:.6f}" for e in elems),
            "  6000.0000   " + "   ".join(f"{v:.12E}" for v in (A, B, C, D, E, F))]


def build(dhf_ox_kmc=KMC_DHF_OX, liq_terms=(), out=None):
    spec = SystemSpec(
        "KCl-MgCl2", [KCL, MGCL2],
        [BinaryExcess("KCl", "MgCl2", list(liq_terms))] if liq_terms else [],
        version="v0.1",
        provenance="TKV endmembers + invariants (Perry&Fletcher 1993, Xu 2018); KMgCl3 "
                   "dHf_ox own-fitted; see PROVENANCE.md")
    lines = dbbuild.write_dat(spec, anion_sym="Cl", anion_charge=1.0,
                              z_per_charge=6.0, family="molten-salt").splitlines()
    lines[1] = "    3    1    2    3"
    lines += _stoich_block("KCl_solid", KCL.dHf, KCL.S298, KCL.a, KCL.b, KCL.c, 1, 0)
    lines += _stoich_block("MgCl2_solid", MGCL2.dHf, MGCL2.S298, MGCL2.a, MGCL2.b, MGCL2.c, 0, 1)
    lines += _stoich_block("KMgCl3", KCL.dHf + MGCL2.dHf + dhf_ox_kmc, KMC_S298,
                           *KMC_CP, 1, 1)
    path = out or (HERE / "KCl-MgCl2.dat")
    Path(path).write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


if __name__ == "__main__":
    print("wrote", build(liq_terms=liquid_terms()))
