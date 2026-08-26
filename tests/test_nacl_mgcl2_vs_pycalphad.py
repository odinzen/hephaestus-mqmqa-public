"""NaCl-MgCl2 (simple divalent-cation eutectic) vs pycalphad, and the fitted anchor."""
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
    d = ROOT / "data" / "nacl-mgcl2"
    bd = _mod("nm_build", d / "build_dat.py")
    vf = _mod("nm_fit", d / "v01_fit.py")
    dat = bd.build(liq_terms=bd.liquid_terms())
    return bd, vf, vf.Model(dat), dat


def test_fitted_eutectic(model):
    _, vf, m, _ = model
    T, x = vf.eutectic(m)
    assert T == pytest.approx(718.15, abs=5.0)
    assert x == pytest.approx(0.42, abs=0.02)


def test_divalent_liquid_matches_pycalphad(model):
    import numpy as np
    from pycalphad import calculate
    _, _, m, dat = model
    pdb = PDB(str(dat))
    res = calculate(pdb, ["NA", "MG", "CL"], "NACL-MGCL2-LIQUID", T=900.0, P=101325,
                    pdens=100000)
    xmg = res.X.sel(component="MG").values.ravel()
    gm = res.GM.values.ravel()
    for x in (0.25, 0.5, 0.75):
        atoms = (1 - x) * 2 + x * 3
        mask = np.abs(xmg - x / atoms) < 2e-4
        assert gm[mask].min() == pytest.approx(m.g_liq(x, 900.0) / atoms, abs=30.0)


def test_topology_simple_eutectic(model):
    """Below the eutectic: NaCl + MgCl2 two-phase; no intermediate compound exists."""
    _, _, _, dat = model
    pdb = PDB(str(dat))
    assert "NACL_SOLID" in pdb.phases and "MGCL2_SOLID" in pdb.phases
    r = equilibrium(pdb, ["NA", "MG", "CL"], list(pdb.phases.keys()),
                    {v.T: 690.0, v.P: 101325, v.N: 1, v.X("MG"): 0.42 / 2.42,
                     v.X("NA"): 0.58 / 2.42})
    phases = sorted(set(str(p) for p in r.Phase.values.ravel() if p))
    assert phases == ["MGCL2_SOLID", "NACL_SOLID"]
