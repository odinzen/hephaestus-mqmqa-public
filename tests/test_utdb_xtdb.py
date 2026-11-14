"""The uTDB <-> XTDB converter (python/mqmqa/utdb_xtdb.py) on the three shipped uTDB files.

Two checks with different reach:
  - Round trip. uTDB -> XTDB -> uTDB must read as the same database, every phase
    including the MQMQA liquid, at the writers' 1e-14. This covers the proposed MQMQA
    form, but only as a translation check, since the same module writes and reads it.
  - Separate reader. pycalphad-xtdb reads the converted file and pycalphad computes
    every compound-energy-formalism and stoichiometric phase, magnetic ones included,
    against this engine on the source file. pycalphad-xtdb 0.1.2 stops at quadruplet
    species without a Stoichiometry (which the XTDB documentation allows), so those
    lines are removed for this check; it leaves the MQMQA phase out with a warning.
"""
import os
import re
import sys
import warnings

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))
import roundtrip_util as U  # noqa: E402
from mqmqa import Database  # noqa: E402
from mqmqa import utdb_xtdb as C  # noqa: E402

FILES = sorted(os.path.join(U.ROOT, "data", "unified", f)
               for f in os.listdir(os.path.join(U.ROOT, "data", "unified"))
               if f.endswith(".utdb"))
IDS = [os.path.basename(f) for f in FILES]
STEEL = os.path.join(U.ROOT, "data", "unified", "FeC-FeOMgOSiO2.utdb")


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _roundtrip(path, plant=None):
    x = C.utdb_to_xtdb(_text(path), os.path.basename(path))
    if plant:
        x = plant(x)
    return Database.read(path), Database.read_string(C.xtdb_to_utdb(x))


@pytest.mark.parametrize("path", FILES, ids=IDS)
def test_roundtrip_through_xtdb(path):
    orig, back = _roundtrip(path)
    assert U.compare(orig, back) < U.REL_TOL


def test_roundtrip_catches_a_planted_excess_change():
    def plant(x):
        new = re.sub(r'(Id="MQXQ\(SLAG_LIQUID,MG\+2,SI\+4[^"]*" LowT="[^"]*" Expr=")([-+]?)',
                     r"\g<1>\g<2>1", x, count=1)
        assert new != x
        return new
    orig, back = _roundtrip(STEEL, plant)
    with pytest.raises(AssertionError):
        U.compare(orig, back)


def test_roundtrip_catches_a_planted_coordination_change():
    def plant(x):
        new = x.replace('MQMQA="MG+2,SI+4/O-2 1.390538233268252', 'MQMQA="MG+2,SI+4/O-2 1.390538233268253')
        assert new != x
        return new
    orig, back = _roundtrip(STEEL, plant)
    with pytest.raises(AssertionError):
        U.compare(orig, back)


def _pycalphad_worst(path, xtext):
    pytest.importorskip("pycalphad")
    pycalphad_xtdb = pytest.importorskip("pycalphad_xtdb")
    from pycalphad import Database as PDatabase, calculate
    db = Database.read(path)
    xtext = "\n".join(ln for ln in xtext.splitlines() if 'MQMQA="' not in ln)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pdb = PDatabase.from_string(xtext, fmt="xtdb")
    comps = [e for e, _ in db.elements] + ["VA"]
    rng = np.random.default_rng(5)
    worst, n = 0.0, 0
    for p, name in enumerate(db.phase_names):
        if db.phase_kind(p) != 1:
            continue
        subls = db.cef_sublattices(p)
        for T in (300.37, 1000.37, 2200.37):
            Ys = list(U._endmembers(subls)) + [U._random_Y(subls, rng) for _ in range(4)]
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = calculate(pdb, comps, name, T=T, P=101325, N=1, points=np.array(Ys),
                                model=pycalphad_xtdb.XTDBModel)
            for Y, g in zip(Ys, np.atleast_1d(res.GM.values.squeeze())):
                worst = max(worst, U.rel(db.cef_gibbs(p, Y, T, per_mole_atoms=True), float(g)))
                n += 1
    for i, name in enumerate(db.stoich):
        atoms = sum(db.stoich_elements(i))
        for T in (300.37, 1500.37):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = calculate(pdb, comps, name, T=T, P=101325, N=1,
                                model=pycalphad_xtdb.XTDBModel)
            worst = max(worst, U.rel(db.stoich_gibbs(i, T),
                                     float(res.GM.values.squeeze()) * atoms))
            n += 1
    assert n > 0
    return worst


@pytest.mark.parametrize("path", FILES, ids=IDS)
def test_standard_phases_match_pycalphad(path):
    x = C.utdb_to_xtdb(_text(path))
    assert _pycalphad_worst(path, x) < U.ORACLE_TOL


def test_pycalphad_check_catches_a_planted_magnetic_change():
    x = C.utdb_to_xtdb(_text(STEEL))
    planted = x.replace('Id="TC(BCC_A2,FE:VA;0)" LowT="298.15" Expr="+1043;"',
                        'Id="TC(BCC_A2,FE:VA;0)" LowT="298.15" Expr="+1044;"')
    assert planted != x
    assert _pycalphad_worst(STEEL, planted) > U.ORACLE_TOL


def test_magnetic_models_written_as_xtdb_ids():
    x = C.utdb_to_xtdb(_text(STEEL))
    assert re.search(r'<Phase Id="BCC_A2"[^>]*>\s*<Sublattices.*?</Sublattices>\s*'
                     r'<AmendPhase Models="IHJBCC" />', x, re.S)
    assert re.search(r'<Phase Id="FCC_A1"[^>]*>\s*<Sublattices.*?</Sublattices>\s*'
                     r'<AmendPhase Models="IHJREST" />', x, re.S)


def test_unsupported_input_refused():
    with pytest.raises(C.ConversionError, match="no XTDB model Id"):
        C.utdb_to_xtdb(" ELEMENT FE BCC_A2 55.8 0 0 !\n"
                       " TYPE_DEFINITION & GES A_P_D BCC_A2 MAGNETIC -2.0 0.4 !\n"
                       " PHASE BCC_A2 %& 1 1 !\n CONSTITUENT BCC_A2 : FE : !\n")
    with pytest.raises(C.ConversionError, match="only :Q"):
        C.utdb_to_xtdb(" PHASE GAS:G G 1 1 !\n")
