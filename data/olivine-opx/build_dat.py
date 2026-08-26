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

# Assessed high-T entropy correction on the enstatite (Mg2Si2O6) endmember: a second
# Gibbs interval above the break adding dG = ENSTATITE_HT_B*(T - T_BREAK) J per formula
# (continuous at the break). Two measured constraints pin it: the forsterite+liquid ->
# enstatite peritectic at 1830 K needs dG(1830) = 18.014*(1830-1000) = 14951.6 J (the
# original calibration), and the measured near-ideal olivine/opx Fe-Mg exchange at
# <= 1273 K needs NO correction there (a 1000 K onset broke K_D at 1273 K when the
# term moved into the database). The break sits at the ortho -> proto-enstatite
# transition, ~1360 K, the physical onset of the extra entropy; the slope follows.
# NOT an extrapolation repair: capping the R&H Cp fit at its 1000 K value was tested
# and supplies only ~40% of the correction with the wrong T-shape. own_derived
# assessment parameter, documented in PROVENANCE.md.
ENSTATITE_T_BREAK = 1360.0
ENSTATITE_HT_B = 18.014 * (1830.0 - 1000.0) / (1830.0 - ENSTATITE_T_BREAK)


def _fmt(x):
    return f"{x:.10E}"


def _endmember_lines(name, coeffs, stoich, ht_break=None, ht_dA=0.0, ht_dB=0.0):
    """A SUBL endmember: name, eq_type/intervals/stoichiometry, Gibbs interval(s), and
    the T^0.5 term (if any) as an additional (coeff, exponent) pair per interval.
    ht_break splits the function at that temperature; the upper interval's constant and
    linear coefficients are offset by ht_dA/ht_dB."""
    std, sqrt_c = coeffs[:6], coeffs[6]
    eq_type = 4 if sqrt_c != 0.0 else 1
    intervals = ([(6000.0, std)] if ht_break is None else
                 [(ht_break, std),
                  (6000.0, [std[0] + ht_dA, std[1] + ht_dB] + list(std[2:]))])
    lines = [f" {name}",
             f"   {eq_type}   {len(intervals)}   " + "   ".join(f"{s:.1f}" for s in stoich)]
    for t_max, cf in intervals:
        lines.append(f"   {t_max:.4f}   " + "   ".join(_fmt(v) for v in cf))
        if eq_type == 4:
            lines.append(f"   1   {_fmt(sqrt_c)}   {_fmt(0.5)}")
    return lines


def _phase_block(name, endmembers, site_ratios, constituents, em_con_idx, excess_L):
    """One SUBL solution phase. endmembers: list of (species_name, coeffs, stoich[, kwargs]).
    excess_L: Redlich-Kister coefficient list on the (Fe,Mg) pair (Si,O pinned)."""
    L = [f" {name}", " SUBL"]
    for sp, coeffs, stoich, *kw in endmembers:
        L += _endmember_lines(sp, coeffs, stoich, **(kw[0] if kw else {}))
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
         ("MG2SI2O6", en2, [0.0, 2.0, 2.0, 6.0],
          dict(ht_break=ENSTATITE_T_BREAK,
               ht_dA=-ENSTATITE_HT_B * ENSTATITE_T_BREAK, ht_dB=ENSTATITE_HT_B))],
        [2.0, 2.0, 6.0], [["FE", "MG"], ["SI"], ["O"]],
        [[1, 2], [1, 1], [1, 1]],
        [L_OPX])

    return "\n".join(out) + "\n"


if __name__ == "__main__":
    out = HERE / "Olivine-Opx-CEF.dat"
    out.write_text(build(), encoding="ascii")
    print(f"wrote {out}")
    print(f"L_opx (Chatillon-Colinet, per M2Si2O6) = {L_OPX:.1f} J/mol")
