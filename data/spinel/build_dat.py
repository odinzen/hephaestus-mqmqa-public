"""Write spinel-hercynite (Mg,Fe)Al2O4 as a ChemSage SUBL .dat (one CEF phase).

  SPINEL  (Mg,Fe)1 (Al)2 (O)4   endmembers spinel MgAl2O4 / hercynite FeAl2O4

Normal-spinel model: Fe and Mg mix on the tetrahedral A-site, Al is fixed on the
octahedral B-site. Endmember Gibbs from data/spinel/endmembers.py. The (Fe,Mg) excess is
MLIP-triangulated (MatterSim, data/spinel/_mlip): a small negative, asymmetric excess
(favourable mixing, no miscibility gap). The normal/inverse cation inversion is a v0.2
study. Constituents are listed [Fe, Mg] to match pycalphad's alphabetical sort.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

_spec = importlib.util.spec_from_file_location("spinel_endmembers", HERE / "endmembers.py")
em = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(em)

ELEMENTS = [("FE", 55.845), ("MG", 24.305), ("AL", 26.982), ("O", 15.9994)]
# MLIP-triangulated (Fe,Mg) A-site excess (data/spinel/_mlip/fit): RK on (y_Fe - y_Mg).
L0 = -3411.1
L1 = -2373.3


def _fmt(x):
    return f"{x:.10E}"


def _endmember_lines(name, coeffs, stoich):
    std = coeffs[:6]
    return [f" {name}",
            f"   1   1   " + "   ".join(f"{s:.1f}" for s in stoich),
            "   6000.0000   " + "   ".join(_fmt(v) for v in std)]


def _phase_block(name, endmembers, site_ratios, constituents, em_con_idx, excess_L):
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
    n_con = sum(len(c) for c in constituents)
    L.append("   " + "   ".join(str(i) for i in [n_con] + list(range(1, n_con + 1))))
    L.append(f"   {len(excess_L)}")
    for Lv in excess_L:
        L.append("   " + "   ".join(_fmt(v) for v in (Lv, 0, 0, 0, 0, 0)))
    L.append("   0")
    return L


def build(out=None):
    sp = em.gibbs_coeffs("spinel")        # MgAl2O4
    hc = em.gibbs_coeffs("hercynite")     # FeAl2O4
    lines = [" Spinel-hercynite (Mg,Fe)Al2O4 CEF - open model, provenance "
             "data/spinel/PROVENANCE.md",
             f"   {len(ELEMENTS)}   1   2   0",
             "   " + "   ".join(e[0] for e in ELEMENTS),
             "   " + "   ".join(f"{m:.6f}" for _, m in ELEMENTS),
             "   6   1   2   3   4   5   6",
             "   6   1   2   3   4   5   6"]
    lines += _phase_block(
        "SPINEL",
        [("HERCYNITE", hc, [1.0, 0.0, 2.0, 4.0]),     # Fe,Mg,Al,O
         ("SPINEL_MG", sp, [0.0, 1.0, 2.0, 4.0])],
        [1.0, 2.0, 4.0], [["FE", "MG"], ["AL"], ["O"]],
        [[1, 2], [1, 1], [1, 1]],
        [L0, L1])
    path = out or (HERE / "Spinel-CEF.dat")
    Path(path).write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


if __name__ == "__main__":
    print("wrote", build())
