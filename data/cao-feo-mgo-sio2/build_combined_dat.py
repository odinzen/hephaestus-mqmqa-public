"""Assemble ONE ChemSage .dat with every candidate phase of the CaO-FeO-MgO-SiO2 system:
the MQMQA liquid (SUBQ), the olivine, orthopyroxene, clinopyroxene and magnesiowustite CEF
solid solutions (SUBL), cristobalite, lime and the four calcium silicates,
so pycalphad can run a full multi-phase equilibrium: the ferromagnesian silicates
crystallizing from the slag melt.

The liquid and CEF blocks are spliced verbatim from the shipped files (data/cao-feo-mgo-sio2
liquid, data/olivine-opx-cpx solids), so the energetics are identical by construction; the
stoichiometric blocks come from the same Gibbs functions the binaries use. Element order Ca, Fe, Mg, Si, O throughout.
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
_mw = _load("mw_q", "magnesiowustite/magnesiowustite.py")

# stoichiometric oxide solids, element order (Ca, Fe, Mg, Si, O). Periclase and wustite are
# the ends of the magnesiowustite solution; lime stays apart (CaO-MgO has a wide solvus).
STOICH = [
    ("CRISTOBALITE", _cao, _cao.OXIDES["SiO2"], [0.0, 0.0, 0.0, 1.0, 2.0]),
    ("LIME", _cao, _cao.OXIDES["CaO"], [1.0, 0.0, 0.0, 0.0, 1.0]),
]

# CaO-SiO2 line compounds: the Robie-Hemingway calcium silicates of data/cao-sio2/silicates.py,
# the same functions the CaO-SiO2 and CaO-Al2O3-SiO2 files carry (Ca2SiO4 in two intervals, alpha'
# and alpha). WOLLASTONITE is pseudowollastonite, the high-temperature form.
_sil = _load("ca_silicates", "cao-sio2/silicates.py")
for _nm, _f, _nca, _nsi in [("WOLLASTONITE", "CaSiO3", 1, 1), ("RANKINITE", "Ca3Si2O7", 3, 2),
                            ("LARNITE", "Ca2SiO4", 2, 1), ("HATRURITE", "Ca3SiO5", 3, 1)]:
    STOICH.append((_nm, _cao, _sil.intervals(_f),
                   [float(_nca), 0.0, 0.0, float(_nsi), float(_nca + 2 * _nsi)]))


def _stoich_block(name, mod, ox, elems):
    """ox is an oxide dict or a list of (T_upper, dict) intervals."""
    ivs = ox if isinstance(ox, list) else [(6000.0, ox)]
    lines = [f" {name}", f"   1   {len(ivs)}   " + "   ".join(f"{e:.6f}" for e in elems)]
    for t_max, cf in ivs:
        assert not cf.get("d"), "a T^-0.5 Cp term needs the additional-terms block"
        coeffs = mod.solid_gibbs_coeffs(cf["dHf"], cf["S298"], cf["a"], cf["b"], cf["c"])
        lines.append(f"  {t_max:.4f}   " + "   ".join(f"{v:.12E}" for v in coeffs))
    return lines


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
        f"    5    5    4    2    4    2    2    {len(STOICH)}",  # 5 el, 5 soln (liquid 4, ol 2, opx 4, cpx 2, mw 2), stoich
        liq[2], liq[3], liq[4], liq[5],        # elements / masses / gibbs idx / excess idx
    ]
    out += liq_block
    out += cef_blocks
    out += _mw.subl_block(["CA", "FE", "MG", "SI", "O"])
    for name, mod, ox, elems in STOICH:
        out += _stoich_block(name, mod, ox, elems)

    OUT.write_text("\n".join(out) + "\n", encoding="ascii")
    print(f"wrote {OUT} ({len(out)} lines)")
    return OUT


if __name__ == "__main__":
    build()
