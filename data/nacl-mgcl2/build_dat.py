"""NaCl-MgCl2 v0.1: the CSP-salt binary's third leg (simple eutectic).

Fourth salt system, and the second with a divalent cation. Liquid SUBQ (Na+1, Mg+2 /
Cl-1) + NaCl and MgCl2 solids, NO intermediate compound. The open literature is split
on whether NaMgCl3 / Na2MgCl4 are stable; the only source that names them (Wang/Villada
2022, FactSage) is validation-target class and is tied to a different eutectic
temperature than the measured one, so v0.1 models the system as the simple eutectic that
the DLR engineering review uses. See PROVENANCE.md.

Endmembers reuse the family values exactly (NaCl from nacl-kcl, MgCl2 from kcl-mgcl2;
both from the workspace Chlorides reference system). Coordination: Z = 6 for both
cations (MQM salt convention, via z_cat), anion Z per pair from charge neutrality
(Cl gets 6 in the Na-Cl pair, 3 in the Mg-Cl pair).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))

from mqmqa import dbbuild
from mqmqa.dbbuild import BinaryExcess, Component, SystemSpec, solid_gibbs_coeffs

NACL = Component(
    name="NaCl", cation="Na", charge=1.0, n_cation=1.0, n_oxygen=1.0,
    dHf=-411412.0, S298=72.132, a=41.1961, b=2.280119e-2, c=2.46588e5,
    Tm=1074.15, dHfus=28200.0, z_cat=6.0,
    source="TKV; Cp own Maier-Kelley fit to Barin 1995 (shared with nacl-kcl)")
MGCL2 = Component(
    name="MgCl2", cation="Mg", charge=2.0, n_cation=1.0, n_oxygen=2.0,
    dHf=-644796.0, S298=89.537, a=76.9, b=8.496e-3, c=-7.463e5,
    Tm=987.0, dHfus=43095.0, z_cat=6.0,
    source="TKV (dHf -644.796 kJ, S298 89.537, Tm 987 K, dHfus 43.095 kJ); Cp R&H "
           "Maier-Kelley model 298-987 K (shared with kcl-mgcl2)")

# Fitted liquid excess (v01_fit.py --fit): Delta_g(Na,Mg)/Cl = LIQ_A00 + LIQ_A10*chi_Na.
LIQ_A00 = -4749.5
LIQ_A10 = -4732.3


def liquid_terms():
    from mqmqa.dbbuild import ExcessTerm
    terms = [ExcessTerm(a=LIQ_A00, b=0.0, p=0, q=0)]
    if LIQ_A10:
        terms.append(ExcessTerm(a=LIQ_A10, b=0.0, p=1, q=0))
    return terms


def _stoich_block(name, dHf, S298, a, b, c, n_na, n_mg):
    A, B, C, D, E, F = solid_gibbs_coeffs(dHf, S298, a, b, c)
    elems = (float(n_na), float(n_mg), float(n_na + 2 * n_mg))     # Na, Mg, Cl
    return [f" {name}",
            "   1   1   " + "   ".join(f"{e:.6f}" for e in elems),
            "  6000.0000   " + "   ".join(f"{v:.12E}" for v in (A, B, C, D, E, F))]


def build(liq_terms=(), out=None):
    spec = SystemSpec(
        "NaCl-MgCl2", [NACL, MGCL2],
        [BinaryExcess("NaCl", "MgCl2", list(liq_terms))] if liq_terms else [],
        version="v0.1",
        provenance="TKV endmembers + DLR 2021 eutectic; simple-eutectic (no double "
                   "salt); see PROVENANCE.md")
    lines = dbbuild.write_dat(spec, anion_sym="Cl", anion_charge=1.0,
                              z_per_charge=6.0, family="molten-salt").splitlines()
    lines[1] = "    3    1    2    2"                # 3 elements, 1 soln, 2 cations, 2 stoich
    lines += _stoich_block("NaCl_solid", NACL.dHf, NACL.S298, NACL.a, NACL.b, NACL.c, 1, 0)
    lines += _stoich_block("MgCl2_solid", MGCL2.dHf, MGCL2.S298, MGCL2.a, MGCL2.b, MGCL2.c, 0, 1)
    path = out or (HERE / "NaCl-MgCl2.dat")
    Path(path).write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


if __name__ == "__main__":
    print("wrote", build(liq_terms=liquid_terms()))
