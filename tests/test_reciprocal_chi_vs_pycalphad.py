"""G-code (Chi) excess terms in reciprocal salts, where both sublattices mix.

With a nonzero exponent the Chi variables of a SUBQ phase take in the quadruplets that
pair the fixed ion with another ion of its sublattice. The engine does not evaluate
those yet, so such a term is refused (NaN, a message naming the phase) in SUBQ and
SUBG phases alike. With both exponents zero Chi drops out and the term is computed.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import test_chemical_groups as G  # noqa: E402
from mqmqa import Database  # noqa: E402

pytest.importorskip("pycalphad")

CATS, ANS = ["NA", "K"], ["CL", "F"]
CATION_TERM = ("G", "NA", "K", "CL", "CL", 1, 1, 0, None, -9000)
ANION_TERM = ("G", "NA", "NA", "CL", "F", 2, 1, 0, None, -7000)


def _subg(path):
    """The SUBQ salt as a SUBG phase: one zeta for the phase instead of one per pair."""
    text = path.read_text()
    text = text.replace("   1.3774438\n", "").replace(" SUBQ\n", " SUBG\n   1.3774438\n")
    out = path.with_name(path.stem + "_subg.dat")
    out.write_text(text)
    return out


def _salt(tmp_path, tag, terms, soln):
    path = G._as_dat(tmp_path, tag, CATS, ANS, [1, 1], [1, 1], terms)
    return path if soln == "SUBQ" else _subg(path)


@pytest.mark.parametrize("soln", ["SUBQ", "SUBG"])
@pytest.mark.parametrize("term", [CATION_TERM, ANION_TERM], ids=["cation", "anion"])
def test_nonzero_exponent_refused(tmp_path, term, soln):
    db = Database.read(str(_salt(tmp_path, "recip", [term], soln)))
    assert db.is_subq(db.phase_index("L")) == (soln == "SUBQ")
    G._refused(db, "L", r"G excess term .* nonzero exponent in a phase with more than one "
                        r"cation and more than one anion")


@pytest.mark.parametrize("soln", ["SUBQ", "SUBG"])
def test_zero_exponents_still_match_pycalphad(tmp_path, soln):
    terms = [CATION_TERM[:5] + (0, 0) + CATION_TERM[7:], ANION_TERM[:5] + (0, 0) + ANION_TERM[7:]]
    worst, _ = G._compare(_salt(tmp_path, "zero", terms, soln), "L")
    print(f"\n{soln} zero exponents: worst relative deviation {worst:.3g}")
