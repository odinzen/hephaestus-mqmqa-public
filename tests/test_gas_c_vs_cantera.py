"""The C-core gas solver (same code the WebAssembly browser build runs) against Cantera.

test_gas_vs_cantera.py checks the Python reference implementation; this checks the C
engine through the ABI, so the numbers the browser produces are validated too. Skips
cleanly if Cantera or the built library is missing.
"""
import os
import sys

import pytest

ct = pytest.importorskip("cantera")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
try:
    from mqmqa._abi import _lib, _ffi
except OSError:
    pytest.skip("mqmqa shared library not built", allow_module_level=True)

HERE = os.path.dirname(__file__)
GAS = os.path.join(HERE, "..", "data", "gas", "nasa_gas.dat")
CHECK = ["CO", "CO2", "H2", "H2O", "O2"]


@pytest.fixture(scope="module")
def cdb():
    text = open(GAS, encoding="utf-8").read()
    g = _lib.mqmqa_gas_read_string(text.encode())
    assert g != _ffi.NULL, _ffi.string(_lib.mqmqa_gas_error()).decode()
    nsp = _lib.mqmqa_gas_num_species(g)
    nel = _lib.mqmqa_gas_num_elements(g)
    names = [_ffi.string(_lib.mqmqa_gas_species_name(g, i)).decode() for i in range(nsp)]
    els = [_ffi.string(_lib.mqmqa_gas_element(g, e)).decode() for e in range(nel)]
    yield g, names, els
    _lib.mqmqa_gas_free(g)


def _c_equil(cdb, T, P, elem):
    g, names, els = cdb
    b = _ffi.new("double[]", [float(elem.get(e, 0.0)) for e in els])
    out = _ffi.new("double[]", len(names))
    rc = _lib.mqmqa_gas_equilibrium(g, T, P, b, out)
    assert rc == 0
    return {names[i]: out[i] for i in range(len(names))}


@pytest.mark.parametrize("feed,elem", [
    ("CH4:1, O2:2", {"C": 1.0, "H": 4.0, "O": 4.0}),
    ("CH4:1, O2:1", {"C": 1.0, "H": 4.0, "O": 2.0}),
    ("CO2:1, H2:1", {"C": 1.0, "O": 2.0, "H": 2.0}),
])
def test_c_gas_matches_cantera(cdb, feed, elem):
    gri = ct.Solution("gri30.yaml")
    for T in (1200.0, 1800.0, 2400.0):
        for P_atm in (0.5, 1.0, 5.0):
            mine = _c_equil(cdb, T, P_atm * ct.one_atm, elem)
            gri.TPX = T, P_atm * ct.one_atm, feed
            gri.equilibrate("TP")
            err = max(abs(mine.get(s, 0.0) - gri.X[gri.species_index(s)]) for s in CHECK)
            assert err < 1e-5, (feed, T, P_atm, err)
