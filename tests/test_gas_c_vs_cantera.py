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


def test_c_realgas_reduces_to_ideal_at_low_pressure(cdb):
    """At 1 atm a gas is ideal: the Peng-Robinson path must match the ideal path."""
    g, names, els = cdb
    b = _ffi.new("double[]", [float({"C": 1, "O": 2, "H": 2}.get(e, 0.0)) for e in els])
    ideal = _ffi.new("double[]", len(names)); real = _ffi.new("double[]", len(names))
    _lib.mqmqa_gas_equilibrium_ex(g, 1500.0, ct.one_atm, b, 0, ideal)
    _lib.mqmqa_gas_equilibrium_ex(g, 1500.0, ct.one_atm, b, 1, real)
    assert max(abs(ideal[i] - real[i]) for i in range(len(names))) < 1e-4


def test_c_peng_robinson_matches_cantera_pure_co2():
    """The Peng-Robinson compressibility of pure CO2 against Cantera's own PR."""
    import math
    yaml = """
phases:
- {name: c, species: [CO2], thermo: Peng-Robinson, state: {T: 600, P: 1 atm}}
species:
- name: CO2
  composition: {C: 1, O: 2}
  thermo: {model: NASA7, temperature-ranges: [200.0, 1000.0, 6000.0],
    data: [[2.35677352, 8.98459677e-03, -7.12356269e-06, 2.45919022e-09, -1.43699548e-13, -4.83719697e+04, 9.90105222],
           [3.85746029, 4.41437026e-03, -2.21481404e-06, 5.23490188e-10, -4.72084164e-14, -4.8759166e+04, 2.27163806]]}
  equation-of-state: {model: Peng-Robinson, critical-temperature: 304.13 K,
    critical-pressure: 73.77 bar, acentric-factor: 0.225}
"""
    import tempfile, os
    fn = os.path.join(tempfile.gettempdir(), "co2pr_test.yaml")
    open(fn, "w").write(yaml)
    co2 = ct.Solution(fn)
    R, Tc, Pc, w = 8.314462618, 304.13, 73.77e5, 0.225

    def z_mine(T, P):
        kappa = 0.37464 + 1.54226 * w - 0.26992 * w * w
        alpha = (1 + kappa * (1 - math.sqrt(T / Tc))) ** 2
        a = 0.45724 * R * R * Tc * Tc / Pc * alpha
        b = 0.07780 * R * Tc / Pc
        A = a * P / (R * T) ** 2
        B = b * P / (R * T)
        import numpy as np
        r = np.roots([1, -(1 - B), A - 3 * B * B - 2 * B, -(A * B - B * B - B * B * B)])
        return max(r[np.isreal(r)].real)

    for T in (500.0, 600.0, 900.0):
        for P_atm in (50.0, 100.0, 200.0):
            P = P_atm * ct.one_atm
            co2.TP = T, P
            z_ct = P * (co2.volume_mole / 1000.0) / (R * T)   # volume_mole is per kmol
            assert abs(z_ct - z_mine(T, P)) < 5e-3
