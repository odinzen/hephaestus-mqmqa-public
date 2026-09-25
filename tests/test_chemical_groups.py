"""Chemical groups in the MQMQA excess: a term that needs the mixed-group interpolation
is refused loudly, never evaluated as if every species shared one group.

pycalphad's MQMQA-tern-tests.dat carries the same ternary G term under four group
assignments. TERN_XS_111 (one group) and TERN_XS_123 (three groups) leave the nu/gamma
sets empty, so the single-group expression is exact and must be evaluated;
TERN_XS_121 and TERN_XS_122 put the third cation on one side of the Cu-Mg term and need
the expansion the engine does not implement.
"""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))
import roundtrip_util as U  # noqa: E402
import mqmqa  # noqa: E402
from mqmqa import Database, UnsupportedModelError  # noqa: E402
from mqmqa import equilibrium as eq  # noqa: E402
from mqmqa._abi import _ffi, _lib, c_equilibrate  # noqa: E402

TERN = U.pycalphad_fixtures(["MQMQA-tern-tests.dat"])
pytestmark = pytest.mark.skipif(not TERN, reason="pycalphad test databases not installed")

REFUSED = ["TERN_XS_121", "TERN_XS_122"]
EVALUATED = ["TERN_XS_111", "TERN_XS_123", "XS_DIFF_CG", "XS_SAME_CG"]


@pytest.fixture(scope="module")
def db():
    return Database.read(TERN[0])


def _excess(db, p, grouped=True):
    cats, ans = db.cations(p), db.anions(p)
    nc, na = len(cats), len(ans)
    ca, cb, ax, ay = mqmqa.enumerate_quadruplets(nc, na)
    X = list(np.full(len(ca), 1.0 / len(ca)))
    one = [1.0] * len(ca)
    mx = db.mqmx(p, 1500.0)
    return mqmqa.excess_energy(nc, na, ca, cb, ax, ay, X, one, one, one, one,
                               mx["mix"], mx["code"], mx["A"], mx["B"], mx["X"], mx["Y"],
                               mx["p"], mx["q"], mx["L"], mx["r"], mx["addcat"],
                               [c["group"] for c in cats] if grouped else None,
                               [a["group"] for a in ans] if grouped else None)


@pytest.mark.parametrize("name", REFUSED)
def test_mixed_groups_refused(db, name):
    p = db.phase_index(name)
    why = db.excess_unsupported(p)
    assert why and name in why and "mixed chemical groups are not supported" in why
    assert math.isnan(_excess(db, p))
    with pytest.raises(UnsupportedModelError, match=name + r".*mixed chemical groups"):
        eq.build_inputs(db, p, 1500.0)


@pytest.mark.parametrize("name", REFUSED)
def test_mixed_groups_refused_by_the_c_solvers(db, name):
    p = db.phase_index(name)
    n_el = len(db.elements)
    target = _ffi.new("double[]", [1.0] * n_el)
    X = _ffi.new("double[]", 64)
    gm = _lib.mqmqa_equilibrate_db(db._db, p, 1500.0, target, X, _ffi.NULL)
    assert math.isnan(gm)
    err = _ffi.string(_lib.mqmqa_db_error()).decode()
    assert name in err and "mixed chemical groups are not supported" in err


def test_ungrouped_call_is_the_single_group_expression(db):
    """Omitting the groups is an explicit single-group request, the old contract."""
    p = db.phase_index("TERN_XS_121")
    assert math.isfinite(_excess(db, p, grouped=False))
    assert _excess(db, p, grouped=False) == _excess(db, db.phase_index("TERN_XS_111"))


@pytest.mark.parametrize("name", EVALUATED)
def test_empty_nu_sets_are_evaluated(db, name):
    """Groups that put no third species on either side leave the expression unchanged."""
    p = db.phase_index(name)
    assert db.excess_unsupported(p) is None
    assert math.isfinite(_excess(db, p))
    inp = eq.build_inputs(db, p, 1500.0)
    n = len(db.cations(p))
    res = c_equilibrate(inp, U._neutral_composition(db, p, np.full(n, 1.0 / n)))
    assert math.isfinite(res["GM"])


def test_group_override_strings_refused(db):
    """ChemSage chemical-group override strings (a negative mixing type) change the
    interpolation; the reader cannot model them, so the phase is refused."""
    text = open(TERN[0]).read()
    head, tail = text.split(" TERN_XS_111", 1)
    body, rest = tail.split(" TERN_XS_121", 1)
    marker = "     0.00000000     0.00000000\n   0\n"
    assert body.endswith(marker)
    override = "     0.00000000     0.00000000\n  -1\n 1 2 3 4 5 6 7 8 9 10\n"
    patched = head + " TERN_XS_111" + body[:-len(marker)] + override + " TERN_XS_121" + rest
    odb = Database.read_string(patched)
    p = odb.phase_index("TERN_XS_111")
    why = odb.excess_unsupported(p)
    assert why and "TERN_XS_111" in why and "override" in why
    with pytest.raises(UnsupportedModelError):
        eq.build_inputs(odb, p, 1500.0)
