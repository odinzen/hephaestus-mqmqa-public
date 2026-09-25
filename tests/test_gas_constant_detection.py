"""Each loaded database's own gas constant and where it came from.

A file states R (a TDB FUNCTION R, an XTDB TPfun R, the gas-constant line of a
Hephaestus-written .dat); failing that its expressions may use one gas-constant literal
consistently, and R is inferred from it; failing both, the format's convention applies,
which is exactly the value the engine always used. Disagreeing literals are reported,
never guessed between. A forced mode overrides every database's own value, which is
kept and reported alongside.
"""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import roundtrip_util as U  # noqa: E402
import mqmqa  # noqa: E402
from mqmqa import Database, XTDB  # noqa: E402
from mqmqa._abi import _ffi, _lib  # noqa: E402

WEB = os.path.join(U.ROOT, "web")
FROM_FILE, INFERRED, CONVENTION, DECLARED, OVERRIDE = mqmqa.GAS_CONSTANT_SOURCES


@pytest.fixture(autouse=True)
def _restore_mode():
    yield
    mqmqa.set_gas_constant("as_assessed")


def tdb(header="", param="+0", r_ref=False):
    """A two-constituent TDB solution whose G is the ideal term plus `param` on A."""
    ref = "+R#*T" if r_ref else ""
    return f"""$ test file
{header}
 ELEMENT A   X  10  0  0 !
 ELEMENT B   X  20  0  0 !
 PHASE P %  1  1.0 !
 CONSTITUENT P : A,B : !
 PARAMETER G(P,A;0)  298.15  {param}{ref};  6000 N !
 PARAMETER G(P,B;0)  298.15  +0;  6000 N !
"""


def ideal_R(db, T=1000.0):
    """R recovered from the ideal term: G(0.5,0.5) - (G_A + G_B)/2 = R T ln(1/2)."""
    p = db.phase_index("P")

    def g(y):
        return db.cef_gibbs(p, [y, 1 - y], T, False)
    return (g(0.5) - 0.5 * (g(1.0) + g(0.0))) / (T * math.log(0.5))


def test_shipped_files():
    for name in ("AlC.xtdb",):
        x = XTDB.read(os.path.join(WEB, name))
        assert (x.own_gas_constant, x.gas_constant_source) == (8.31451, FROM_FILE)
        assert x.gas_constant_note == "R = 8.31451, read from this file"
    x = XTDB.read(os.path.join(WEB, "PbSn.xtdb"))
    assert (x.own_gas_constant, x.gas_constant_source) == (8.31451, CONVENTION)
    assert x.gas_constant_note == ("Not stated in the file; using 8.31451, the convention for "
                                   ".xtdb files")
    for name, fmt in (("AlZn.tdb", ".tdb"), ("FeC-FeOMgOSiO2.utdb", ".utdb"),
                      ("LiCl-KCl.dat", ".dat")):
        d = Database.read(os.path.join(WEB, name))
        assert (d.own_gas_constant, d.gas_constant_source) == (8.3145, CONVENTION)
        assert d.gas_constant_note == ("Not stated in the file; using 8.3145, the convention "
                                       f"for {fmt} files")


def test_tdb_function_R_is_read_and_used():
    """A file's own FUNCTION R wins over the built-in, in its expressions (R#) and in the
    model terms."""
    d = Database.read_string(tdb(" FUNCTION R  298.15  8.314;  6000 N !", "-1000", r_ref=True))
    assert (d.own_gas_constant, d.gas_constant_source) == (8.314, FROM_FILE)
    assert d.gas_constant_note == "R = 8.314, read from this file"
    assert abs(ideal_R(d) - 8.314) < 1e-12
    p = d.phase_index("P")
    assert d.cef_gibbs(p, [1.0, 0.0], 1000.0, False) == -1000 + 8.314 * 1000.0


def test_tdb_R_inferred_from_one_literal():
    """8.31451*T as a coefficient, no FUNCTION R: R is inferred, used by the model
    terms, and given to R# as well."""
    d = Database.read_string(tdb(param="-1000+8.31451*T", r_ref=True))
    assert (d.own_gas_constant, d.gas_constant_source) == (8.31451, INFERRED)
    assert d.gas_constant_note == "R = 8.31451, inferred from constants in this file"
    assert abs(ideal_R(d) - 8.31451) < 1e-12
    p = d.phase_index("P")
    want = -1000 + 8.31451 * 1000.0 + 8.31451 * 1000.0
    assert abs(d.cef_gibbs(p, [1.0, 0.0], 1000.0, False) - want) < 1e-9


def test_conflicting_literals_fall_back_to_the_convention():
    d = Database.read_string(tdb(param="-1000+8.3145*T-2*8.31451*T"))
    assert (d.own_gas_constant, d.gas_constant_source) == (8.3145, CONVENTION)
    assert d.gas_constant_note == ("Not stated in the file; using 8.3145, the convention for "
                                   ".tdb files; its constants disagree (8.3145, 8.31451)")
    assert ideal_R(d) == pytest.approx(8.3145, abs=1e-12)


def test_comments_never_change_the_value():
    d = Database.read_string(tdb("$ assessed with Thermo-Calc, R = 8.31451", "-1000+2*T"))
    assert (d.own_gas_constant, d.gas_constant_source) == (8.3145, CONVENTION)


