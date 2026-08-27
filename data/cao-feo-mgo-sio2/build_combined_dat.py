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

# CaO-SiO2 line compounds (the data/cao-sio2 phase model, as rebuilt in the CaO-Al2O3-SiO2
# ternary): Neumann-Kopp Cp on the oxides, measured dHf_ox relative to quartz plus the
# quartz->cristobalite offset, absolute S298. The CaO(l) melting calibration is tuned to
# diopside, and one CaO(l) anchor cannot also set the pure calcium-silicate melting (they
# depend on CaO(l) differently), so wollastonite and larnite each carry a small dHf melting
# calibration (dHf_cal), fit so they melt congruently at 1817 K and 2403 K in this liquid -
# the same discipline as the CaO(l)/diopside anchor, one anchor per compound. Only the two
# congruently-melting calcium silicates are included; rankinite and tricalcium silicate
# (incongruent) are a later step.
_CAO, _SIO2 = _cao.OXIDES["CaO"], _cao.OXIDES["SiO2"]
_DHF_QZ_TO_CRIST = -2300.0


def _casio(n_ca, n_si, dHf_ox_qz, S298, dHf_cal=0.0):
    return dict(dHf=n_ca * _CAO["dHf"] + n_si * _SIO2["dHf"] + dHf_ox_qz
                + _DHF_QZ_TO_CRIST * n_si + dHf_cal,
                S298=S298, a=n_ca * _CAO["a"] + n_si * _SIO2["a"],
                b=n_ca * _CAO["b"] + n_si * _SIO2["b"], c=n_ca * _CAO["c"] + n_si * _SIO2["c"])


for _nm, _nca, _nsi, _dho, _s, _cal in [("WOLLASTONITE", 1, 1, -81922.72, 85.2, -11499.0),
                                        ("LARNITE", 2, 1, -136816.80, 120.5, -24458.0)]:
    STOICH.append((_nm, _cao, _casio(_nca, _nsi, _dho, _s, _cal),
                   [float(_nca), 0.0, 0.0, float(_nsi), float(_nca + 2 * _nsi)]))


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
        f"    5    4    4    2    2    2    {len(STOICH)}",  # 5 el, 4 soln (counts 4,2,2,2), stoich
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
