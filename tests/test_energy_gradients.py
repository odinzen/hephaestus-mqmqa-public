"""The exact gradients of the MQMQA entropy and excess energies equal central
differences of the energies themselves, on every liquid the engine evaluates."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
sys.path.insert(0, str(ROOT / "tests"))

import mqmqa
import roundtrip_util as U
from mqmqa import equilibrium as eqm
from mqmqa._abi import _ffi, _lib

SHIPPED = [ROOT / p for p in (
    "data/feo-sio2/FeO-SiO2-liquid.dat",
    "data/feo-mgo-sio2/FeO-MgO-SiO2-liquid.dat",          # chemical groups + additional cation
    "data/cao-al2o3-sio2/CaO-Al2O3-SiO2.dat",
    "data/cao-feo-mgo-sio2/CaO-FeO-MgO-SiO2-liquid.dat",
    "data/nacl-kcl-mgcl2/NaCl-KCl-MgCl2.dat",
)]
# pycalphad's fixtures add the G code, anion mixing, reciprocal SUBQ and SUBG liquids
FIXTURES = [Path(p) for p in U.pycalphad_fixtures([
    "MQMQA-tern-tests.dat", "Shishin_Fe-Sb-O-S_slag.dat", "2026-Dixon-Na-K-Cl-I.dat",
    "KF-NIF2_switched.dat", "Ocadiz-Flores.dat", "Viitala.dat"])]


def _liquids():
    out = []
    for path in SHIPPED + FIXTURES:
        if not path.exists():
            continue
        try:
            db = mqmqa.Database.read(path)
        except OSError:
            continue
        for p, name in enumerate(db.phase_names):
            if db.phase_kind(p) == 0 and db.excess_unsupported(p) is None:
                out.append(pytest.param(path, p, id=f"{path.stem}:{name}"))
    return out


_ints = lambda v: _ffi.new("int[]", [int(a) for a in v])
_dbl = lambda v: _ffi.new("double[]", [float(a) for a in v])


def _entropy_args(inp, X, T):
    return [float(T), int(inp["ncat"]), int(inp["nan"]), len(X), _ints(inp["qca"]),
            _ints(inp["qcb"]), _ints(inp["qax"]), _ints(inp["qay"]), _dbl(X), _dbl(inp["Za"]),
            _dbl(inp["Zb"]), _dbl(inp["Zx"]), _dbl(inp["Zy"]), _dbl(np.ravel(inp["zeta"])),
            int(inp["soln_type"]), float(inp["R_own"])]


def _excess_args(inp, X):
    ex = inp["ex"]
    return [int(inp["ncat"]), int(inp["nan"]), len(X), _ints(inp["qca"]), _ints(inp["qcb"]),
            _ints(inp["qax"]), _ints(inp["qay"]), _dbl(X), _dbl(inp["Za"]), _dbl(inp["Zb"]),
            _dbl(inp["Zx"]), _dbl(inp["Zy"]), int(inp["soln_type"]), len(ex["A"]),
            _ints(ex["mix"]), _ints(ex["code"]), _ints(ex["A"]), _ints(ex["B"]), _ints(ex["X"]),
            _ints(ex["Y"]), _dbl(ex["p"]), _dbl(ex["q"]), _dbl(ex["L"]), _dbl(ex["r"]),
            _ints(ex["addcat"]), _ints(inp["cat_group"]), _ints(inp["an_group"])]


@pytest.mark.parametrize("path,p", _liquids())
def test_gradients_match_central_differences(path, p):
    db = mqmqa.Database.read(path)
    T = 1500.0
    inp = eqm.build_inputs(db, p, T)
    n = len(inp["qca"])
    rng = np.random.default_rng(5)
    h = 1e-6
    for _ in range(4):
        X = rng.dirichlet(np.ones(n) * 2.0) * 0.98 + 0.02 / n       # every fraction above h
        g_ent = _ffi.new("double[]", n)
        g_exc = _ffi.new("double[]", n)
        _lib.mqmqa_ideal_mixing_gradient(*_entropy_args(inp, X, T), g_ent)
        _lib.mqmqa_excess_gradient(*_excess_args(inp, X), g_exc)
        for q in range(n):
            Xp, Xm = X.copy(), X.copy()
            Xp[q] += h
            Xm[q] -= h
            fd_ent = (_lib.mqmqa_ideal_mixing_energy(*_entropy_args(inp, Xp, T))
                      - _lib.mqmqa_ideal_mixing_energy(*_entropy_args(inp, Xm, T))) / (2 * h)
            fd_exc = (_lib.mqmqa_excess_energy(*_excess_args(inp, Xp))
                      - _lib.mqmqa_excess_energy(*_excess_args(inp, Xm))) / (2 * h)
            assert g_ent[q] == pytest.approx(fd_ent, rel=1e-6, abs=1e-3)
            assert g_exc[q] == pytest.approx(fd_exc, rel=1e-6, abs=1e-3)


def test_the_test_would_catch_a_wrong_gradient():
    """Planted error: the entropy gradient is not the excess gradient."""
    path = SHIPPED[1]
    db = mqmqa.Database.read(path)
    p = next(i for i in range(len(db.phase_names)) if db.phase_kind(i) == 0)
    inp = eqm.build_inputs(db, p, 1500.0)
    n = len(inp["qca"])
    X = np.full(n, 1.0 / n)
    g_ent = _ffi.new("double[]", n)
    g_exc = _ffi.new("double[]", n)
    _lib.mqmqa_ideal_mixing_gradient(*_entropy_args(inp, X, 1500.0), g_ent)
    _lib.mqmqa_excess_gradient(*_excess_args(inp, X), g_exc)
    assert any(abs(g_ent[q] - g_exc[q]) > 1.0 for q in range(n))