def test_undefined_R_reference_is_the_builtin():
    """Today's behavior, kept: R# without a FUNCTION R is the built-in SGTE 8.31451 while
    the model terms keep the TDB convention; the note says both."""
    d = Database.read_string(tdb(param="-1000", r_ref=True))
    assert (d.own_gas_constant, d.gas_constant_source) == (8.3145, CONVENTION)
    assert d.gas_constant_note == ("Not stated in the file; using 8.3145, the convention for "
                                   ".tdb files; R# in its expressions is the built-in 8.31451")
    p = d.phase_index("P")
    assert d.cef_gibbs(p, [1.0, 0.0], 1000.0, False) == -1000 + 8.31451 * 1000.0
    assert abs(ideal_R(d) - 8.3145) < 1e-12


def test_dat_title_states_R():
    text = open(os.path.join(WEB, "LiCl-KCl.dat")).read()
    first, rest = text.split("\n", 1)
    d = Database.read_string(first + " Gas constant R = 8.31451 J/(mol K).\n" + rest)
    assert (d.own_gas_constant, d.gas_constant_source) == (8.31451, FROM_FILE)


XTDB_NO_R = """<XTDB version="0.1.5">
<Defaults LowT="298.15" HighT="6000" Elements="VA /-" />
<Element Id="A" Refstate="X" Mass="10" H298="0" S298="0" />
<Species Id="A" Stoichiometry="A" />
<!-- a comment quoting 8.314462618 does not count -->
<Phase Id="S" Configuration="CEF" State="S">
  <Sublattices NumberOf="1" Multiplicities="1">
    <Constituents Sublattice="1" List="A" />
  </Sublattices>
</Phase>
<Parameter Id="G(S,A;0)" Expr="-1000+{lit}*T*LN(2);" />
</XTDB>
"""


def test_xtdb_R_inferred_and_conflicting():
    x = XTDB.read_string(XTDB_NO_R.format(lit="8.3145"))
    assert (x.own_gas_constant, x.gas_constant_source) == (8.3145, INFERRED)
    x = XTDB.read_string(XTDB_NO_R.format(lit="8.3145*T+8.31451"))
    assert (x.own_gas_constant, x.gas_constant_source) == (8.31451, CONVENTION)
    assert "disagree (8.3145, 8.31451)" in x.gas_constant_note


def test_gas_data_convention():
    g = _lib.mqmqa_gas_read_string(open(os.path.join(WEB, "nasa_gas.dat")).read().encode())
    try:
        assert _lib.mqmqa_gas_R_own(g) == 8.314462618
        assert mqmqa.GAS_CONSTANT_SOURCES[_lib.mqmqa_gas_R_own_source(g)] == CONVENTION
        assert _ffi.string(_lib.mqmqa_gas_R_note(g)).decode() == (
            "Not stated in the file; using 8.314462618, the convention for NASA gas data")
        mqmqa.set_gas_constant("calphad")
        assert _lib.mqmqa_gas_R(g) == 8.3145
        assert mqmqa.GAS_CONSTANT_SOURCES[_lib.mqmqa_gas_R_source(g)] == OVERRIDE
    finally:
        _lib.mqmqa_gas_free(g)


def test_override_takes_precedence_and_keeps_the_own_value():
    d = Database.read_string(tdb(" FUNCTION R  298.15  8.314;  6000 N !", "-1000", r_ref=True))
    x = XTDB.read(os.path.join(WEB, "AlC.xtdb"))
    mqmqa.set_gas_constant("si")
    for db, own in ((d, 8.314), (x, 8.31451)):
        assert db.gas_constant == 8.314462618 and db.gas_constant_source == OVERRIDE
        assert db.own_gas_constant == own and db.own_gas_constant_source == FROM_FILE
        assert db.gas_constant_note == (f"R = 8.314462618, the gas-constant setting, "
                                        f"overriding this database's own {own} (read from "
                                        f"this file)")
    assert abs(ideal_R(d) - 8.314462618) < 1e-12
    p = d.phase_index("P")
    assert d.cef_gibbs(p, [1.0, 0.0], 1000.0, False) == -1000 + 8.314462618 * 1000.0
    mqmqa.set_gas_constant("as_assessed")
    assert d.gas_constant_source == FROM_FILE and abs(ideal_R(d) - 8.314) < 1e-12


def test_databases_loaded_together_keep_their_own_values():
    stated = Database.read_string(tdb(" FUNCTION R  298.15  8.314;  6000 N !"))
    inferred = Database.read_string(tdb(param="-1000+8.31451*T"))
    plain = Database.read_string(tdb())
    x = XTDB.read(os.path.join(WEB, "AlC.xtdb"))
    g = _lib.mqmqa_gas_read_string(open(os.path.join(WEB, "nasa_gas.dat")).read().encode())
    try:
        assert abs(ideal_R(stated) - 8.314) < 1e-12
        assert abs(ideal_R(inferred) - 8.31451) < 1e-12
        assert abs(ideal_R(plain) - 8.3145) < 1e-12
        assert x.gas_constant == 8.31451 and _lib.mqmqa_gas_R(g) == 8.314462618
    finally:
        _lib.mqmqa_gas_free(g)
