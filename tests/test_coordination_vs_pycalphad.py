"""Validate the C coordination-number recursion against pycalphad's Z.

Every quadruplet slot in the full Fe-Sb-S-O slag is checked, which covers pure
pairs (MQMZ lookup), mixed quadruplets, and reciprocal quadruplets (the eq-23/24
recursion).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

pytest.importorskip("pycalphad")
from pycalphad import Database
from pycalphad.models.model_mqmqa import ModelMQMQA
from tinydb import where

import mqmqa

DAT = Path("C:/Users/busta/Code/pycalphad/pycalphad/tests/databases/Shishin_Fe-Sb-O-S_slag.dat")


def _ctx():
    dbf = Database(str(DAT))
    mod = ModelMQMQA(dbf, ["FE", "SB", "S", "O", "VA"], "SLAG-LIQ")
    cations = list(mod.cations)
    anions = list(mod.anions)
    ci = {c: i for i, c in enumerate(cations)}
    ai = {a: i for i, a in enumerate(anions)}
    q_cat = [abs(c.charge) for c in cations]
    q_an = [abs(a.charge) for a in anions]

    mz_A, mz_B, mz_X, mz_Y, mz_Z = [], [], [], [], []
    for prm in dbf._parameters.search(
        (where("phase_name") == "SLAG-LIQ") & (where("parameter_type") == "MQMZ")
    ):
        (A, B), (X, Y) = prm["constituent_array"]
        a, b = ci[A], ci[B]
        x, y = ai[X], ai[Y]
        z = list(prm["coordinations"])  # [Z_A, Z_B, Z_X, Z_Y]
        if a > b:
            a, b = b, a
            z[0], z[1] = z[1], z[0]
        if x > y:
            x, y = y, x
            z[2], z[3] = z[3], z[2]
        mz_A.append(a); mz_B.append(b); mz_X.append(x); mz_Y.append(y)
        mz_Z.extend(z)
    return dbf, mod, cations, anions, ci, ai, q_cat, q_an, (mz_A, mz_B, mz_X, mz_Y, mz_Z)


def _max_diff():
    dbf, mod, cations, anions, ci, ai, q_cat, q_an, mz = _ctx()
    mz_A, mz_B, mz_X, mz_Y, mz_Z = mz
    worst = 0.0
    n = 0
    for A, B, X, Y in mod._quadruplets:
        for sp, is_cat, idx in ((A, 1, ci[A]), (B, 1, ci[B]),
                                (X, 0, ai[X]), (Y, 0, ai[Y])):
            py = float(mod.Z(dbf, sp, A, B, X, Y))
            c = mqmqa.coordination(is_cat, idx, ci[A], ci[B], ai[X], ai[Y],
                                   len(cations), len(anions), q_cat, q_an,
                                   mz_A, mz_B, mz_X, mz_Y, mz_Z)
            worst = max(worst, abs(c - py) / max(1.0, abs(py)))
            n += 1
    return worst, n


def test_coordination_matches_pycalphad():
    worst, n = _max_diff()
    assert worst <= 1e-9, worst


if __name__ == "__main__":
    worst, n = _max_diff()
    print(f"checked {n} (species, quadruplet) coordinations; max rel diff = {worst:.3e}")
