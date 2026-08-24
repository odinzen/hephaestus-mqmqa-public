"""Validate the C compound-energy-formalism (CEF) path against pycalphad.

Two levels, both reading a ChemSage SUBL .dat with the C reader and computing GM with
the C kernel (mqmqa_cef_gibbs), against pycalphad's Model.GM on the same file:

1. Olivine (Mg,Fe)2SiO4, a hand-authored SUBL file (data/olivine, built on the fly):
   two sublattices that mix / stay fixed, site multiplicities 2/1/4, a forsterite
   endmember carrying a T^0.5 term, and a two-order Redlich-Kister excess.
2. Viitala Pb-Zn-Cu-Fe-Cl, a real-world ChemSage database whose SUBL phases exercise
   multi-interval endmembers, log(T) additional terms, charged species names, vacancies
   (per-atom GM normalization), and non-alphabetical constituent order.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
sys.path.insert(0, str(ROOT / "cef"))
sys.path.insert(0, str(ROOT / "data" / "olivine"))

pytest.importorskip("pycalphad")
from pycalphad import Database as PycDatabase, calculate

import mqmqa

VIITALA = Path("C:/Users/busta/Code/pycalphad/pycalphad/tests/databases/Viitala.dat")


def _gm_pycalphad(pdb, comps, phase, points, T):
    res = calculate(pdb, comps, phase, T=T, P=101325,
                    points=np.array([points], dtype=float), output="GM")
    return float(res.GM.values.squeeze())


def test_olivine_subl_reader_and_kernel():
    import build_subl_dat
    dat = ROOT / "data" / "olivine" / "Olivine-CEF.dat"
    dat.write_text(build_subl_dat.build(), encoding="ascii")

    cdb = mqmqa.Database.read(str(dat))
    p = cdb.phase_index("OLIVINE")
    assert cdb.phase_kind(p) == 1
    subl = cdb.cef_sublattices(p)
    assert [s["site_ratio"] for s in subl] == [2.0, 1.0, 4.0]
    assert subl[0]["constituents"] == ["FE", "MG"]

    pdb = PycDatabase(str(dat))
    order = [c for sl in subl for c in sl["constituents"]]  # [FE, MG, SI, O]
    worst = 0.0
    for T in (1000.0, 1400.0, 1800.0):
        for x_fo in (0.0, 0.2, 0.5, 0.8, 1.0):
            Y = {"FE": 1 - x_fo, "MG": x_fo, "SI": 1.0, "O": 1.0}
            gc = cdb.cef_gibbs(p, [Y[c] for c in order], T)
            gpc = _gm_pycalphad(pdb, ["FE", "MG", "SI", "O"], "OLIVINE",
                                [1 - x_fo, x_fo, 1.0, 1.0], T)
            worst = max(worst, abs(gc - gpc))
    assert worst < 1e-4, f"olivine GM worst |d| = {worst}"


@pytest.mark.skipif(not VIITALA.exists(), reason="Viitala.dat not available")
def test_viitala_real_subl_phases():
    cdb = mqmqa.Database.read(str(VIITALA))
    pdb = PycDatabase(str(VIITALA))

    worst = 0.0
    for name in ("CUCL", "FEZNSOLN", "ZNFESOLN"):
        p = cdb.phase_index(name)
        assert cdb.phase_kind(p) == 1
        subl = cdb.cef_sublattices(p)
        pph = pdb.phases[name]
        comps = sorted({e for ss in pph.constituents for sp in ss for e in sp.constituents})

        # a few interior site-fraction assignments, populating vacancies too
        for frac in (0.5, 0.3, 0.7):
            assign = {}  # (sublattice, constituent name) -> site fraction
            for s, sl in enumerate(subl):
                cons = sl["constituents"]
                if len(cons) == 1:
                    assign[(s, cons[0])] = 1.0
                else:
                    assign[(s, cons[0])] = frac
                    assign[(s, cons[1])] = 1.0 - frac
                    for c in cons[2:]:
                        assign[(s, c)] = 0.0
            for T in (1000.0, 1500.0):
                # our Y in the reader's constituent order
                Y = [assign[(s, c)] for s, sl in enumerate(subl) for c in sl["constituents"]]
                gc = cdb.cef_gibbs(p, Y, T)
                # pycalphad points in its (sorted) constituent order, matched by name
                pts = [assign[(s, sp.name)]
                       for s, ss in enumerate(pph.constituents) for sp in sorted(ss)]
                gpc = _gm_pycalphad(pdb, comps, name, pts, T)
                worst = max(worst, abs(gc - gpc))
    assert worst < 1e-4, f"Viitala GM worst |d| = {worst}"
