"""TDB front-end vs the pycalphad oracle.

The reader parses the Thermo-Calc TDB dialect into the same internal database
the ChemSage reader builds. These tests load pycalphad's own shipped test TDBs
and compare every solution phase's Gibbs energy, and the line compounds, against
pycalphad at random site fractions and temperatures to machine precision. The
negative tests pin the scope: models outside the subset (the ionic
two-sublattice liquid) must fail loudly, never compute silently wrong; the
magnetic Inden-Hillert-Jarl contribution is in the subset and oracle-checked.
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

import pycalphad
from pycalphad import Database as PDatabase, calculate

from mqmqa import Database

ROOT = os.path.join(os.path.dirname(pycalphad.__file__), "..", "pycalphad", "tests", "databases")
TOL = 1e-7   # J/mol-atom; observed worst ~1e-10


def _oracle_db(fname):
    path = os.path.join(ROOT, fname)
    if not os.path.exists(path):
        pytest.skip(f"pycalphad test database {fname} not present")
    return Database.read(path), PDatabase(path), path


@pytest.mark.parametrize("fname", ["alzn_mey.tdb", "pbsn.tdb", "Al-Mg_Zhong.tdb",
                                   "crfe_bcc_magnetic.tdb"])
def test_solution_phases_match_pycalphad(fname):
    db, pdb, _ = _oracle_db(fname)
    comps = [e for e, m in db.elements] + ["VA"]
    rng = np.random.default_rng(7)
    for pname in db.phase_names:
        p = db.phase_index(pname)
        subls = db.cef_sublattices(p)
        for _ in range(6):
            T = float(rng.uniform(320.0, 2400.0))
            Y = []
            for sl in subls:
                y = rng.uniform(0.02, 1.0, len(sl["constituents"]))
                Y += list(y / y.sum())
            ours = db.cef_gibbs(p, Y, T, per_mole_atoms=True)
            res = calculate(pdb, comps, pname, T=T, P=101325, N=1, points=np.array([Y]))
            assert abs(ours - float(res.GM.values.squeeze())) < TOL, (fname, pname, T)


def test_line_compounds_match_pycalphad():
    # ALMG_BETA and ALMG_EPSILON are single-endmember phases -> stoichiometric list
    db, pdb, _ = _oracle_db("Al-Mg_Zhong.tdb")
    names = list(db.stoich)
    assert "ALMG_BETA" in names and "ALMG_EPSILON" in names
    rng = np.random.default_rng(3)
    for i, name in enumerate(names):
        # per-formula-unit atoms, to convert pycalphad's per-mole-atoms GM
        import numpy as _np
        elems = db.stoich_elements(i) if hasattr(db, "stoich_elements") else None
        for _ in range(5):
            T = float(rng.uniform(400.0, 800.0))
            ours = db.stoich_gibbs(i, T)
            res = calculate(pdb, [e for e, m in db.elements] + ["VA"], name,
                            T=T, P=101325, N=1)
            gm_atom = float(res.GM.values.squeeze())
            # scale: moles of atoms per formula unit of the phase
            ph = pdb.phases[name]
            atoms = sum(float(r) for r in ph.sublattices)
            assert abs(ours - gm_atom * atoms) < TOL * atoms, (name, T)


def test_extrapolates_above_last_interval_like_pycalphad():
    # ZN liquid's function ends at 1700 K; the TDB convention extrapolates
    db, pdb, _ = _oracle_db("alzn_mey.tdb")
    p = db.phase_index("LIQUID")
    ours = db.cef_gibbs(p, [0.000001, 0.999999], 2000.0, per_mole_atoms=True)
    res = calculate(pdb, ["AL", "ZN"], "LIQUID", T=2000.0, P=101325, N=1,
                    points=np.array([[0.000001, 0.999999]]))
    assert abs(ours - float(res.GM.values.squeeze())) < TOL


@pytest.mark.parametrize("fname,needle", [
    ("al2o3_nd2o3_zro2.tdb", "ionic"),
])
def test_out_of_subset_models_fail_loudly(fname, needle):
    path = os.path.join(ROOT, fname)
    if not os.path.exists(path):
        pytest.skip(f"{fname} not present")
    with pytest.raises(Exception) as exc:
        Database.read(path)
    assert needle in str(exc.value).lower()


def test_chemsage_files_still_detect_as_chemsage():
    # the dat family must keep loading through the original reader
    dat = os.path.join(os.path.dirname(__file__), "..", "web", "LiCl-KCl.dat")
    db = Database.read(dat)
    assert db.phase_names == ["LICL-KCL-LIQUID"]
