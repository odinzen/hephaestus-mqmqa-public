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
    cs = tmp_path_factory.mktemp("cs") / "cs.dat"
    cs.write_text(cao.build(excess=cao.assessed_excess(), version="ref"), encoding="ascii")
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
    """FeO-SiO2 and MgO-SiO2 reduce to the shipped ternary, CaO-SiO2 to the assessed binary,
    exactly, below and above the CaO melting point (no endmember is recalibrated here)."""
    _, qdb, fms, cdb = dbs
    Q = "CAO-FEO-MGO-SIO2-LIQUID"
    csl = [n for n in cdb.phase_names if "LIQ" in n.upper()][0]
    for comps, rdb, rph, T in [(["FE", "SI", "O"], fms, "FEO-MGO-SIO2-LIQUID", 1800.0),
                               (["MG", "SI", "O"], fms, "FEO-MGO-SIO2-LIQUID", 1800.0),
                               (["CA", "SI", "O"], cdb, csl, 1800.0),
                               (["CA", "SI", "O"], cdb, csl, 2900.0)]:
        for x in (0.3, 0.5, 0.7):
            gq = _gbin(qdb, Q, comps, x, T)
            gr = _gbin(rdb, rph, comps, x, T)
            assert gq == pytest.approx(gr, abs=0.01), (comps, x, T, gq - gr)


def test_single_quadruplet_energies_are_finite(dbs):
    """One quadruplet alone: every term whose quadruplets are absent adds nothing. Their
    mixing fractions are 0/0 there, which made the whole energy NaN at a pure oxide."""
    import numpy as np
    _, qdb, _, _ = dbs
    inp = eq.build_inputs(qdb, 0, 1800.0)
    n = len(inp["quads"])
    for q in range(n):
        X = [1.0 if k == q else 0.0 for k in range(n)]
        g = eq.gibbs_per_quad(inp, X)
        assert np.isfinite(g), inp["quads"][q]
        if inp["qca"][q] == inp["qcb"][q]:          # a pure oxide: its reference energy only
            ref = mqmqa.reference_energy(inp["qca"], inp["qcb"], inp["qax"], inp["qay"], X,
                                         inp["pcat"], inp["pan"], inp["pG"], inp["pstoich"],
                                         inp["Ztab"])
            assert g == ref, (inp["quads"][q], g, ref)


def test_feo_mgo_sio2_face_is_the_shipped_ternary():
    """Same grouping and the same terms: the Fe-Mg-Si face of the quaternary is the shipped
    FeO-MgO-SiO2 liquid line for line, only the title differs."""
    q = _load("cao-feo-mgo-sio2/build_dat.py", "q_face")
    face = q.build(cations=["Fe", "Mg", "Si"]).splitlines()
    shipped = (ROOT / "data" / "feo-mgo-sio2" / "FeO-MgO-SiO2-liquid.dat").read_text().splitlines()
    assert face[1:] == shipped[1:]
