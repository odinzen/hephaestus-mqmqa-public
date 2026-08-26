"""The MQMX additional-constituent (ternary) term vs pycalphad.

Poschmann Eq. 25-26 with a single chemical group and r = 1: the term is the binary
Q-code mixing term multiplied by the third cation's pair fraction Y_m. pycalphad
implements the general form; the C engine implements the single-group r = 1 case and
returns NaN beyond it. Here a three-cation liquid carrying one ternary-tagged term is
written by dbbuild, read back, and the equilibrium Gibbs energy is compared between
the C solver and pycalphad's equilibrium at ternary compositions where the factor is
strongly active.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

import mqmqa
from mqmqa import dbbuild
from mqmqa import equilibrium as eq
from mqmqa import _abi
from mqmqa.dbbuild import BinaryExcess, ExcessTerm, SystemSpec

pycalphad = pytest.importorskip("pycalphad")
from pycalphad import Database as PDB, equilibrium as pyc_eq, variables as v


@pytest.fixture(scope="module")
def ternary_dat(tmp_path_factory):
    cao = dbbuild.starter_component("CaO")
    mgo = dbbuild.starter_component("MgO")
    sio2 = dbbuild.starter_component("SiO2")
    bins = [
        BinaryExcess("CaO", "SiO2", [
            ExcessTerm(a=-80000.0, b=10.0, p=0, q=0),
            ExcessTerm(a=-50000.0, b=0.0, p=0, q=0, add_cat="MgO", r=1),
        ]),
        BinaryExcess("MgO", "SiO2", [ExcessTerm(a=-60000.0, b=0.0, p=0, q=0)]),
    ]
    spec = SystemSpec("CaO-MgO-SiO2", [cao, mgo, sio2], bins,
                      version="test", provenance="ternary-term regression test")
    p = tmp_path_factory.mktemp("tern") / "tern.dat"
    p.write_text(dbbuild.write_dat(spec), encoding="ascii")
    return p


def test_reader_roundtrip(ternary_dat):
    db = mqmqa.Database.read(str(ternary_dat))
    p = db.phase_index("CAO-MGO-SIO2-LIQUID")
    mx = db.mqmx(p, 1800.0)
    assert mx["addcat"].count(-1) == 2      # two plain terms
    assert 1 in mx["addcat"]                # MgO is cation index 1
    i = mx["addcat"].index(1)
    assert mx["r"][i] == 1.0


def test_equilibrium_gm_matches_pycalphad(ternary_dat):
    db = mqmqa.Database.read(str(ternary_dat))
    p = db.phase_index("CAO-MGO-SIO2-LIQUID")
    pdb = PDB(str(ternary_dat))
    for T in (1700.0, 2000.0):
        inp = eq.build_inputs(db, p, T, components=["CA", "MG", "SI", "O"])
        for x_ca, x_mg, x_si in ((0.4, 0.3, 0.3), (0.2, 0.5, 0.3), (0.45, 0.45, 0.10)):
            n = {"CA": x_ca, "MG": x_mg, "SI": x_si,
                 "O": x_ca + x_mg + 2 * x_si}
            ours = _abi.c_equilibrate(inp, n)["GM"]
            tot = sum(n.values())
            res = pyc_eq(pdb, ["CA", "MG", "SI", "O"], ["CAO-MGO-SIO2-LIQUID"],
                         {v.T: T, v.P: 101325, v.N: 1,
                          v.X("CA"): n["CA"] / tot, v.X("MG"): n["MG"] / tot,
                          v.X("SI"): n["SI"] / tot})
            theirs = float(res.GM.values.ravel()[0])
            assert ours == pytest.approx(theirs, abs=0.5), (T, x_ca, x_mg, x_si)


def test_r2_is_loud(ternary_dat):
    """r >= 2 is not implemented in C and must return NaN, never a wrong number."""
    db = mqmqa.Database.read(str(ternary_dat))
    p = db.phase_index("CAO-MGO-SIO2-LIQUID")
    inp = eq.build_inputs(db, p, 1800.0, components=["CA", "MG", "SI", "O"])
    inp["ex"]["r"] = [2.0 if a >= 0 else r for r, a in zip(inp["ex"]["r"], inp["ex"]["addcat"])]
    gm = _abi.c_equilibrate(inp, {"CA": 0.4, "MG": 0.3, "SI": 0.3, "O": 1.3})["GM"]
    assert np.isnan(gm)
