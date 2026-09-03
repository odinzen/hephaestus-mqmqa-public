"""uTDB round-trip: the unified dialect must reproduce the .dat physics exactly.

web/AlZn-LiClKCl.utdb carries the LiCl-KCl MQMQA assessment (shipped as
web/LiCl-KCl.dat) through the uTDB extension statements, alongside the Al-Zn
alloy of web/AlZn.tdb. These tests assert that every energy path agrees between
the containers at machine precision: pair Gibbs, coordination rows, SNN excess,
single-phase equilibria, stoichiometric solids, and the alloy CEF phases.
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
DAT = os.path.join(HERE, "..", "web", "LiCl-KCl.dat")
UTDB = os.path.join(HERE, "..", "web", "AlZn-LiClKCl.utdb")
ALZN = os.path.join(HERE, "..", "web", "AlZn.tdb")

TOL = 1e-7


@pytest.fixture(scope="module")
def dbs():
    return Database.read(DAT), Database.read(UTDB)


def test_salt_structure_matches(dbs):
    dat, uni = dbs
    pd_, pu = dat.phase_index("LICL-KCL-LIQUID"), uni.phase_index("SALT_LIQUID")
    assert dat.is_subq(pd_) and uni.is_subq(pu)
    import re
    el = lambda n: re.match(r"[A-Z]+", n).group(0)
    assert [el(c["name"]) for c in dat.cations(pd_)] == [el(c["name"]) for c in uni.cations(pu)]
    assert [el(a["name"]) for a in dat.anions(pd_)] == [el(a["name"]) for a in uni.anions(pu)]
    assert dat.mqmz(pd_) == uni.mqmz(pu)


def test_salt_pair_gibbs_matches(dbs):
    dat, uni = dbs
    pd_, pu = dat.phase_index("LICL-KCL-LIQUID"), uni.phase_index("SALT_LIQUID")
    for T in (400.0, 700.0, 1044.0, 1500.0):
        gd, gu = dat.pairs(pd_, T), uni.pairs(pu, T)
        assert np.allclose(gd["G"], gu["G"], atol=TOL)
        assert np.allclose(gd["zeta"], gu["zeta"], atol=1e-12)
        assert np.allclose(gd["stoich"], gu["stoich"], atol=1e-12)


def test_salt_excess_matches(dbs):
    dat, uni = dbs
    pd_, pu = dat.phase_index("LICL-KCL-LIQUID"), uni.phase_index("SALT_LIQUID")
    xd, xu = dat.mqmx(pd_, 900.0), uni.mqmx(pu, 900.0)
    assert xd == xu


def test_salt_equilibrium_matches(dbs):
    dat, uni = dbs
    pd_, pu = dat.phase_index("LICL-KCL-LIQUID"), uni.phase_index("SALT_LIQUID")
    for T in (700.0, 900.0, 1100.0):
        ind = build_inputs(dat, pd_, T)
        inu = build_inputs(uni, pu, T)
        for t in (0.1, 0.4, 0.585, 0.9):
            comp = {"LI": 1 - t, "K": t, "CL": 1.0}
            gd = c_equilibrate(ind, comp)["GM"]
            gu = c_equilibrate(inu, comp)["GM"]
            assert abs(gd - gu) < TOL, (T, t, gd, gu)


def test_salt_solids_match(dbs):
    dat, uni = dbs
    names_d = list(dat.stoich)
    names_u = list(uni.stoich)
    for nm_d, nm_u in (("LICL_SOLID", "LICL_SOLID"), ("KCL_SOLID", "KCL_SOLID")):
        i_d, i_u = names_d.index(nm_d), names_u.index(nm_u)
        for T in (500.0, 876.0, 1043.0):
            assert abs(dat.stoich_gibbs(i_d, T) - uni.stoich_gibbs(i_u, T)) < TOL


def test_alloy_phases_match_alzn_tdb(dbs):
    _, uni = dbs
    ref = Database.read(ALZN)
    rng = np.random.default_rng(5)
    pairs = [("ALLOY_LIQUID", "LIQUID"), ("FCC_A1", "FCC_A1"), ("HCP_A3", "HCP_A3")]
    for uname, rname in pairs:
        pu, pr = uni.phase_index(uname), ref.phase_index(rname)
        for _ in range(6):
            y = float(rng.uniform(0.02, 0.98))
            T = float(rng.uniform(320.0, 1900.0))
            assert abs(uni.cef_gibbs(pu, [y, 1 - y], T, 1)
                       - ref.cef_gibbs(pr, [y, 1 - y], T, 1)) < TOL
