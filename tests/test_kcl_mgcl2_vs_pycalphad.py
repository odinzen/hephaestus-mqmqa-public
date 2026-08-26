"""KCl-MgCl2 (first divalent-cation salt) vs pycalphad, and the fitted anchors."""
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
    d = ROOT / "data" / "kcl-mgcl2"
    bd = _mod("km_build", d / "build_dat.py")
    vf = _mod("km_fit", d / "v01_fit.py")
    from mqmqa.dbbuild import ExcessTerm
    terms = [ExcessTerm(a=vf.STORED[1], b=0.0, p=0, q=0),
             ExcessTerm(a=vf.STORED[2], b=0.0, p=1, q=0)]
    dat = bd.build(liq_terms=terms)
    return bd, vf, vf.Model(dat), dat


def test_fitted_invariants(model):
    bd, vf, m, _ = model
    assert vf.congruent(m, bd.KMC_DHF_OX) == pytest.approx(761.65, abs=3.0)
    T, x = vf.eutectic(m, bd.KMC_DHF_OX, "KCl_solid", "KMgCl3")
    assert T == pytest.approx(697.55, abs=3.0)
    assert x == pytest.approx(0.375, abs=0.01)


def test_eutectic_fusion_enthalpy(model):
    bd, vf, m, _ = model
    assert vf.eutectic_fusion_enthalpy(m, bd.KMC_DHF_OX) == pytest.approx(17.04, abs=0.5)


def test_divalent_liquid_matches_pycalphad(model):
    import numpy as np
    from pycalphad import calculate
    _, _, m, dat = model
    pdb = PDB(str(dat))
    res = calculate(pdb, ["K", "MG", "CL"], "KCL-MGCL2-LIQUID", T=900.0, P=101325,
                    pdens=100000)
    xmg = res.X.sel(component="MG").values.ravel()
    gm = res.GM.values.ravel()
    for x in (0.25, 0.5, 0.75):
        atoms = (1 - x) * 2 + x * 3
        mask = np.abs(xmg - x / atoms) < 2e-4
        assert gm[mask].min() == pytest.approx(m.g_liq(x, 900.0) / atoms, abs=30.0)


def test_topology(model):
    _, _, _, dat = model
    pdb = PDB(str(dat))
    r = equilibrium(pdb, ["K", "MG", "CL"], list(pdb.phases.keys()),
                    {v.T: 720.0, v.P: 101325, v.N: 1, v.X("MG"): 0.5 / 2.5, v.X("K"): 0.5 / 2.5})
    assert sorted(set(str(p) for p in r.Phase.values.ravel() if p)) == ["KMGCL3"]
