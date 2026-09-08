"""Coupled gas + condensed equilibrium against the Cantera oracle.

gas_condensed_equilibrium shares one set of element potentials between the ideal gas and the
condensed species, so the gas and the condensate settle to a common element (oxygen) potential.
These tests check that coupling on the steel-relevant cases: the Boudouard balance
C(gr) + CO2 = 2 CO, and iron-oxide reduction FeO + CO = Fe + CO2.

To isolate the coupling ALGORITHM from thermodynamic-data differences, both sides use Cantera's
own thermo (a species-reduced gri30 gas and NASA condensed phases), so the only thing under test
is the element-potential/active-set math. Feeds are kept off the exact-stoichiometric knife edges
where the gas oxygen vanishes (element potential -> -inf), which is a measure-zero pathology, and
each comparison is skipped unless Cantera's own multiphase solver reports convergence.

Skips cleanly if Cantera is not installed.
"""
import io
import contextlib
import os
import sys

import numpy as np
import pytest

ct = pytest.importorskip("cantera")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
from mqmqa.gas import gas_condensed_equilibrium, gas_equilibrium, Condensed  # noqa: E402


@pytest.fixture(scope="module")
def gas_co():
    full = ct.Solution("gri30.yaml")
    names = ["CO", "CO2", "O2", "C", "O"]
    gas = ct.Solution(thermo="ideal-gas", species=[full.species(s) for s in names])

    class Spec:
        def __init__(self, n):
            self.name = n
            self.comp = {e: gas.n_atoms(n, e) for e in gas.element_names if gas.n_atoms(n, e)}
        def g_rt(self, T):
            gas.TP = T, ct.one_atm
            return gas.standard_gibbs_RT[gas.species_index(self.name)]

    return gas, names, {n: Spec(n) for n in names}


def _mix_equilibrate(phases, T, P):
    mix = ct.Mixture(phases)
    mix.T, mix.P = T, P
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        mix.equilibrate("TP", max_steps=8000)
    return mix, ("FAILURE" not in buf.getvalue())


def test_empty_condensed_reproduces_gas_solver(gas_co):
    gas, names, db = gas_co
    for T in (900.0, 1500.0, 2200.0):
        feed = {"C": 1.0, "O": 2.0}
        a = gas_equilibrium(db, names, T, ct.one_atm, feed)
        b, cond, _ = gas_condensed_equilibrium(db, names, [], T, ct.one_atm, feed)
        assert not cond
        assert max(abs(a[s] - b[s]) for s in names) < 1e-9


def test_boudouard_vs_cantera(gas_co):
    gas, names, db = gas_co
    graphite = ct.Solution("graphite.yaml")

    def g_gr(T):
        graphite.TP = T, ct.one_atm
        return graphite.standard_gibbs_RT[0]

    checked = 0
    for (C, O) in [(2.0, 1.0), (1.5, 1.0), (1.0, 1.5), (3.0, 2.0)]:
        for T in (900.0, 1100.0, 1400.0, 1800.0):
            for Patm in (0.5, 1.0):
                P = Patm * ct.one_atm
                gas.TPX = T, P, {"O2": max(O / 2, 1e-12)}
                mix, ok = _mix_equilibrate([(gas, max(O / 2, 1e-12)),
                                            (graphite, max(C, 0.0))], T, P)
                if not ok:
                    continue
                gp = mix.phase(0)
                Xc = {s: gp.X[gp.species_index(s)] for s in names}
                grc = mix.phase_moles(1)
                cond = [Condensed("C(gr)", {"C": 1}, g_gr(T))]
                Xm, cm, _ = gas_condensed_equilibrium(db, names, cond, T, P, {"C": C, "O": O})
                gerr = max(abs(Xm[s] - Xc[s]) for s in names)
                assert gerr < 2e-3, (C, O, T, Patm, gerr)
                assert abs(cm.get("C(gr)", 0.0) - grc) < 2e-3, (C, O, T, Patm)
                checked += 1
    assert checked >= 10


def test_iron_oxide_reduction_vs_cantera(gas_co):
    gas, names, db = gas_co
    sp = {s.name: s for s in ct.Species.list_from_file("nasa_condensed.yaml")}
    cond_names = ["C(gr)", "FeO(s)", "Fe(a)"]
    comp = {"C(gr)": {"C": 1}, "FeO(s)": {"Fe": 1, "O": 1}, "Fe(a)": {"Fe": 1}}
    cphase = {n: ct.Solution(thermo="fixed-stoichiometry", species=[sp[n]]) for n in cond_names}

    def g_cond(n, T):
        cphase[n].TP = T, ct.one_atm
        return cphase[n].standard_gibbs_RT[0]

    checked = 0
    # oxygen kept clear of the exact O == Fe knife edge, Fe(a) within its valid T range
    for feed in [{"Fe": 1.0, "C": 1.5, "O": 1.5}, {"Fe": 1.0, "C": 3.0, "O": 1.15},
                 {"Fe": 2.0, "C": 1.0, "O": 2.2}, {"Fe": 1.0, "C": 0.5, "O": 1.5}]:
        for T in (900.0, 1050.0, 1150.0):
            P = ct.one_atm
            gas.TPX = T, P, {"O2": max(feed["O"] / 2, 1e-12)}
            phases = [(gas, max(feed["O"] / 2, 1e-12)),
                      (cphase["C(gr)"], max(feed["C"], 0.0)),
                      (cphase["FeO(s)"], 0.0), (cphase["Fe(a)"], feed["Fe"])]
            mix, ok = _mix_equilibrate(phases, T, P)
            if not ok:
                continue
            gp = mix.phase(0)
            Xc = {s: gp.X[gp.species_index(s)] for s in names}
            cmc = {n: mix.phase_moles(1 + i) for i, n in enumerate(cond_names)}
            # skip if Cantera's own VCS returned a nonsense amount (it does at some low-T points)
            if any(v > 1e3 or v < -1e-6 for v in cmc.values()):
                continue
            cond = [Condensed(n, comp[n], g_cond(n, T)) for n in cond_names]
            Xm, cmm, _ = gas_condensed_equilibrium(db, names, cond, T, P, feed)
            assert max(abs(Xm[s] - Xc[s]) for s in names) < 2e-3, (feed, T)
            for n in cond_names:
                assert abs(cmm.get(n, 0.0) - cmc[n]) < 2e-3, (feed, T, n)
            checked += 1
    assert checked >= 8
