"""Ca-Fe-Mg-Si silicate assembly: olivine + opx + cpx in one .dat, vs pycalphad."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

pycalphad = pytest.importorskip("pycalphad")
from pycalphad import calculate


def _mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def sys_():
    ex = _mod("oox_exchange", ROOT / "data" / "olivine-opx-cpx" / "exchange.py")
    db, pdb, _ = ex._load()
    return ex, db, pdb


def test_three_phases_engine_matches_pycalphad(sys_):
    ex, db, pdb = sys_
    for ph, (_, Yf) in ex.PH.items():
        for T in (1000.0, 1400.0):
            for x in (0.25, 0.6):
                Y = Yf(x)
                ge = db.cef_gibbs(db.phase_index(ph), Y, T, per_mole_atoms=True)
                gp = float(calculate(pdb, ["CA", "FE", "MG", "SI", "O"], ph, T=T, P=101325,
                                     points=np.array([Y])).GM.values.ravel()[0])
                assert ge == pytest.approx(gp, abs=1e-6), (ph, T, x)


def test_pairwise_fe_mg_exchange_matches_pycalphad(sys_):
    """For each phase pair the engine's equal-exchange-potential coexisting composition
    equals pycalphad's own equilibrium tie-line, and K_D is in the expected direction."""
    ex, db, pdb = sys_
    T = 1000.0
    cases = [
        ("OLIVINE", "ORTHOPYROXENE", ex._bulk(0.0, 0.35, 0.9, mtot=1.2), (0.8, 1.15)),
        ("CLINOPYROXENE", "ORTHOPYROXENE", ex._bulk(0.5, 0.35, 2.0, mtot=1.5), (0.2, 0.6)),
        ("CLINOPYROXENE", "OLIVINE", ex._bulk(0.5, 0.35, 1.5, mtot=1.5), (0.2, 0.6)),
    ]
    for phA, phB, bulk, kd_range in cases:
        got = ex.pyc_pair(pdb, phA, phB, T, bulk)
        assert phA in got and phB in got, (phA, phB, got)
        xA_p, xB_p = got[phA], got[phB]
        xA_e = ex.coexist(db, phA, phB, xB_p, T)
        assert xA_e == pytest.approx(xA_p, abs=1e-4), (phA, phB)
        assert kd_range[0] < ex.kd(xA_p, xB_p) < kd_range[1], (phA, phB, ex.kd(xA_p, xB_p))
