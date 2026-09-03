"""Recycling uTDB round-trip: alloy + ternary salt flux must reproduce the .dat physics.

web/AlZn-NaClKClMgCl2.utdb carries the NaCl-KCl-MgCl2 assessment (shipped as
data/nacl-kcl-mgcl2/NaCl-KCl-MgCl2.dat) through the uTDB extension statements,
alongside the Al-Zn alloy of web/AlZn.tdb. Beyond the binary demo this exercises
a 2+ charged cation (Mg), the 6-6-3-3 coordination row, a true ternary MQXT
excess term, and a CEF solid solution (halite) riding in the same file.
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
DAT = os.path.join(HERE, "..", "data", "nacl-kcl-mgcl2", "NaCl-KCl-MgCl2.dat")
UTDB = os.path.join(HERE, "..", "web", "AlZn-NaClKClMgCl2.utdb")
ALZN = os.path.join(HERE, "..", "web", "AlZn.tdb")

TOL = 1e-7


@pytest.fixture(scope="module")
def dbs():
    return Database.read(DAT), Database.read(UTDB)


def _salt_phases(dat, uni):
    return dat.phase_index("NACL-KCL-MGCL2-LIQUID"), uni.phase_index("SALT_LIQUID")


def test_structure_matches(dbs):
    dat, uni = dbs
    pd_, pu = _salt_phases(dat, uni)
    assert dat.is_subq(pd_) and uni.is_subq(pu)
    import re
    el = lambda n: re.match(r"[A-Z]+", n.upper()).group(0)
    assert [el(c["name"]) for c in dat.cations(pd_)] == [el(c["name"]) for c in uni.cations(pu)]
    assert [c["charge"] for c in dat.cations(pd_)] == [c["charge"] for c in uni.cations(pu)]
    assert [a["charge"] for a in dat.anions(pd_)] == [a["charge"] for a in uni.anions(pu)]
    assert dat.mqmz(pd_) == uni.mqmz(pu)


def test_pair_gibbs_matches(dbs):
    dat, uni = dbs
    pd_, pu = _salt_phases(dat, uni)
    for T in (500.0, 800.0, 987.0, 1200.0):
        gd, gu = dat.pairs(pd_, T), uni.pairs(pu, T)
        assert np.allclose(gd["G"], gu["G"], atol=TOL)
        assert np.allclose(gd["zeta"], gu["zeta"], atol=1e-12)
        assert np.allclose(gd["stoich"], gu["stoich"], atol=1e-12)


def test_excess_matches_including_ternary(dbs):
    dat, uni = dbs
    pd_, pu = _salt_phases(dat, uni)
    xd, xu = dat.mqmx(pd_, 900.0), uni.mqmx(pu, 900.0)
    assert xd == xu


def test_equilibrium_matches(dbs):
    dat, uni = dbs
    pd_, pu = _salt_phases(dat, uni)
    comps = [
        {"NA": 0.5, "K": 0.3, "MG": 0.2},
        {"NA": 0.2, "K": 0.2, "MG": 0.6},
        {"NA": 0.8, "K": 0.1, "MG": 0.1},
    ]
    for T in (800.0, 1000.0, 1150.0):
        ind = build_inputs(dat, pd_, T)
        inu = build_inputs(uni, pu, T)
        for c in comps:
            full = dict(c)
            full["CL"] = c["NA"] + c["K"] + 2.0 * c["MG"]
            gd = c_equilibrate(ind, full)["GM"]
            gu = c_equilibrate(inu, full)["GM"]
            assert abs(gd - gu) < TOL, (T, c, gd, gu)


def test_halite_cef_matches(dbs):
    dat, uni = dbs
    pd_, pu = dat.phase_index("HALITE"), uni.phase_index("HALITE")
    rng = np.random.default_rng(7)
    for _ in range(8):
        y = float(rng.uniform(0.02, 0.98))
        T = float(rng.uniform(400.0, 1100.0))
        assert abs(dat.cef_gibbs(pd_, [y, 1 - y, 1.0], T, 1)
                   - uni.cef_gibbs(pu, [y, 1 - y, 1.0], T, 1)) < TOL


def test_solids_match(dbs):
    dat, uni = dbs
    names_d = [n.upper() for n in dat.stoich]
    names_u = [n.upper() for n in uni.stoich]
    for nm_d, nm_u in (("MGCL2_SOLID", "MGCL2_SOLID"), ("KMGCL3", "KMGCL3_SOLID")):
        i_d, i_u = names_d.index(nm_d), names_u.index(nm_u)
        for T in (500.0, 758.0, 987.0):
            assert abs(dat.stoich_gibbs(i_d, T) - uni.stoich_gibbs(i_u, T)) < TOL


def test_alloy_phases_match_alzn_tdb(dbs):
    _, uni = dbs
    ref = Database.read(ALZN)
    rng = np.random.default_rng(11)
    for uname, rname in (("ALLOY_LIQUID", "LIQUID"), ("FCC_A1", "FCC_A1"), ("HCP_A3", "HCP_A3")):
        pu, pr = uni.phase_index(uname), ref.phase_index(rname)
        for _ in range(6):
            y = float(rng.uniform(0.02, 0.98))
            T = float(rng.uniform(320.0, 1900.0))
            assert abs(uni.cef_gibbs(pu, [y, 1 - y], T, 1)
                       - ref.cef_gibbs(pr, [y, 1 - y], T, 1)) < TOL
