"""TDB expressions read as written, against pycalphad and the exact value.

The TDB reader once dropped everything after a '/', so 1000/T read as 1000; a workspace
TDB written by sympy (`+ 113.985/T`) came back up to 1.9e5 J/mol-atom off. Each case here
is one FUNCTION evaluated through a one-endmember phase at 400 K. Syntax the reader does
not evaluate must fail the read, never be skipped.
"""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from mqmqa import Database

T = 400.0

TDB = """ELEMENT X BLANK 1 0 0 !
FUNCTION GC 298.15 4; 3000 N !
FUNCTION GX 298.15 {expr}; 3000 N !
PHASE A % 1 1 !
CONSTITUENT A :X: !
PARAMETER G(A,X;0) 298.15 GX#; 3000 N !
"""

CASES = [
    ("1000*T**(-1)", 1000 / T),
    ("1000/T", 1000 / T),
    ("1000/T**2", 1000 / T**2),
    ("1000/T**0.5", 1000 / T**0.5),
    ("5+1000/T", 5 + 1000 / T),
    ("1000/(T)", 1000 / T),
    ("1000/T/2", 1000 / T / 2),
    ("1000/(2*T)", 1000 / (2 * T)),
    ("1000/T**2/5", 1000 / T**2 / 5),
    ("-T**2", -T**2),
    ("2**3**2", 512.0),
    ("T**-1*1000", 1000 / T),
    ("(T+1)*2/T", (T + 1) * 2 / T),
    ("GC#/8", 0.5),
    ("1000/GC#", 250.0),
    ("GC#**(-1)*T", T / 4),
    ("-24.3671976*T*LN(T)+74092/T-1.884662E-3*T**2", -24.3671976 * T * math.log(T) + 74092 / T - 1.884662e-3 * T**2),
]


def _ours(expr):
    db = Database.read_string(TDB.format(expr=expr))
    return db.stoich_gibbs(list(db.stoich).index("A"), T)


@pytest.mark.parametrize("expr,exact", CASES)
def test_expression_value(expr, exact):
    assert _ours(expr) == pytest.approx(exact, rel=1e-12, abs=0)


@pytest.mark.parametrize("expr,exact", CASES)
def test_expression_matches_pycalphad(expr, exact):
    pycalphad = pytest.importorskip("pycalphad")
    from pycalphad import calculate
    res = calculate(pycalphad.Database(TDB.format(expr=expr)), ["X"], "A", T=T, P=101325, N=1)
    assert _ours(expr) == pytest.approx(float(res.GM.values.squeeze()), rel=1e-12, abs=0)


@pytest.mark.parametrize("expr,needle", [
    ("1000 @ 5", "unexpected text"),
    ("2T", "unexpected text"),
    ("1000/", "expected a number"),
    ("(1000/T", "missing ')'"),
    ("1000/0", "division by zero"),
    ("1000/(T+1)", "division by a sum"),
    ("(T+1)**2", "power of a sum"),
    ("LOG(T)", "LOG(...)"),
    ("SQRT(T)", "SQRT(...)"),
    ("T*LN(T)*T", "LN(T) other than"),
    ("T**T", "exponent that is not a number"),
])
def test_unread_syntax_fails_loudly(expr, needle):
    with pytest.raises(Exception, match=r"(?s)" + needle.replace("(", r"\(").replace(")", r"\)")
                       .replace(".", r"\.").replace("*", r"\*")):
        Database.read_string(TDB.format(expr=expr))


def test_unused_function_outside_the_subset_does_not_block_the_file():
    # the SGTE pressure helper is defined in many files and used by none of their phases
    text = TDB.format(expr="1000/T") + "FUNCTION RTLNP 298.15 +8.31451*T*LN(1E-05*P); 6000 N !\n"
    db = Database.read_string(text)
    assert db.stoich_gibbs(0, T) == pytest.approx(2.5, rel=1e-12)
    used = text.replace("PARAMETER G(A,X;0) 298.15 GX#;", "PARAMETER G(A,X;0) 298.15 GX#+RTLNP#;")
    with pytest.raises(Exception, match="function RTLNP is used"):
        Database.read_string(used)


def test_constant_power_times_function_keeps_both_factors():
    # R**(-1)*TINV once read as 1/R, dropping TINV
    text = TDB.format(expr="RR#**(-1)*TINV#") + (
        "FUNCTION RR 298.15 8.31451; 6000 N !\nFUNCTION TINV 298.15 T**(-1); 6000 N !\n")
    assert Database.read_string(text).stoich_gibbs(0, T) == pytest.approx(1 / (8.31451 * T), rel=1e-12)


def test_upper_limit_may_be_left_out_after_commas():
    text = TDB.format(expr="1000/T").replace("GX#; 3000 N !", "GX#;,,N REF !")
    assert Database.read_string(text).stoich_gibbs(0, T) == pytest.approx(2.5, rel=1e-12)


def test_every_shipped_tdb_reads_under_the_strict_parser():
    root = Path(__file__).resolve().parents[1] / "data"
    for path in list(root.rglob("*.tdb")) + list(root.rglob("*.utdb")):
        Database.read(str(path))
