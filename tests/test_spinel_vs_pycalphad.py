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


def test_mixing_excess_negative_no_gap(model):
    """The MLIP-triangulated excess is favourable (negative) and asymmetric, so the solid
    solution is stabilized (no miscibility gap)."""
    bd, _, _ = model
    assert (bd.L0, bd.L1) == pytest.approx((-3411.1, -2373.3))
    hmix = lambda x: x * (1 - x) * (bd.L0 + bd.L1 * (2 * x - 1))
    assert hmix(0.5) < -300 and hmix(0.25) < 0 and hmix(0.75) < 0          # negative across
