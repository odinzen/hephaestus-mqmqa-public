"""Declaring a database's R, and the writers recording it.

A database that does not state R can be declared to have been assessed with one of the
labeled values; that value is then its own, used by its calculations in the
as-assessed mode. Every writer records the database's own R, never a forced mode's
(FUNCTION R in .tdb/.utdb, TPfun R in .xtdb, the title line of a .dat), so reading a
written file back reports "read from file" with that value.
"""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))
import roundtrip_util as U  # noqa: E402
import mqmqa  # noqa: E402
from mqmqa import Database, XTDB  # noqa: E402
from mqmqa import equilibrium as eq  # noqa: E402
from mqmqa._abi import _ffi, _lib  # noqa: E402
from test_gas_constant_detection import tdb, ideal_R  # noqa: E402

WEB = os.path.join(U.ROOT, "web")
FROM_FILE, INFERRED, CONVENTION, DECLARED, OVERRIDE = mqmqa.GAS_CONSTANT_SOURCES
VALUES = {"calphad": 8.3145, "sgte": 8.31451, "si": 8.314462618}
WRITERS = {"write_tdb": ".tdb", "write_utdb": ".utdb", "write_dat": ".dat", "write_xtdb": ".xtdb"}


@pytest.fixture(autouse=True)
def _restore_mode():
    yield
    mqmqa.set_gas_constant("as_assessed")


def reread(db, method, tmp_path):
    """Write with `method` and read the file back with the reader for its format."""
    path = tmp_path / ("out" + WRITERS[method])
    getattr(db, method)(str(path))
    return XTDB.read(str(path)) if method == "write_xtdb" else Database.read(str(path))


def writable(db):
    out = []
    for m in WRITERS:
        try:
            getattr(db, m)()
            out.append(m)
        except mqmqa.ConversionError:
            pass
    return out


def _mqmqa_ideal(db, T=1000.0):
    p = next(i for i in range(len(db.phase_names)) if db.phase_kind(i) == 0)
    inp = eq.build_inputs(db, p, T)
    X = list(np.full(len(inp["quads"]), 1.0 / len(inp["quads"])))
    return mqmqa.ideal_mixing_energy(inp["T"], inp["ncat"], inp["nan"], inp["qca"], inp["qcb"],
                                     inp["qax"], inp["qay"], X, inp["Za"], inp["Zb"], inp["Zx"],
                                     inp["Zy"], inp["zeta"], inp["soln_type"], inp["R_own"])


@pytest.mark.parametrize("choice", list(VALUES))
def test_declare_then_save_then_reload(choice, tmp_path):
    db = Database.read(os.path.join(WEB, "LiCl-KCl.dat"))
    base = _mqmqa_ideal(db)
    db.declare_gas_constant(choice)
    assert (db.own_gas_constant, db.gas_constant_source) == (VALUES[choice], DECLARED)
    assert db.gas_constant_note == f"R = {VALUES[choice]}, declared by you for this database"
    ours = _mqmqa_ideal(db)
    assert abs(ours * 8.3145 - base * VALUES[choice]) <= 1e-12 * abs(base)
    for method in writable(db):
        back = reread(db, method, tmp_path)
        assert (back.own_gas_constant, back.gas_constant_source) == (VALUES[choice], FROM_FILE), method
    db.declare_gas_constant("as_assessed")
    assert (db.own_gas_constant, db.gas_constant_source) == (8.3145, CONVENTION)
    assert _mqmqa_ideal(db) == base


def test_a_stated_value_cannot_be_declared():
    d = Database.read_string(tdb(" FUNCTION R  298.15  8.314;  6000 N !"))
    with pytest.raises(ValueError, match="states R = 8.314"):
        d.declare_gas_constant("si")
    x = XTDB.read(os.path.join(WEB, "AlC.xtdb"))
    with pytest.raises(ValueError, match="states R = 8.31451"):
        x.declare_gas_constant("calphad")
    with pytest.raises(ValueError):
        d.declare_gas_constant("codata")


