"""Steelmaking uTDB round-trip: basic steel + the slag must reproduce their sources.

web/FeC-FeOMgOSiO2.utdb carries the FeO-MgO-SiO2 slag assessment (shipped as
web/FeO-MgO-SiO2-combined.dat) through the uTDB extension statements, alongside
the Fe-C steel of web/FeC.tdb with its magnetic BCC and FCC. Beyond the earlier
demos this exercises two-interval MQG pairs, zeta-valued coordination numbers,
T^0.5 endmember terms, three-sublattice CEF solid solutions, and the magnetic
model riding next to an MQMQA liquid in one file.
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

from mqmqa import Database
from mqmqa.equilibrium import build_inputs
from mqmqa._abi import c_equilibrate

HERE = os.path.dirname(__file__)
DAT = os.path.join(HERE, "..", "web", "FeO-MgO-SiO2-combined.dat")
UTDB = os.path.join(HERE, "..", "web", "FeC-FeOMgOSiO2.utdb")
FEC = os.path.join(HERE, "..", "web", "FeC.tdb")

TOL = 1e-7


@pytest.fixture(scope="module")
def dbs():
    return Database.read(DAT), Database.read(UTDB)


def _slag_phases(dat, uni):
    return dat.phase_index("FEO-MGO-SIO2-LIQUID"), uni.phase_index("SLAG_LIQUID")


def test_structure_matches(dbs):
    dat, uni = dbs
    pd_, pu = _slag_phases(dat, uni)
    assert dat.is_subq(pd_) and uni.is_subq(pu)
    assert [c["charge"] for c in dat.cations(pd_)] == [c["charge"] for c in uni.cations(pu)]
    assert [a["charge"] for a in dat.anions(pd_)] == [a["charge"] for a in uni.anions(pu)]
    assert dat.mqmz(pd_) == uni.mqmz(pu)


def test_pair_gibbs_matches_across_intervals(dbs):
    dat, uni = dbs
    pd_, pu = _slag_phases(dat, uni)
    # 1500/1700 straddle the FeO interval break at 1650; 3200 exceeds MgO's at 3098
    for T in (1500.0, 1700.0, 2100.0, 3200.0):
        gd, gu = dat.pairs(pd_, T), uni.pairs(pu, T)
        assert np.allclose(gd["G"], gu["G"], atol=TOL)
        assert np.allclose(gd["zeta"], gu["zeta"], atol=1e-12)
        assert np.allclose(gd["stoich"], gu["stoich"], atol=1e-12)


def test_excess_matches(dbs):
    dat, uni = dbs
    pd_, pu = _slag_phases(dat, uni)
    assert dat.mqmx(pd_, 1873.0) == uni.mqmx(pu, 1873.0)


def test_equilibrium_matches(dbs):
    dat, uni = dbs
    pd_, pu = _slag_phases(dat, uni)
    comps = [
        {"FE": 0.4, "MG": 0.3, "SI": 0.3},
        {"FE": 0.2, "MG": 0.2, "SI": 0.6},
        {"FE": 0.6, "MG": 0.3, "SI": 0.1},
    ]
    for T in (1700.0, 1873.0, 2000.0):
        ind = build_inputs(dat, pd_, T)
        inu = build_inputs(uni, pu, T)
        for c in comps:
            full = dict(c)
            full["O"] = c["FE"] + c["MG"] + 2.0 * c["SI"]
            gd = c_equilibrate(ind, full)["GM"]
            gu = c_equilibrate(inu, full)["GM"]
            assert abs(gd - gu) < TOL, (T, c, gd, gu)


def test_silicate_solid_solutions_match(dbs):
    dat, uni = dbs
    rng = np.random.default_rng(17)
    for name in ("OLIVINE", "ORTHOPYROXENE"):
        pd_, pu = dat.phase_index(name), uni.phase_index(name)
        for _ in range(8):
            y = float(rng.uniform(0.02, 0.98))
            T = float(rng.uniform(600.0, 2000.0))
            Y = [y, 1 - y, 1.0, 1.0]
            assert abs(dat.cef_gibbs(pd_, Y, T, 1) - uni.cef_gibbs(pu, Y, T, 1)) < TOL, (name, T)


def test_oxide_solids_match(dbs):
    dat, uni = dbs
    names_d = [n.upper() for n in dat.stoich]
    names_u = [n.upper() for n in uni.stoich]
    for nm in ("CRISTOBALITE", "PERICLASE", "WUSTITE"):
        i_d, i_u = names_d.index(nm), names_u.index(nm)
        for T in (900.0, 1650.0, 1873.0):
            assert abs(dat.stoich_gibbs(i_d, T) - uni.stoich_gibbs(i_u, T)) < TOL


def test_steel_phases_match_fec_tdb(dbs):
    _, uni = dbs
    ref = Database.read(FEC)
    rng = np.random.default_rng(19)
    pairs = [("STEEL_LIQUID", "LIQUID"), ("BCC_A2", "BCC_A2"), ("FCC_A1", "FCC_A1")]
    for uname, rname in pairs:
        pu, pr = uni.phase_index(uname), ref.phase_index(rname)
        subls = uni.cef_sublattices(pu)
        for _ in range(6):
            T = float(rng.uniform(400.0, 2200.0))
            Y = []
            for sl in subls:
                y = rng.uniform(0.02, 1.0, len(sl["constituents"]))
                Y += list(y / y.sum())
            assert abs(uni.cef_gibbs(pu, Y, T, 1) - ref.cef_gibbs(pr, Y, T, 1)) < TOL, (uname, T)
    # cementite and graphite ride as stoichiometric phases in both containers
    su = [n.upper() for n in uni.stoich]
    sr = [n.upper() for n in ref.stoich]
    for nm in ("CEMENTITE", "GRAPHITE"):
        i_u, i_r = su.index(nm), sr.index(nm)
        for T in (600.0, 1000.0, 1400.0):
            assert abs(uni.stoich_gibbs(i_u, T) - ref.stoich_gibbs(i_r, T)) < TOL
