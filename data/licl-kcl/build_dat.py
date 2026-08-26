"""LiCl-KCl v0.1: open literature-only molten-salt database (SUBQ liquid + 2 solids).

First non-oxide system in the open family: common anion Cl (charge 1). Endmember
thermochemistry from the TKV evaluation (dHf, S298, Cp298, Tm, dHfus; the assessment
workspace's Chlorides reference system); solid Cp as own Maier-Kelley fits to Barin (1995)
points over each solid's stable range (LiCl 298-800 K max resid 0.011, KCl 298-1000 K
max resid 0.097 J/mol/K). Eutectic target from the pyroprocessing literature; see
PROVENANCE.md, including the INL report's mol/wt fraction slip.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))

from mqmqa import dbbuild
from mqmqa.dbbuild import BinaryExcess, Component, SystemSpec, solid_gibbs_coeffs

LICL = Component(
    name="LiCl", cation="Li", charge=1.0, n_cation=1.0, n_oxygen=1.0,   # n_oxygen = anions
    dHf=-408358.0, S298=59.287, a=43.6024, b=2.071321e-2, c=-1.5510e5,
    Tm=883.0, dHfus=19748.0,
    source="TKV (dHf -408.358 kJ, S298 59.287, Tm 883 K, dHfus 19.748 kJ); Cp own "
           "Maier-Kelley fit to Barin 1995 solid points 298-800 K")
KCL = Component(
    name="KCl", cation="K", charge=1.0, n_cation=1.0, n_oxygen=1.0,
    dHf=-436558.0, S298=82.55, a=40.5254, b=2.498808e-2, c=2.9839e5,
    Tm=1044.0, dHfus=26317.0,
    source="TKV (dHf -436.558 kJ, S298 82.55, Tm 1044 K, dHfus 26.317 kJ); Cp own "
           "Maier-Kelley fit to Barin 1995 solid points 298-1000 K")

SOLIDS = {
    # name: (component, x_KCl position)
    "LiCl_solid": (LICL, 0.0),
    "KCl_solid": (KCL, 1.0),
}


def _stoich_block(name, comp):
    """ChemSage stoichiometric block (elements Li, K, Cl order)."""
    A, B, C, D, E, F = solid_gibbs_coeffs(comp.dHf, comp.S298, comp.a, comp.b, comp.c)
    elems = (1.0 if comp.cation == "Li" else 0.0, 1.0 if comp.cation == "K" else 0.0, 1.0)
    return [f" {name}",
            "   1   1   " + "   ".join(f"{e:.6f}" for e in elems),
            "  6000.0000   " + "   ".join(f"{v:.12E}" for v in (A, B, C, D, E, F))]


def build(terms=(), out=None):
    spec = SystemSpec(
        "LiCl-KCl", [LICL, KCL],
        [BinaryExcess("LiCl", "KCl", list(terms))] if terms else [],
        version="v0.1",
        provenance="TKV/Barin endmembers + eutectic from the pyroprocessing literature; "
                   "see PROVENANCE.md")
    # Z = 6 is the published MQM convention for monovalent molten salts; the oxide
    # charge-proportional Z could not reproduce the eutectic COMPOSITION at any excess
    # (x_KCl pinned near 0.458 vs measured 0.415) - see PROVENANCE.md.
    lines = dbbuild.write_dat(spec, anion_sym="Cl", anion_charge=1.0,
                              z_per_charge=6.0).splitlines()
    lines[1] = "    3    1    2    2"      # 3 elements, 1 solution (2 cations), 2 stoich solids
    for name, (comp, _x) in SOLIDS.items():
        lines += _stoich_block(name, comp)
    path = out or (HERE / "LiCl-KCl.dat")
    Path(path).write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


if __name__ == "__main__":
    print("wrote", build())
