"""Write the olivine (Mg,Fe)2SiO4 model as a ChemSage SUBL (compound-energy-formalism)
.dat file - the format the engine's ChemSage reader parses.

Same model as olivine.py: endmembers forsterite/fayalite (Robie-Hemingway 1995), the
Wood & Kleppa 1981 subregular excess. The endmember Gibbs energies are written on the
ChemSage term basis (1, T, T*lnT, T^2, T^3, 1/T); forsterite's T^0.5 term (from its
Robie-Hemingway T^-0.5 heat-capacity term) rides in the "additional terms" slot as a
coefficient/exponent pair (c6, 0.5), which the reader evaluates as c6*T^0.5.

Sublattice model (Mg,Fe)2(Si)1(O)4: metal sublattice mixes, Si and O fixed, site ratios
2/1/4 so the per-mole-of-atoms divisor is 7. Constituents are listed [Fe, Mg] to match
pycalphad's alphabetical sort.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "cef"))

import endmembers as em
import olivine as ol

# element order in the file; stoichiometry vectors follow it
ELEMENTS = [("FE", 55.845), ("MG", 24.305), ("SI", 28.085), ("O", 15.9994)]

# endmember -> (species name, stoichiometry over [Fe,Mg,Si,O], the endmember key)
ENDMEMBERS = [
    ("FAYALITE",   [2.0, 0.0, 1.0, 4.0], "fayalite"),    # metal sublattice = Fe
    ("FORSTERITE", [0.0, 2.0, 1.0, 4.0], "forsterite"),  # metal sublattice = Mg
]

# sublattice model: (Mg,Fe)2 (Si)1 (O)4, constituents in [Fe,Mg] order
SUBL_RATIOS = [2.0, 1.0, 4.0]
SUBL_CONSTITUENTS = [["FE", "MG"], ["SI"], ["O"]]
# 1-based constituent index of each endmember on each sublattice (endmember order above)
EM_CON_IDX = [
    [1, 2],  # sublattice 0: fayalite->Fe(1), forsterite->Mg(2)
    [1, 1],  # sublattice 1: both Si
    [1, 1],  # sublattice 2: both O
]


def _fmt(x):
    return f"{x:.10E}"


def build():
    L = []
    ap = L.append
    ap(" Olivine (Mg,Fe)2SiO4 CEF (SUBL) - open model, provenance data/olivine/PROVENANCE.md")
    # header: n_el, n_soln, [species-count per soln phase], n_stoich
    ap(f"   {len(ELEMENTS)}   1   {len(ENDMEMBERS)}   0")
    ap("   " + "   ".join(e[0] for e in ELEMENTS))
    ap("   " + "   ".join(f"{m:.6f}" for _, m in ELEMENTS))
    # Gibbs and excess term bases: (1, T, T*lnT, T^2, T^3, 1/T)
    ap("   6   1   2   3   4   5   6")
    ap("   6   1   2   3   4   5   6")

    ap(" OLIVINE")
    ap(" SUBL")

    for name, stoich, key in ENDMEMBERS:
        c = em.gibbs_coeffs(key)             # [c0..c5, c6(sqrt)]
        std, sqrt_c = c[:6], c[6]
        eq_type = 4 if sqrt_c != 0.0 else 1  # 4 = Gibbs with additional terms
        ap(f" {name}")
        # eq_type, n_intervals, then stoichiometry over the pure elements
        ap(f"   {eq_type}   1   " + "   ".join(f"{s:.1f}" for s in stoich))
        # one interval: T_max, six Gibbs coefficients
        ap("   6000.0000   " + "   ".join(_fmt(v) for v in std))
        if eq_type == 4:
            # additional terms: count, then (coeff, exponent) pairs
            ap(f"   1   {_fmt(sqrt_c)}   {_fmt(0.5)}")

    # sublattice model
    ap(f"   {len(SUBL_RATIOS)}")
    ap("   " + "   ".join(f"{r:.6f}" for r in SUBL_RATIOS))
    ap("   " + "   ".join(str(len(c)) for c in SUBL_CONSTITUENTS))
    for con in SUBL_CONSTITUENTS:
        ap("   " + "   ".join(con))
    for row in EM_CON_IDX:
        ap("   " + "   ".join(str(i) for i in row))

    # excess (Redlich-Kister) block: one interaction, orders 0 and 1
    # interacting linear species indices: Fe=1, Mg=2 (subl0), Si=3 (subl1), O=4 (subl2)
    L0, L1 = ol.L0, ol.L1
    ap("   4   1   2   3   4")           # num_interacting_species, then the linear idxs
    ap("   2")                            # number of RK orders
    ap("   " + "   ".join(_fmt(v) for v in [L0, 0, 0, 0, 0, 0]))  # order 0 coeffs
    ap("   " + "   ".join(_fmt(v) for v in [L1, 0, 0, 0, 0, 0]))  # order 1 coeffs
    ap("   0")                            # terminate the excess block

    return "\n".join(L) + "\n"


if __name__ == "__main__":
    out = HERE / "Olivine-CEF.dat"
    out.write_text(build(), encoding="ascii")
    print(f"wrote {out}")
