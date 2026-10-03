"""Two-site orthopyroxene: the engine's line sampler takes the M1/M2 order at internal
equilibrium, exactly as pycalphad and the assessment's own model do, and a one-site phase
is sampled exactly as before."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

pycalphad = pytest.importorskip("pycalphad")
from pycalphad import Database, equilibrium, variables as v

import mqmqa

DAT = ROOT / "data" / "olivine-opx" / "Olivine-Opx-CEF.dat"


def _load(name, rel):
    s = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def dbs():
    bd = _load("opx_ts_build", "data/olivine-opx/build_dat.py")
    DAT.write_text(bd.build(), encoding="ascii")
    return mqmqa.Database.read(str(DAT)), Database(str(DAT))


def test_line_gibbs_matches_pycalphad_and_the_model(dbs):
    db, pdb = dbs
    opx = _load("opx_ts_model", "data/olivine-opx/orthopyroxene.py")
    p = db.phase_index("ORTHOPYROXENE")
    for T in (900.0, 1300.0, 1700.0):
        for x in (0.05, 0.3, 0.5, 0.8):
            g, Y = db.cef_line_gibbs(p, 1 - x, T, per_mole_atoms=True)
            r = equilibrium(pdb, ["FE", "MG", "SI", "O"], ["ORTHOPYROXENE"],
                            {v.T: T, v.P: 101325, v.N: 1, v.X("FE"): 0.2 * x,
                             v.X("MG"): 0.2 * (1 - x), v.X("SI"): 0.2})
            assert g == pytest.approx(float(r.GM.values.ravel()[0]), abs=1e-3), (T, x)
            gm, y1, y2 = opx.equilibrium(x, T)
            assert g == pytest.approx(gm / 10.0, abs=1e-3), (T, x)
            assert Y[0] == pytest.approx(y1, abs=1e-5) and Y[2] == pytest.approx(y2, abs=1e-5)
            # Fe prefers M2 at every composition and temperature sampled
            assert Y[2] > Y[0]


def test_one_site_line_is_the_plain_cef_value(dbs):
    db, _ = dbs
    p = db.phase_index("OLIVINE")
    for y in (0.0, 0.17, 0.5, 0.93, 1.0):
        g, Y = db.cef_line_gibbs(p, y, 1500.0, per_mole_atoms=False)
        assert Y == [1 - y, y, 1.0, 1.0]
        assert g == db.cef_gibbs(p, [1 - y, y, 1.0, 1.0], 1500.0, per_mole_atoms=False)


def test_assessed_model_reproduces_its_data():
    a = _load("opx_ts_assess", "data/olivine-opx/assessment/assess.py")
    res, rows = a.residuals([getattr(a.opx, n) for n in a.NAMES], detail=True)
    site = np.array([r for tag, r, _ in rows if tag.startswith("site")])
    boh = np.array([r for tag, r, _ in rows if tag.startswith("Bohlen")])
    assert len(site) == 29 and np.sqrt(np.mean(site ** 2)) < 1.0
    assert np.max(np.abs(boh)) < 3.0
    assert np.sqrt(np.mean(res ** 2)) < 1.5
