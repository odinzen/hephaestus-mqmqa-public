"""Clinopyroxene (diopside-hedenbergite) CEF solid solution vs pycalphad."""
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
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def model():
    bd = _mod("cpx_build", ROOT / "data" / "clinopyroxene" / "build_dat.py")
    dat = bd.build()
    return bd, mqmqa.Database.read(str(dat)), PDB(str(dat))


def test_endmembers_reproduce_robie_hemingway(model):
    bd, _, _ = model
    em = bd.em
    assert em.cp("diopside", 298.15) == pytest.approx(166.78, abs=0.05)
    assert em.cp("hedenbergite", 298.15) == pytest.approx(175.3, abs=0.05)
    assert em.ENDMEMBERS["diopside"]["dHf"] == pytest.approx(-3201500.0)
    assert em.ENDMEMBERS["hedenbergite"]["dHf"] == pytest.approx(-2839900.0)


def test_mixing_excess_small_and_asymmetric(model):
    """v0.2 carries the MLIP-triangulated (Fe,Mg) excess: small (near-ideal, no gap) and
    asymmetric (negative Mg-rich, positive Fe-rich). Checked as the RK enthalpy."""
    bd, _, _ = model
    assert (bd.L0, bd.L1) == pytest.approx((-576.0, 3441.7))
    hmix = lambda x: x * (1 - x) * (bd.L0 + bd.L1 * (2 * x - 1))   # J/mol formula
    assert abs(hmix(0.5)) < 500                                    # near-ideal
    assert hmix(0.125) < -200 and hmix(0.875) > 100               # asymmetric


def test_cef_gibbs_matches_pycalphad(model):
    _, db, pdb = model
    p = db.phase_index("CLINOPYROXENE")
    assert db.phase_kind(p) == 1                       # CEF
    for T in (1000.0, 1400.0):
        for xdi in (0.0, 0.3, 0.5, 0.8, 1.0):
            Y = [1.0, 1.0 - xdi, xdi, 1.0, 1.0]        # CA, FE, MG, SI, O
            ge = db.cef_gibbs(p, Y, T, per_mole_atoms=True)
            res = calculate(pdb, ["CA", "FE", "MG", "SI", "O"], "CLINOPYROXENE", T=T,
                            P=101325, points=np.array([[1.0, 1.0 - xdi, xdi, 1.0, 1.0]]))
            assert ge == pytest.approx(float(res.GM.values.ravel()[0]), abs=1e-6), (T, xdi)
