"""Assemble ONE ChemSage .dat with every candidate phase of the CaO-FeO-MgO-SiO2 system:
the MQMQA liquid (SUBQ), the olivine + orthopyroxene + clinopyroxene CEF solid solutions
(SUBL), and the four stoichiometric oxide solids (cristobalite, periclase, wustite, lime),
so pycalphad can run a full multi-phase equilibrium: the ferromagnesian silicates
crystallizing from the slag melt.

The liquid and CEF blocks are spliced verbatim from the shipped files (data/cao-feo-mgo-sio2
liquid, data/olivine-opx-cpx solids), so the energetics are identical by construction; the
stoichiometric oxide blocks come from the same solid-oxide Gibbs coefficients the binaries
use. Element order Ca, Fe, Mg, Si, O throughout.
"""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
D = HERE.parent
LIQ = HERE / "CaO-FeO-MgO-SiO2-liquid.dat"
CEF = D / "olivine-opx-cpx" / "Olivine-Opx-Cpx-CEF.dat"
OUT = HERE / "CaO-FeO-MgO-SiO2-combined.dat"


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, D / rel)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


_cao = _load("bd_cao_c", "cao-sio2/build_dat.py")
_feo = _load("bd_feo_c", "feo-sio2/build_dat.py")
_mgo = _load("bd_mgo_c", "mgo-sio2/build_dat.py")

# stoichiometric oxide solids, element order (Ca, Fe, Mg, Si, O)
STOICH = [
    ("CRISTOBALITE", _cao, _cao.OXIDES["SiO2"], [0.0, 0.0, 0.0, 1.0, 2.0]),
    ("LIME", _cao, _cao.OXIDES["CaO"], [1.0, 0.0, 0.0, 0.0, 1.0]),
    ("PERICLASE", _mgo, _mgo.OXIDES["MgO"], [0.0, 0.0, 1.0, 0.0, 1.0]),
    ("WUSTITE", _feo, _feo.OXIDES["FeO"], [0.0, 1.0, 0.0, 0.0, 1.0]),
]


def _stoich_block(name, mod, ox, elems):
    A, B, C, D_, E, F = mod.solid_gibbs_coeffs(ox["dHf"], ox["S298"], ox["a"], ox["b"], ox["c"])
    return [f" {name}",
            "   1   1   " + "   ".join(f"{e:.6f}" for e in elems),
            "  6000.0000   " + "   ".join(f"{v:.12E}" for v in (A, B, C, D_, E, F))]


def build():
    # regenerate the two source files from their builders so the combined file is current
    LIQ.write_text(_load("q_liq", "cao-feo-mgo-sio2/build_dat.py").build(), encoding="ascii")
    _load("oox_cef", "olivine-opx-cpx/build_dat.py").build(out=str(CEF))
    liq = LIQ.read_text().splitlines()
    cef = CEF.read_text().splitlines()
    # both files carry a 6-line header (name, counts, elements, masses, gibbs, excess)
    liq_block = liq[6:]
    cef_blocks = cef[6:]        # OLIVINE + ORTHOPYROXENE + CLINOPYROXENE SUBL blocks

    out = [
        " System CaO-FeO-MgO-SiO2 combined liquid + ol/opx/cpx + oxide solids"
        " (multiphase melting; provenance data/cao-feo-mgo-sio2/PROVENANCE.md)",
        "    5    4    4    2    2    2    4",  # 5 el, 4 soln (counts 4,2,2,2), 4 stoich
        liq[2], liq[3], liq[4], liq[5],        # elements / masses / gibbs idx / excess idx
    ]
    out += liq_block
    out += cef_blocks
    for name, mod, ox, elems in STOICH:
        out += _stoich_block(name, mod, ox, elems)

    OUT.write_text("\n".join(out) + "\n", encoding="ascii")
    print(f"wrote {OUT} ({len(out)} lines)")
    return OUT


if __name__ == "__main__":
    build()
