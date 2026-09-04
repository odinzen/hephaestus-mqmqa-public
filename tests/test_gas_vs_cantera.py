"""Gas-phase thermochemistry and equilibrium against the Cantera oracle.

Cantera is to the gas phase what pycalphad is to the condensed phases: an independent
implementation whose numbers ours must reproduce. These tests read the shipped open
NASA thermo.dat and check species Gibbs and full ideal-gas equilibria against Cantera.
Skips cleanly if Cantera is not installed.
"""
import os

import numpy as np
import pytest

ct = pytest.importorskip("cantera")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
from mqmqa.gas import read_nasa_thermo, gas_equilibrium  # noqa: E402

HERE = os.path.dirname(__file__)
GAS = os.path.join(HERE, "..", "data", "gas", "nasa_gas.dat")
SET = ["CO", "CO2", "H2", "H2O", "O2", "N2", "CH4", "H", "O", "OH", "HO2", "H2O2"]


@pytest.fixture(scope="module")
def db():
    return read_nasa_thermo(GAS)


@pytest.fixture(scope="module")
def gri():
    return ct.Solution("gri30.yaml")


def test_species_gibbs_matches_cantera(db, gri):
    R = 8.314462618
    for name in SET:
        for T in (400.0, 1000.0, 1600.0, 2400.0):
            mine = db[name].g_rt(T) * R * T
            gri.TP = T, ct.one_atm
            ref = gri.standard_gibbs_RT[gri.species_index(name)] * R * T
            # 0.1 J/mol is the NASA card's own 8-significant-figure precision
            # (~5e-7 relative on a ~-5e5 J/mol Gibbs energy)
            assert abs(mine - ref) < 0.1, (name, T, mine, ref)


@pytest.mark.parametrize("feed,elems", [
    ("CH4:1, O2:2", {"C": 1.0, "H": 4.0, "O": 4.0}),
    ("CO2:1, H2:1", {"C": 1.0, "O": 2.0, "H": 2.0}),
    ("CH4:1, O2:1", {"C": 1.0, "H": 4.0, "O": 2.0}),
])
def test_equilibrium_matches_cantera(db, gri, feed, elems):
    for T in (1200.0, 1800.0, 2400.0):
        for P_atm in (0.5, 1.0, 5.0):
            mine = gas_equilibrium(db, SET, T, P_atm * ct.one_atm, elems)
            gri.TPX = T, P_atm * ct.one_atm, feed
            gri.equilibrate("TP")
            err = max(abs(mine.get(s, 0.0) - gri.X[gri.species_index(s)]) for s in SET)
            assert err < 1e-5, (feed, T, P_atm, err)


def test_pressure_shifts_equilibrium(db, gri):
    # a mole-changing reaction (2 CO + O2 -> 2 CO2) must shift with pressure
    lo = gas_equilibrium(db, SET, 2500.0, 0.1 * ct.one_atm, {"C": 1.0, "O": 2.0})
    hi = gas_equilibrium(db, SET, 2500.0, 10.0 * ct.one_atm, {"C": 1.0, "O": 2.0})
    assert hi["CO2"] > lo["CO2"]        # higher P favors fewer gas moles (more CO2)
