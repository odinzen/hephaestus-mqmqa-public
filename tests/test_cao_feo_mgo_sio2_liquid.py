"""CaO-FeO-MgO-SiO2 quaternary liquid: reduces to each shipped binary, reads in pycalphad."""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

pycalphad = pytest.importorskip("pycalphad")
from pycalphad import Database

import mqmqa
from mqmqa import equilibrium as eq, dbbuild


def _load(rel, nm):
    s = importlib.util.spec_from_file_location(nm, ROOT / "data" / rel)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def dbs(tmp_path_factory):
    q = _load("cao-feo-mgo-sio2/build_dat.py", "q_build")
    d = tmp_path_factory.mktemp("q") / "quaternary.dat"
    d.write_text(q.build(), encoding="ascii")
    qdb = mqmqa.Database.read(str(d))
    fms = mqmqa.Database.read(str(ROOT / "data" / "feo-mgo-sio2" / "FeO-MgO-SiO2-liquid.dat"))
    cao = _load("cao-sio2/build_dat.py", "cao_build")
    ex = [dict(code="Q", li=[1, 2, 3, 3], exp=[0, 0, 0, 0],
               coeffs=[-189763.512, 15.7059847, 0, 0, 0, 0]),
          dict(code="Q", li=[1, 2, 3, 3], exp=[1, 0, 0, 0], coeffs=[57170.779, 0, 0, 0, 0, 0])]
    cs = tmp_path_factory.mktemp("cs") / "cs.dat"
    cs.write_text(cao.build(excess=ex, version="ref"), encoding="ascii")
    cdb = mqmqa.Database.read(str(cs))
    return str(d), qdb, fms, cdb


def _gbin(db, ph, comps, x, T):
    inp = eq.build_inputs(db, db.phase_index(ph), T, components=comps)
    gm, _ = dbbuild._binary_activity_solver(inp, 2.0, 3.0)     # MO=2 atoms, SiO2=3
    return gm(x) * ((1 - x) * 2.0 + x * 3.0)


def test_pycalphad_reads_quaternary(dbs):
    path, *_ = dbs
    pdb = Database(path)
    assert list(pdb.phases.keys()) == ["CAO-FEO-MGO-SIO2-LIQUID"]
    assert sorted(str(e) for e in pdb.elements) == ["CA", "FE", "MG", "O", "SI"]


def test_binary_limit_reductions_are_exact(dbs):
    _, qdb, fms, cdb = dbs
    Q = "CAO-FEO-MGO-SIO2-LIQUID"
    csl = [n for n in cdb.phase_names if "LIQ" in n.upper()][0]
    cases = [("FeO-SiO2", ["FE", "SI", "O"], fms, "FEO-MGO-SIO2-LIQUID"),
             ("MgO-SiO2", ["MG", "SI", "O"], fms, "FEO-MGO-SIO2-LIQUID"),
             ("CaO-SiO2", ["CA", "SI", "O"], cdb, csl)]
    for _, comps, rdb, rph in cases:
        for x in (0.3, 0.5, 0.7):
            gq = _gbin(qdb, Q, comps, x, 1800.0)
            gr = _gbin(rdb, rph, comps, x, 1800.0)
            assert gq == pytest.approx(gr, abs=0.01), (comps, x, gq - gr)
