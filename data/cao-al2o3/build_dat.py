"""CaO-Al2O3 v0.1: open literature-only database (liquid SUBQ + 6 stoichiometric solids).

Liquid components CaO and AlO1.5 (per-cation basis, charge-neutral units; AlO1.5 carries half
the Al2O3 thermodynamics). Compound enthalpies from measured formation-from-oxides values on
CODATA/JANAF endmembers; entropies Barin (1995); Cp Maier-Kelley (Bonnickson 1955 drop
calorimetry for CA; workspace fits to Barin points for C3A/C12A7/CA2). Invariant targets are
Rankin & Wright (1915). Full provenance in PROVENANCE.md.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))

from mqmqa import dbbuild
from mqmqa.dbbuild import BinaryExcess, Component, ExcessTerm, SystemSpec, solid_gibbs_coeffs

CAO = dbbuild.starter_component("CaO")

# Corundum solid (per mole Al2O3): dHf TKV/JANAF/CODATA -1675.692 kJ; S298 CODATA 50.92;
# Cp Kelley J-based Maier-Kelley (Cp298 = 79.09 vs Barin 79.038). Fusion: Barin (1995)
# corundum sheet (= JANAF): Tm 2327 K, dHfus 111.085 kJ/mol.
AL2O3_SOLID = dict(dHf=-1675692.0, S298=50.92, a=115.0182, b=0.01179888, c=-3.50619e6)
ALO15 = Component(
    name="AlO1.5", cation="Al", charge=3.0, n_cation=1.0, n_oxygen=1.5,
    dHf=AL2O3_SOLID["dHf"] / 2, S298=AL2O3_SOLID["S298"] / 2,
    a=AL2O3_SOLID["a"] / 2, b=AL2O3_SOLID["b"] / 2, c=AL2O3_SOLID["c"] / 2,
    Tm=2327.0, dHfus=111085.0 / 2,
    source="dHf TKV/CODATA; S298 CODATA; Cp Kelley (J Maier-Kelley); fusion Barin 1995 "
           "corundum sheet (=JANAF): 2327 K, 111.085 kJ/mol Al2O3; all halved to AlO1.5")

# Stoichiometric solids. dHf assembled as sum(oxide dHf) + measured dHf_ox:
#   C3A, C12A7, CA dHf_ox: Coughlin 1956 (solution calorimetry; -6.65, -79.37, -15.44 kJ/mol)
#   CA2 dHf_ox: Geiger 1988 Eqn (2)/Table 2 (-25.6 kJ/mol; his Eqn (3) alt -20.9, Barin -39.3)
#   (consistency: Coughlin's element-basis values use 1956 oxide enthalpies; from-oxide values
#    on CODATA endmembers land within 0.5 kJ of Barin's element-basis sheets)
# S298: Barin 1995 (C3A p.445, CA2 p.443, CA p.443-adjacent sheet, C12A7 sheet)
# Cp Maier-Kelley (a + b*T + c*T^-2, J/mol/K):
#   CA: Bonnickson 1955 heat-content fit converted cal->J (Cp298 120.6 vs Barin 120.791)
#   C3A/C12A7/CA2: workspace least-squares fits to Barin Cp points (nominal 298-1000 K)
_D = dict
SOLIDS = {
    # name: (n_CaO_units, n_AlO15_units, coeff dict per formula)
    "CaO_solid": (1, 0, _D(dHf=-635100.0, S298=38.1, a=51.85, b=2.444e-3, c=-9.340e5)),
    "Al2O3_corundum": (0, 2, AL2O3_SOLID),
    "Ca3Al2O6": (3, 2, _D(dHf=3 * -635100.0 + -1675692.0 + -6650.0, S298=205.899,
                          a=255.89493, b=0.03133642, c=-4.937217061e6)),
    "Ca12Al14O33": (12, 14, _D(dHf=12 * -635100.0 + 7 * -1675692.0 + -79370.0, S298=1046.837,
                               a=1263.401703, b=0.27405094, c=-2.3137622161e7)),
    "CaAl2O4": (1, 2, _D(dHf=-635100.0 + -1675692.0 + -15440.0, S298=114.223,
                         a=150.624, b=0.02493866, c=-3.330464e6)),
    "CaAl4O7": (1, 4, _D(dHf=-635100.0 + 2 * -1675692.0 + -25600.0, S298=177.820,
                         a=258.235022, b=0.04008426, c=-6.401403508e6)),
}


def solid_x_and_units(name):
    """(x_AlO15, cation units per formula) for a solid's position on the join."""
    n_ca, n_al, _ = SOLIDS[name]
    return n_al / (n_ca + n_al), n_ca + n_al


def _stoich_block(name, coeffs, n_ca, n_al):
    """ChemSage stoichiometric block, Gibbs eq. type 1 (elements Ca, Al, O order)."""
    A, B, C, D, E, F = solid_gibbs_coeffs(coeffs["dHf"], coeffs["S298"],
                                          coeffs["a"], coeffs["b"], coeffs["c"])
    elems = (float(n_ca), float(n_al), float(n_ca + 1.5 * n_al))
    return [f" {name}",
            "   1   1   " + "   ".join(f"{e:.6f}" for e in elems),
            "  6000.0000   " + "   ".join(f"{v:.12E}" for v in (A, B, C, D, E, F))]


def build(terms=(), out=None):
    """Write the .dat with the given liquid ExcessTerms; returns the path."""
    spec = SystemSpec(
        "CaO-AlO1.5", [CAO, ALO15],
        [BinaryExcess("CaO", "AlO1.5", list(terms))] if terms else [],
        version="v0.1",
        provenance="Rankin&Wright 1915 invariants + Coughlin 1956/Geiger 1988 calorimetry "
                   "+ Barin 1995/CODATA endmembers; see PROVENANCE.md")
    lines = dbbuild.write_dat(spec).splitlines()
    lines[1] = "    3    1    2    6"      # 3 elements, 1 solution (2 cations), 6 stoich solids
    for name, (n_ca, n_al, coeffs) in SOLIDS.items():
        lines += _stoich_block(name, coeffs, n_ca, n_al)
    path = out or (HERE / "CaO-Al2O3.dat")
    Path(path).write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


if __name__ == "__main__":
    print("wrote", build())
