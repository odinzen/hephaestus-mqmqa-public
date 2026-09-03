"""Fe-C steel TDB: pycalphad parity and the measured pure-iron transitions.

web/FeC.tdb is an own transcription (Gustafson 1985 on Dinsdale 1991 unaries).
Two independent checks: (1) pycalphad reads the same file and every phase's
Gibbs energy matches at random site fractions and temperatures, which validates
the reader including both magnetic phases; (2) the pure-iron BCC/FCC/BCC/liquid
transition temperatures come out at their measured values, which validates the
transcription itself (the alpha/gamma balance is carried by the magnetic term,
so these three numbers are the sharpest test of the Inden model there is).
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

from pycalphad import Database as PDatabase, calculate

from mqmqa import Database

HERE = os.path.dirname(__file__)
TDB = os.path.join(HERE, "..", "web", "FeC.tdb")
TOL = 1e-7


@pytest.fixture(scope="module")
def dbs():
    return Database.read(TDB), PDatabase(TDB)


def test_all_phases_match_pycalphad(dbs):
    db, pdb = dbs
    comps = ["FE", "C", "VA"]
    rng = np.random.default_rng(13)
    for pname in db.phase_names:
        p = db.phase_index(pname)
        subls = db.cef_sublattices(p)
        for _ in range(6):
            T = float(rng.uniform(400.0, 2200.0))
            Y = []
            for sl in subls:
                y = rng.uniform(0.02, 1.0, len(sl["constituents"]))
                Y += list(y / y.sum())
            ours = db.cef_gibbs(p, Y, T, per_mole_atoms=True)
            res = calculate(pdb, comps, pname, T=T, P=101325, N=1, points=np.array([Y]))
            assert abs(ours - float(res.GM.values.squeeze())) < TOL, (pname, T)


def _pure_fe_g(db, pname, T):
    p = db.phase_index(pname)
    subls = db.cef_sublattices(p)
    if len(subls) == 1:
        return db.cef_gibbs(p, [1.0], T, per_mole_atoms=True)
    # (FE)(C,VA): pure iron is all-vacancy on the interstitial sublattice
    yva = [1.0, 1e-12, 1.0 - 1e-12]
    return db.cef_gibbs(p, yva, T, per_mole_atoms=True)


def _crossing(db, ph_a, ph_b, lo, hi):
    f = lambda T: _pure_fe_g(db, ph_a, T) - _pure_fe_g(db, ph_b, T)
    flo = f(lo)
    assert flo * f(hi) < 0, (ph_a, ph_b, lo, hi)
    for _ in range(60):
        m = 0.5 * (lo + hi)
        if flo * f(m) <= 0:
            hi = m
        else:
            lo = m
            flo = f(lo)
    return 0.5 * (lo + hi)


def test_pure_iron_transitions(dbs):
    db, _ = dbs
    # alpha (BCC) -> gamma (FCC): measured 1184.8 K; the magnetic term carries this
    t1 = _crossing(db, "BCC_A2", "FCC_A1", 1000.0, 1400.0)
    assert abs(t1 - 1184.8) < 3.0, t1
    # gamma (FCC) -> delta (BCC): measured 1667.5 K
    t2 = _crossing(db, "FCC_A1", "BCC_A2", 1500.0, 1750.0)
    assert abs(t2 - 1667.5) < 3.0, t2
    # delta (BCC) -> liquid: measured 1811 K
    p_liq = db.phase_index("LIQUID")
    g_liq = lambda T: db.cef_gibbs(p_liq, [1e-12, 1.0 - 1e-12], T, per_mole_atoms=True)
    f = lambda T: _pure_fe_g(db, "BCC_A2", T) - g_liq(T)
    lo, hi = 1700.0, 1900.0
    flo = f(lo)
    assert flo * f(hi) < 0
    for _ in range(60):
        m = 0.5 * (lo + hi)
        if flo * f(m) <= 0:
            hi = m
        else:
            lo = m
            flo = f(lo)
    t3 = 0.5 * (lo + hi)
    assert abs(t3 - 1811.0) < 2.0, t3


def test_curie_point_kink_present(dbs):
    # the BCC heat-capacity anomaly at the Curie point: d2G/dT2 jumps near 1043 K
    db, _ = dbs
    cp = lambda T: -T * (_pure_fe_g(db, "BCC_A2", T + 1) - 2 * _pure_fe_g(db, "BCC_A2", T)
                         + _pure_fe_g(db, "BCC_A2", T - 1))
    below, peak, above = cp(900.0), cp(1042.0), cp(1200.0)
    assert peak > below and peak > above
