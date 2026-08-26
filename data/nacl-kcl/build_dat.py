"""NaCl-KCl v0.1: open salt database with a SOLID SOLUTION (liquid SUBQ + halite CEF).

The system's diagram is a liquidus minimum over a continuous (Na,K)Cl halite solution
with a low-temperature solvus - no eutectic, no stoichiometric compounds. Endmembers
from the TKV evaluation (workspace Chlorides reference system); solid Cp own
Maier-Kelley fits to Barin points. The liquid excess is fitted to the measured
Hersh & Kleppa (1965) mixing enthalpy; the halite excess to the evaluated solvus
consolute. The Sangster & Pelton liquidus minimum is a pure validation target.
See PROVENANCE.md.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))

from mqmqa import dbbuild
from mqmqa.dbbuild import BinaryExcess, Component, ExcessTerm, SystemSpec, solid_gibbs_coeffs

R = 8.3145

NACL = Component(
    name="NaCl", cation="Na", charge=1.0, n_cation=1.0, n_oxygen=1.0,
    dHf=-411412.0, S298=72.132, a=41.1961, b=2.280119e-2, c=2.46588e5,
    Tm=1074.15, dHfus=28200.0,
    source="TKV (dHf -411.412 kJ, S298 72.132, Tm 1074.15 K, dHfus 28.2 kJ); Cp own "
           "Maier-Kelley fit to Barin 1995 solid points 298-1000 K (max resid 0.63)")
KCL = Component(
    name="KCl", cation="K", charge=1.0, n_cation=1.0, n_oxygen=1.0,
    dHf=-436558.0, S298=82.55, a=40.5254, b=2.498808e-2, c=2.9839e5,
    Tm=1044.0, dHfus=26317.0,
    source="TKV; Cp own Maier-Kelley fit to Barin 1995 solid points 298-1000 K "
           "(same endmember as the LiCl-KCl system)")

# Halite (Na,K)Cl regular-solution excess from the evaluated solvus consolute
# (Sangster & Pelton 1987: 768.15 K): T_c = W/2R for one ideally-mixing site.
T_CONSOLUTE = 768.15
W_HALITE = 2.0 * R * T_CONSOLUTE           # 12773.6 J/mol


def _fmt(x):
    return f"{x:.10E}"


def _halite_block():
    """SUBL block: (Na,K)1 (Cl)1, constituents name-sorted [K, NA] for pycalphad."""
    gk = solid_gibbs_coeffs(KCL.dHf, KCL.S298, KCL.a, KCL.b, KCL.c)
    gn = solid_gibbs_coeffs(NACL.dHf, NACL.S298, NACL.a, NACL.b, NACL.c)
    L = [" HALITE", " SUBL"]
    for name, cf, stoich in (("KCL_S", gk, [0.0, 1.0, 1.0]),
                             ("NACL_S", gn, [1.0, 0.0, 1.0])):
        L.append(f" {name}")
        L.append("   1   1   " + "   ".join(f"{s:.1f}" for s in stoich))
        L.append("   6000.0000   " + "   ".join(_fmt(v) for v in cf))
    L.append("   2")                                    # 2 sublattices
    L.append("   1.000000   1.000000")                  # site ratios
    L.append("   2   1")                                # constituents per sublattice
    L.append("   K   NA")
    L.append("   CL")
    L.append("   1   2")                                # endmember constituent rows
    L.append("   1   1")
    L.append("   3   1   2   3")                        # excess: K,Na mix (subl 1), Cl pinned
    L.append("   1")
    L.append("   " + "   ".join(_fmt(v) for v in [W_HALITE, 0, 0, 0, 0, 0]))
    L.append("   0")
    return L


def build(liq_terms=(), out=None):
    spec = SystemSpec(
        "NaCl-KCl", [NACL, KCL],
        [BinaryExcess("NaCl", "KCl", list(liq_terms))] if liq_terms else [],
        version="v0.1",
        provenance="H&K 1965 mixing enthalpy (liquid) + evaluated solvus consolute "
                   "(halite); liquidus minimum is validation only; see PROVENANCE.md")
    lines = dbbuild.write_dat(spec, anion_sym="Cl", anion_charge=1.0,
                              z_per_charge=6.0).splitlines()
    lines[1] = "    3    2    2    2    0"   # 3 elements, 2 solutions (2 cations, 2 subl-consts), 0 stoich
    lines += _halite_block()
    path = out or (HERE / "NaCl-KCl.dat")
    Path(path).write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


if __name__ == "__main__":
    print("wrote", build())
