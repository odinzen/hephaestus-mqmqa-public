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


def test_ideal_mixing_no_excess(model):
    """The (Fe,Mg) M1 mixing is ideal: no excess term is shipped. A 7-model MLIP study put
    di-hed near ideal across every model, and the excess shifts the CaO-FeO-MgO-SiO2 liquidus
    by <= 20 K with no phase change (data/olivine/_mlip/VALIDATION.md). The phase Gibbs equals
    the endmember mixture plus the ideal one-site configurational term exactly."""
    bd, db, _ = model
    assert bd.EXCESS == []
    p = db.phase_index("CLINOPYROXENE")
    R, T = 8.31446, 1400.0
    for xmg in (0.25, 0.5, 0.75):
        g = db.cef_gibbs(p, [1.0, 1 - xmg, xmg, 1.0, 1.0], T, per_mole_atoms=True)
        g_hed = db.cef_gibbs(p, [1.0, 1.0, 0.0, 1.0, 1.0], T, per_mole_atoms=True)
        g_di = db.cef_gibbs(p, [1.0, 0.0, 1.0, 1.0, 1.0], T, per_mole_atoms=True)
        ideal = (xmg * g_di + (1 - xmg) * g_hed
                 + R * T * (xmg * np.log(xmg) + (1 - xmg) * np.log(1 - xmg)) / 10.0)  # 1 site / 10 atoms
        assert g == pytest.approx(ideal, abs=0.1), xmg


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
