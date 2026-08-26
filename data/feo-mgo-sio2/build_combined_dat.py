"""Assemble ONE ChemSage .dat holding every candidate phase of the FeO-MgO-SiO2 diagram -
the MQMQA liquid (SUBQ), the olivine and orthopyroxene CEF solid solutions (SUBL), and the
three stoichiometric oxide solids (cristobalite SiO2, periclase MgO, wustite FeO) - so that
pycalphad can run a full multi-phase `equilibrium` on the same model our 2-D minimizer uses.
This closes the one remaining validation gap: an end-to-end check of the minimizer's stable
assemblages against an independent global solver.

The liquid and CEF blocks are spliced verbatim from the shipped single-/two-phase .dat files
(so the energetics are identical by construction); the stoichiometric blocks are generated from
the same solid-oxide Gibbs coefficients the minimizer uses (`solid_gibbs_coeffs`). The opx block
carries the assessed enstatite high-T entropy correction as a second Gibbs interval (see
data/olivine-opx/build_dat.py), so the file and the minimizer share identical full energetics.
"""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIQ = HERE / "FeO-MgO-SiO2-liquid.dat"
OPX = HERE.parents[0] / "olivine-opx" / "Olivine-Opx-CEF.dat"
OUT = HERE / "FeO-MgO-SiO2-combined.dat"


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, HERE.parents[0] / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_feo = _load("bd_feo_comb", "feo-sio2/build_dat.py")
_mgo = _load("bd_mgo_comb", "mgo-sio2/build_dat.py")

# per-element stoichiometry (Fe, Mg, Si, O order) of each stoichiometric oxide solid
STOICH = [
    ("CRISTOBALITE", _feo.OXIDES["SiO2"], [0.0, 0.0, 1.0, 2.0]),
    ("PERICLASE", _mgo.OXIDES["MgO"], [0.0, 0.0, 0.0, 1.0]),  # placeholder, fixed below
    ("WUSTITE", _feo.OXIDES["FeO"], [1.0, 0.0, 0.0, 1.0]),
]
STOICH[1] = ("PERICLASE", _mgo.OXIDES["MgO"], [0.0, 1.0, 0.0, 1.0])


def _stoich_block(name, ox, elems):
    """One ChemSage stoichiometric-phase block, Gibbs eq. type 1 (single interval, six
    coefficients on the (1, T, T*lnT, T^2, T^3, 1/T) basis, no additional terms)."""
    A, B, C, D, E, F = _feo.solid_gibbs_coeffs(ox["dHf"], ox["S298"], ox["a"], ox["b"], ox["c"])
    lines = [f" {name}"]
    lines.append("   1   1   " + "   ".join(f"{e:.6f}" for e in elems))
    lines.append(f"  6000.0000   " + "   ".join(f"{v:.12E}" for v in (A, B, C, D, E, F)))
    return lines


def build():
    liq = LIQ.read_text().splitlines()
    opx = OPX.read_text().splitlines()
    # both source files carry a 6-line header (name, counts, elements, masses, gibbs, excess)
    liq_block = liq[6:]
    cef_blocks = opx[6:]  # OLIVINE + ORTHOPYROXENE SUBL blocks

    out = [
        " System FeO-MgO-SiO2 combined liquid+olivine+opx+oxides"
        " (validation .dat for pycalphad end-to-end; provenance PROVENANCE.md)",
        "    4    3    3    2    2    3",  # 4 el, 3 soln (counts 3,2,2), 3 stoich
        liq[2],  # elements  Fe Mg Si O
        liq[3],  # masses
        liq[4],  # gibbs coeff idxs   6 1 2 3 4 5 6
        liq[5],  # excess coeff idxs  6 1 2 3 4 5 6
    ]
    out += liq_block
    out += cef_blocks
    for name, ox, elems in STOICH:
        out += _stoich_block(name, ox, elems)

    OUT.write_text("\n".join(out) + "\n")
    print(f"wrote {OUT} ({len(out)} lines)")
    return OUT


if __name__ == "__main__":
    build()
