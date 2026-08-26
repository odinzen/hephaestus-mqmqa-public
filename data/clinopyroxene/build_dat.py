"""Write clinopyroxene (diopside-hedenbergite) as a ChemSage SUBL .dat (one CEF phase).

  CLINOPYROXENE  (Ca)1 (Mg,Fe)1 (Si)2 (O)6   endmembers diopside / hedenbergite

The Ca, Si and O sublattices are fixed; only the M1 (Mg,Fe) sublattice mixes. Endmember
Gibbs energies are Robie-Hemingway 1995 (data/clinopyroxene/endmembers.py). v0.1 is IDEAL
mixing on the M1 sublattice (Redlich-Kister L0 = 0): no open diopside-hedenbergite mixing
calorimetry exists, so the configurational entropy is the only non-endmember term. A
measured excess (and the low-T di-hed solvus it implies) is the v0.2 refinement, from a
targeted open-data pull. Constituents are listed [Fe, Mg] to match pycalphad's
alphabetical sort. See PROVENANCE.md.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Load the endmember module by path under a unique name (a bare import collides with the
# other systems' modules in the shared test process).
_spec = importlib.util.spec_from_file_location("cpx_endmembers", HERE / "endmembers.py")
em = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(em)

ELEMENTS = [("CA", 40.078), ("FE", 55.845), ("MG", 24.305), ("SI", 28.085), ("O", 15.9994)]
L0 = 0.0   # ideal (Fe,Mg) mixing; a measured excess is the v0.2 refinement


def _fmt(x):
    return f"{x:.10E}"


def _endmember_lines(name, coeffs, stoich):
    std, sqrt_c = coeffs[:6], coeffs[6]
    eq_type = 4 if sqrt_c != 0.0 else 1
    lines = [f" {name}",
             f"   {eq_type}   1   " + "   ".join(f"{s:.1f}" for s in stoich),
             "   6000.0000   " + "   ".join(_fmt(v) for v in std)]
    if eq_type == 4:
        lines.append(f"   1   {_fmt(sqrt_c)}   {_fmt(0.5)}")
    return lines


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
    # excess: every constituent gets a sequential global index; the reader finds the one
    # sublattice with two listed (the mixing pair) and pins the rest.
    n_con = sum(len(c) for c in constituents)
    L.append("   " + "   ".join(str(i) for i in [n_con] + list(range(1, n_con + 1))))
    L.append(f"   {len(excess_L)}")
    for Lv in excess_L:
        L.append("   " + "   ".join(_fmt(v) for v in (Lv, 0, 0, 0, 0, 0)))
    L.append("   0")
    return L


def build(out=None):
    di = em.gibbs_coeffs("diopside")       # CaMgSi2O6
    hd = em.gibbs_coeffs("hedenbergite")   # CaFeSi2O6
    lines = [" Clinopyroxene (Ca)(Mg,Fe)(Si2O6) CEF - open model, provenance "
             "data/clinopyroxene/PROVENANCE.md",
             f"   {len(ELEMENTS)}   1   2   0",     # n_el, n_soln=1, mixing count=2, n_stoich=0
             "   " + "   ".join(e[0] for e in ELEMENTS),
             "   " + "   ".join(f"{m:.6f}" for _, m in ELEMENTS),
             "   6   1   2   3   4   5   6",
             "   6   1   2   3   4   5   6"]
    # (Ca)1 (Fe,Mg)1 (Si)2 (O)6; endmembers ordered [Fe-end, Mg-end] = [hed, di]
    lines += _phase_block(
        "CLINOPYROXENE",
        [("HEDENBERGITE", hd, [1.0, 1.0, 0.0, 2.0, 6.0]),   # Ca,Fe,Mg,Si,O
         ("DIOPSIDE", di, [1.0, 0.0, 1.0, 2.0, 6.0])],
        [1.0, 1.0, 2.0, 6.0],
        [["CA"], ["FE", "MG"], ["SI"], ["O"]],
        [[1, 1], [1, 2], [1, 1], [1, 1]],
        [L0])
    path = out or (HERE / "Clinopyroxene-CEF.dat")
    Path(path).write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


if __name__ == "__main__":
    print("wrote", build())
