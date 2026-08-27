"""Spinel-hercynite (Mg,Fe)Al2O4 CEF solid solution vs pycalphad."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

pycalphad = pytest.importorskip("pycalphad")
from pycalphad import Database as PDB, calculate

import mqmqa


def _mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def model():
    bd = _mod("spinel_build", ROOT / "data" / "spinel" / "build_dat.py")
    dat = bd.build()
    return bd, mqmqa.Database.read(str(dat)), PDB(str(dat))


def test_endmembers(model):
    bd, _, _ = model
    em = bd.em
    assert em.ENDMEMBERS["hercynite"]["dHf"] == pytest.approx(-1982380.0)
    assert em.cp("hercynite", 298.15) == pytest.approx(128.8, abs=0.2)   # NK, ~TKV 123.55


def test_cef_gibbs_matches_pycalphad(model):
    _, db, pdb = model
    p = db.phase_index("SPINEL")
    assert db.phase_kind(p) == 1
    for T in (1000.0, 1600.0):
        for x in (0.0, 0.3, 0.5, 0.8, 1.0):
            Y = [x, 1 - x, 1, 1]                                          # FE, MG, AL, O
            ge = db.cef_gibbs(p, Y, T, per_mole_atoms=True)
            gp = float(calculate(pdb, ["FE", "MG", "AL", "O"], "SPINEL", T=T, P=101325,
                                 points=np.array([Y])).GM.values.ravel()[0])
            assert ge == pytest.approx(gp, abs=1e-6), (T, x)


def test_ideal_mixing_no_excess(model):
    """The (Fe,Mg) A-site is ideal: no excess term is shipped (7-model MLIP study gave a 22 kJ
    spread and no agreed sign; see data/olivine/_mlip/VALIDATION.md). Ideal mixing has no gap,
    and the phase Gibbs equals the endmember mechanical mixture plus RT*sum(y ln y) exactly."""
    bd, db, _ = model
    assert bd.EXCESS == []
    p = db.phase_index("SPINEL")
    R, T = 8.31446, 1500.0
    for x in (0.25, 0.5, 0.75):
        Y = [x, 1 - x, 1, 1]                                              # FE, MG, AL, O
        g = db.cef_gibbs(p, Y, T, per_mole_atoms=True)
        g0 = db.cef_gibbs(p, [1, 0, 1, 1], T, per_mole_atoms=True)
        g1 = db.cef_gibbs(p, [0, 1, 1, 1], T, per_mole_atoms=True)
        ideal = x * g0 + (1 - x) * g1 + R * T * (x * np.log(x) + (1 - x) * np.log(1 - x)) / 7.0
        assert g == pytest.approx(ideal, abs=0.1), x                     # no excess, one A-site of 7 atoms
