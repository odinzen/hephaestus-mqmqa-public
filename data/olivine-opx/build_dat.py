"""Write the olivine + orthopyroxene model as one ChemSage SUBL .dat (two CEF phases).

Both are Fe-Mg solid solutions on a two-site metal sublattice:
  OLIVINE        (Mg,Fe)2 (Si)1 (O)4   endmembers forsterite / fayalite
  ORTHOPYROXENE  (Mg,Fe)2 (Si)2 (O)6   endmembers enstatite / ferrosilite (per M2Si2O6)

Endmember Gibbs energies are Robie-Hemingway 1995 (the orthopyroxene ones doubled to the
M2Si2O6 formula so both phases carry two mixing cations). Excess interactions are the
measured enthalpies of mixing: olivine from Wood & Kleppa 1981 (subregular), orthopyroxene
from Chatillon-Colinet 1983 (symmetric, W = 950 cal/MSiO3 = 7949.6 J per M2Si2O6). All
T-independent. Constituents are listed [Fe, Mg] to match pycalphad's alphabetical sort.
See PROVENANCE.md.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "olivine"))
sys.path.insert(0, str(HERE.parents[1] / "cef"))

import endmembers as em
import olivine as ol  # reuse the validated olivine excess (L0, L1)

CAL = 4.184
ELEMENTS = [("FE", 55.845), ("MG", 24.305), ("SI", 28.085), ("O", 15.9994)]

# orthopyroxene excess: Chatillon-Colinet 1983 W = 950 cal/MSiO3 -> per M2Si2O6 (2 cations)
L_OPX = 2.0 * 950.0 * CAL  # 7949.6 J/mol, symmetric, T-independent


def _fmt(x):
    return f"{x:.10E}"


def _endmember_lines(name, coeffs, stoich):
    """A SUBL endmember: name, eq_type/intervals/stoichiometry, one Gibbs interval, and
    the T^0.5 term (if any) as an additional (coeff, exponent) pair."""
    std, sqrt_c = coeffs[:6], coeffs[6]
    eq_type = 4 if sqrt_c != 0.0 else 1
    lines = [f" {name}",
             f"   {eq_type}   1   " + "   ".join(f"{s:.1f}" for s in stoich),
             "   6000.0000   " + "   ".join(_fmt(v) for v in std)]
    if eq_type == 4:
        lines.append(f"   1   {_fmt(sqrt_c)}   {_fmt(0.5)}")
    return lines


def _phase_block(name, endmembers, site_ratios, constituents, em_con_idx, excess_L):
    """One SUBL solution phase. endmembers: list of (species_name, coeffs, stoich).
    excess_L: Redlich-Kister coefficient list on the (Fe,Mg) pair (Si,O pinned)."""
    L = [f" {name}", " SUBL"]
    for sp, coeffs, stoich in endmembers:
        L += _endmember_lines(sp, coeffs, stoich)
    L.append(f"   {len(site_ratios)}")
    L.append("   " + "   ".join(f"{r:.6f}" for r in site_ratios))
    L.append("   " + "   ".join(str(len(c)) for c in constituents))
    for con in constituents:
        L.append("   " + "   ".join(con))
    for row in em_con_idx:
        L.append("   " + "   ".join(str(i) for i in row))
    # excess: interacting linear indices Fe=1, Mg=2 (subl0), Si=3 (subl1), O=4 (subl2)
    L.append("   4   1   2   3   4")
    L.append(f"   {len(excess_L)}")
    for Lv in excess_L:
        L.append("   " + "   ".join(_fmt(v) for v in [Lv, 0, 0, 0, 0, 0]))
    L.append("   0")
    return L


def build():
    fo = em.gibbs_coeffs("forsterite")
    fa = em.gibbs_coeffs("fayalite")
    en2 = [2.0 * c for c in em.gibbs_coeffs("enstatite")]     # Mg2Si2O6
    fs2 = [2.0 * c for c in em.gibbs_coeffs("ferrosilite")]   # Fe2Si2O6

    out = [" Olivine + orthopyroxene (Mg,Fe) CEF - open model, provenance data/olivine-opx/PROVENANCE.md"]
    out.append(f"   {len(ELEMENTS)}   2   2   2   0")  # n_el, n_soln, counts [2,2], n_stoich
    out.append("   " + "   ".join(e[0] for e in ELEMENTS))
    out.append("   " + "   ".join(f"{m:.6f}" for _, m in ELEMENTS))
    out.append("   6   1   2   3   4   5   6")
    out.append("   6   1   2   3   4   5   6")

    # OLIVINE (Mg,Fe)2 (Si)1 (O)4
    out += _phase_block(
        "OLIVINE",
        [("FAYALITE", fa, [2.0, 0.0, 1.0, 4.0]),
         ("FORSTERITE", fo, [0.0, 2.0, 1.0, 4.0])],
        [2.0, 1.0, 4.0], [["FE", "MG"], ["SI"], ["O"]],
        [[1, 2], [1, 1], [1, 1]],
        [ol.L0, ol.L1])

    # ORTHOPYROXENE (Mg,Fe)2 (Si)2 (O)6
    out += _phase_block(
        "ORTHOPYROXENE",
        [("FE2SI2O6", fs2, [2.0, 0.0, 2.0, 6.0]),
         ("MG2SI2O6", en2, [0.0, 2.0, 2.0, 6.0])],
        [2.0, 2.0, 6.0], [["FE", "MG"], ["SI"], ["O"]],
        [[1, 2], [1, 1], [1, 1]],
        [L_OPX])

    return "\n".join(out) + "\n"


if __name__ == "__main__":
    out = HERE / "Olivine-Opx-CEF.dat"
    out.write_text(build(), encoding="ascii")
    print(f"wrote {out}")
    print(f"L_opx (Chatillon-Colinet, per M2Si2O6) = {L_OPX:.1f} J/mol")
