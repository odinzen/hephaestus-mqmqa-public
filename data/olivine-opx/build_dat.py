"""Write the olivine + orthopyroxene model as one ChemSage SUBL .dat (two CEF phases).

  OLIVINE        (Mg,Fe)2 (Si)1 (O)4               endmembers forsterite / fayalite
  ORTHOPYROXENE  (Mg,Fe)[M1] (Mg,Fe)[M2] Si2 O6    enstatite / ferrosilite and the two
                                                    mixed-site endmembers (orthopyroxene.py)

Olivine: Robie-Hemingway 1995 endmembers with the Wood & Kleppa 1981 subregular excess.
Orthopyroxene: the assessed two-site model (Fe-Mg order between M1 and M2) written by
orthopyroxene.subl_block. Constituents are listed [Fe, Mg] to match pycalphad's
alphabetical sort. See PROVENANCE.md.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "olivine"))
sys.path.insert(0, str(HERE.parents[1] / "cef"))

import endmembers as em
import olivine as ol  # reuse the validated olivine excess (L0, L1)
import orthopyroxene as opx

ELEMENTS = [("FE", 55.845), ("MG", 24.305), ("SI", 28.085), ("O", 15.9994)]


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

    out = [" Olivine + orthopyroxene (Mg,Fe) CEF - open model, provenance data/olivine-opx/PROVENANCE.md"]
    out.append(f"   {len(ELEMENTS)}   2   2   {len(opx.ENDMEMBERS)}   0")  # n_el, n_soln, counts [ol, opx], n_stoich
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

    # ORTHOPYROXENE (Mg,Fe)[M1] (Mg,Fe)[M2] (Si)2 (O)6: the two-site model of orthopyroxene.py
    out += opx.subl_block([e for e, _ in ELEMENTS])

    return "\n".join(out) + "\n"


if __name__ == "__main__":
    out = HERE / "Olivine-Opx-CEF.dat"
    out.write_text(build(), encoding="ascii")
    print(f"wrote {out}")
