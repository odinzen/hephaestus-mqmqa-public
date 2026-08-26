"""NaCl-KCl-MgCl2 ternary (CSP salt) assembled from three binaries, vs pycalphad."""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

pycalphad = pytest.importorskip("pycalphad")
from pycalphad import Database as PDB, equilibrium, variables as v

import mqmqa
from mqmqa import equilibrium as eq
from mqmqa import _abi


def _mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def dat():
    bd = _mod("nkm_build", ROOT / "data" / "nacl-kcl-mgcl2" / "build_dat.py")
    return bd.build()


# Mohan 2018 eutectic, element mole fractions (24.5/20.5/55 wt% NaCl/KCl/MgCl2).
_M = {"NaCl": 24.5 / 58.442, "KCl": 20.5 / 74.551, "MgCl2": 55.0 / 95.211}
_S = sum(_M.values())
NA, K, MG = _M["NaCl"] / _S, _M["KCl"] / _S, _M["MgCl2"] / _S
EL = {"NA": NA, "K": K, "MG": MG, "CL": NA + K + 2 * MG}
TOT = sum(EL.values())


def test_engine_matches_pycalphad_liquid(dat):
    """The Muggianu assembly of the three binaries: C engine == pycalphad, exact."""
    db = mqmqa.Database.read(str(dat))
    p = db.phase_index("NACL-KCL-MGCL2-LIQUID")
    pdb = PDB(str(dat))
    for T in (700.0, 900.0):
        inp = eq.build_inputs(db, p, T, components=["NA", "K", "MG", "CL"])
        ours = _abi.c_equilibrate(inp, EL)["GM"]
        r = equilibrium(pdb, ["NA", "K", "MG", "CL"], ["NACL-KCL-MGCL2-LIQUID"],
                        {v.T: T, v.P: 101325, v.N: 1, v.X("NA"): EL["NA"] / TOT,
                         v.X("K"): EL["K"] / TOT, v.X("MG"): EL["MG"] / TOT})
        assert ours == pytest.approx(float(r.GM.values.ravel()[0]), abs=1.0), T


def test_no_ternary_term(dat):
    """v0.1 carries only the five binary Muggianu terms (no ternary tag)."""
    db = mqmqa.Database.read(str(dat))
    p = db.phase_index("NACL-KCL-MGCL2-LIQUID")
    mx = db.mqmx(p, 700.0)
    assert len(mx["addcat"]) == 5
    assert all(a == -1 for a in mx["addcat"])


def test_eutectic_melting_bracket(dat):
    """Unfitted prediction: fully liquid by 720 K, solid still present at the measured
    660 K (the no-ternary assembly melts ~46 K above Mohan 2018's 387 degC)."""
    pdb = PDB(str(dat))
    cond = lambda T: {v.T: T, v.P: 101325, v.N: 1, v.X("NA"): EL["NA"] / TOT,
                      v.X("K"): EL["K"] / TOT, v.X("MG"): EL["MG"] / TOT}
    hot = equilibrium(pdb, ["NA", "K", "MG", "CL"], list(pdb.phases.keys()), cond(720.0))
    assert sorted(set(str(x) for x in hot.Phase.values.ravel() if x)) == \
        ["NACL-KCL-MGCL2-LIQUID"]
    cold = equilibrium(pdb, ["NA", "K", "MG", "CL"], list(pdb.phases.keys()), cond(660.0))
    assert any(str(x) not in ("NACL-KCL-MGCL2-LIQUID", "") and str(x)
               for x in cold.Phase.values.ravel())
