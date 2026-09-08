"""Gas coupled to the MQMQA solution slag (iron-saturated), against the Cantera oracle.

gas_slag couples the furnace gas to a real slag through the iron-saturation oxygen potential,
the slag entering only through its FeO activity. Two checks:

  1. Pure-FeO limit: as the slag approaches pure FeO (a_FeO -> 1) the equilibrium CO2/CO must
     recover the Fe/FeO(l) buffer, which we take from Cantera's own multiphase equilibrium of a
     CO-CO2 gas with liquid FeO and liquid iron. Agreement to under a percent validates the whole
     chain (gas oxygen potential and the FeO/Fe references) against an independent implementation.

  2. Slag response: a more silica-rich slag has a lower FeO activity and so must sit under a more
     reducing (lower CO2/CO) gas to stay iron saturated. The activity must fall with silica and
     the equilibrium gas ratio must track it monotonically.

Skips cleanly if Cantera is not installed.
"""
import io
import contextlib
import os
import sys

import pytest

ct = pytest.importorskip("cantera")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
from mqmqa import gas_slag  # noqa: E402

T = 1873.0


def _cantera_fe_feo_buffer():
    full = ct.Solution("gri30.yaml")
    gas = ct.Solution(thermo="ideal-gas", species=[full.species(s) for s in ("CO", "CO2", "O2")])
    sp = {s.name: s for s in ct.Species.list_from_file("nasa_condensed.yaml")}
    feo = ct.Solution(thermo="fixed-stoichiometry", species=[sp["FeO(L)"]])
    fe = ct.Solution(thermo="fixed-stoichiometry", species=[sp["Fe(L)"]])
    gas.TPX = T, ct.one_atm, {"CO": 1, "CO2": 1}
    mix = ct.Mixture([(gas, 2.0), (feo, 0.0), (fe, 1.0)])
    mix.T, mix.P = T, ct.one_atm
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        mix.equilibrate("TP", max_steps=6000)
    gp = mix.phase(0)
    # both condensed phases must survive for this to be the buffer
    assert mix.phase_moles(1) > 1e-6 and mix.phase_moles(2) > 1e-6
    return gp.X[gp.species_index("CO2")] / gp.X[gp.species_index("CO")]


def test_pure_feo_limit_matches_cantera_buffer():
    mine = gas_slag.iron_saturated_gas_ratio(1.0, T)          # a_FeO = 1 (pure FeO)
    ref = _cantera_fe_feo_buffer()
    assert abs(mine - ref) / ref < 0.01, (mine, ref)


def test_iron_wustite_pO2_matches_the_known_buffer():
    # pure-FeO iron saturation is the iron-wustite buffer; its 1873 K oxygen pressure is a
    # textbook value near log10 pO2 = -8.5 (bar). A third, independent physical check.
    assert abs(gas_slag.log10_pO2_iron_saturated(1.0, T) - (-8.5)) < 0.4


def test_slag_activity_falls_with_silica():
    xs = [0.05, 0.15, 0.25, 0.35, 0.45]
    a = [gas_slag.feo_sio2_activity(T, x) for x in xs]
    assert all(0.0 < v < 1.0 for v in a)
    assert all(a[i + 1] < a[i] for i in range(len(a) - 1))     # activity drops with silica


def test_equilibrium_gas_tracks_the_slag():
    # a more silica-rich (lower a_FeO) slag needs a more reducing gas: CO2/CO falls with silica
    xs = [0.05, 0.2, 0.35, 0.45]
    ratios = [gas_slag.iron_saturated_gas_ratio(gas_slag.feo_sio2_activity(T, x), T) for x in xs]
    assert all(r > 0 for r in ratios)
    assert all(ratios[i + 1] < ratios[i] for i in range(len(ratios) - 1))
    # and each is below the pure-FeO buffer, since a_FeO < 1 shifts the gas reducing
    buffer = gas_slag.iron_saturated_gas_ratio(1.0, T)
    assert all(r < buffer for r in ratios)
