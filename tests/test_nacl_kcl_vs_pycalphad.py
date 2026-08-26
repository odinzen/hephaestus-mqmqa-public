"""NaCl-KCl (liquid + halite solid solution) vs pycalphad, and the diagram anchors."""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

pycalphad = pytest.importorskip("pycalphad")
from pycalphad import Database as PDB, equilibrium, variables as v


def _mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def model():
    d = ROOT / "data" / "nacl-kcl"
    bd = _mod("nk_build", d / "build_dat.py")
    vf = _mod("nk_fit", d / "v01_fit.py")
    from mqmqa.dbbuild import ExcessTerm
    dat = bd.build([ExcessTerm(a=vf.STORED[0], b=0.0, p=0, q=0)])
    return vf, vf.Model(dat), dat


def test_hersh_kleppa_reproduced(model):
    vf, m, _ = model
    assert m.dh_mix(0.5, 1083.15) == pytest.approx(-547.0, abs=2.0)


def test_solvus_consolute(model):
    vf, m, _ = model
    assert vf.solvus_consolute(m) == pytest.approx(768.15, abs=1.0)


def test_liquidus_minimum_prediction(model):
    """Not fitted: the minimum must sit within ~25 K of the evaluated 931 K."""
    vf, m, _ = model
    T, x = vf.liquidus_minimum(m)
    assert T == pytest.approx(931.15, abs=25.0)
    assert 0.40 < x < 0.65


def test_two_halites_below_consolute(model):
    _, _, dat = model
    pdb = PDB(str(dat))
    res = equilibrium(pdb, ["NA", "K", "CL"], ["NACL-KCL-LIQUID", "HALITE"],
                      {v.T: 700.0, v.P: 101325, v.N: 1, v.X("K"): 0.25, v.X("NA"): 0.25})
    ph = [str(x) for x in res.Phase.values.ravel() if x]
    assert ph.count("HALITE") == 2