def test_declared_R_reaches_R_references():
    d = Database.read_string(tdb(param="-1000", r_ref=True))
    p = d.phase_index("P")
    assert d.cef_gibbs(p, [1.0, 0.0], 1000.0, False) == -1000 + 8.31451 * 1000.0
    d.declare_gas_constant("si")
    assert d.cef_gibbs(p, [1.0, 0.0], 1000.0, False) == -1000 + 8.314462618 * 1000.0
    assert abs(ideal_R(d) - 8.314462618) < 1e-12


def test_declared_xtdb_uses_and_writes_it(tmp_path):
    x = XTDB.read(os.path.join(WEB, "PbSn.xtdb"))
    g0 = x.phase_gibbs(0, "SN", 0.4, 700.0)[0]
    x.declare_gas_constant("calphad")
    assert (x.own_gas_constant, x.gas_constant_source) == (8.3145, DECLARED)
    g1 = x.phase_gibbs(0, "SN", 0.4, 700.0)[0]
    ideal = 700.0 * (0.6 * math.log(0.6) + 0.4 * math.log(0.4))
    assert abs((g1 - g0) - (8.3145 - 8.31451) * ideal) < 1e-9
    back = reread(x, "write_xtdb", tmp_path)
    assert (back.own_gas_constant, back.gas_constant_source) == (8.3145, FROM_FILE)
    assert back.phase_gibbs(0, "SN", 0.4, 700.0)[0] == g1


def test_gas_declaration():
    g = _lib.mqmqa_gas_read_string(open(os.path.join(WEB, "nasa_gas.dat")).read().encode())
    try:
        assert _lib.mqmqa_gas_declare_R(g, 1) == 0
        assert _lib.mqmqa_gas_R_own(g) == 8.3145
        assert mqmqa.GAS_CONSTANT_SOURCES[_lib.mqmqa_gas_R_own_source(g)] == DECLARED
        assert _lib.mqmqa_gas_declare_R(g, 9) == -2
    finally:
        _lib.mqmqa_gas_free(g)


STATED = [
    ("stated .tdb", lambda: Database.read_string(tdb(" FUNCTION R  298.15  8.314;  6000 N !",
                                                     "-1000", r_ref=True)), 8.314),
    ("inferred .tdb", lambda: Database.read_string(tdb(param="-1000+8.31451*T")), 8.31451),
    ("convention .utdb", lambda: Database.read(os.path.join(WEB, "AlZn-NaClKClMgCl2.utdb")),
     8.3145),
    ("convention .dat", lambda: Database.read(os.path.join(WEB, "FeO-MgO-SiO2-combined.dat")),
     8.3145),
    ("convention .tdb", lambda: Database.read(os.path.join(WEB, "FeC.tdb")), 8.3145),
    ("stated .xtdb", lambda: XTDB.read(os.path.join(WEB, "AlC.xtdb")), 8.31451),
    ("convention .xtdb", lambda: XTDB.read(os.path.join(WEB, "PbSn.xtdb")), 8.31451),
]


@pytest.mark.parametrize("name,load,own", STATED, ids=[s[0] for s in STATED])
def test_every_format_records_the_own_value(name, load, own, tmp_path):
    db = load()
    assert db.own_gas_constant == own
    methods = writable(db)
    assert methods
    for method in methods:
        back = reread(db, method, tmp_path)
        assert (back.own_gas_constant, back.gas_constant_source) == (own, FROM_FILE), method


@pytest.mark.parametrize("mode", list(VALUES))
def test_the_global_override_never_leaks_into_files(mode, tmp_path):
    loads = [s[1]() for s in STATED]
    ref = [[getattr(db, m)() for m in writable(db)] for db in loads]
    mqmqa.set_gas_constant(mode)
    assert [[getattr(db, m)() for m in writable(db)] for db in loads] == ref
    for (_, _, own), db in zip(STATED, loads):
        for method in writable(db):
            back = reread(db, method, tmp_path)
            assert back.own_gas_constant == own
