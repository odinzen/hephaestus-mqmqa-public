"""Validate the C excess term against pycalphad's excess_mixing_energy.

Two oracles from the Shishin Fe-Sb-S-O slag:
  - Fe-O sub-slag: two cation-mixing Q params (single anion, factors vanish).
  - Full Fe-Sb-S-O: the same Q params (now with a non-zero anion factor from the
    second anion) plus one anion-mixing G param (non-zero cation factor). This
    exercises the eq-17 factor assembly and the G code.

Chemical groups are single-per-sublattice in this database, so the nu/gamma
expansion is empty and this covers the excess exactly.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

pytest.importorskip("pycalphad")
from pycalphad import Database, variables as v
from pycalphad.models.model_mqmqa import ModelMQMQA
from tinydb import where

import mqmqa

DAT = Path("C:/Users/busta/Code/pycalphad/pycalphad/tests/databases/Shishin_Fe-Sb-O-S_slag.dat")
T = 1873.0


def _build_case(comps):
    dbf = Database(str(DAT))
    mod = ModelMQMQA(dbf, comps, "SLAG-LIQ")
    cations = list(mod.cations)
    anions = list(mod.anions)
    ci = {c: i for i, c in enumerate(cations)}
    ai = {a: i for i, a in enumerate(anions)}
    quads = list(mod._quadruplets)

    quad_ca = [ci[A] for (A, B, X, Y) in quads]
    quad_cb = [ci[B] for (A, B, X, Y) in quads]
    quad_ax = [ai[X] for (A, B, X, Y) in quads]
    quad_ay = [ai[Y] for (A, B, X, Y) in quads]
    Za = [float(mod.Z(dbf, q[0], *q)) for q in quads]
    Zb = [float(mod.Z(dbf, q[1], *q)) for q in quads]
    Zx = [float(mod.Z(dbf, q[2], *q)) for q in quads]
    Zy = [float(mod.Z(dbf, q[3], *q)) for q in quads]

    Xval = {q: 0.03 + 0.005 * i for i, q in enumerate(quads)}
    Xarr = [Xval[q] for q in quads]

    def evalG(expr):
        return float(mod.symbol_replace(expr, dict(dbf.symbols)).subs({v.T: T}))

    params = dbf._parameters.search(
        (where("phase_name") == "SLAG-LIQ")
        & (where("parameter_type") == "MQMX")
        & (where("constituent_array").test(mod._array_validity))
    )
    pm = dict(mix=[], code=[], A=[], B=[], X=[], Y=[], p=[], q=[], L=[])
    for prm in params:
        (A, B), (X, Y) = prm["constituent_array"]
        code = prm["mixing_code"]
        assert code in ("Q", "G"), f"code {code} not yet handled"
        if A != B and X == Y:
            pm["mix"].append(0)
        elif A == B and X != Y:
            pm["mix"].append(1)
        else:
            raise AssertionError("reciprocal excess not yet handled")
        pm["code"].append(0 if code == "Q" else 1)
        pm["A"].append(ci[A]); pm["B"].append(ci[B])
        pm["X"].append(ai[X]); pm["Y"].append(ai[Y])
        pm["p"].append(prm["exponents"][0]); pm["q"].append(prm["exponents"][1])
        pm["L"].append(evalG(prm["parameter"]))

    subs = {v.T: T}
    subs.update({mod._X_ijkl(*q): Xval[q] for q in quads})
    exc_py = float(mod.excess_mixing_energy(dbf).subs(subs))

    exc_c = mqmqa.excess_energy(
        len(cations), len(anions),
        quad_ca, quad_cb, quad_ax, quad_ay, Xarr,
        Za, Zb, Zx, Zy,
        pm["mix"], pm["code"], pm["A"], pm["B"], pm["X"], pm["Y"],
        pm["p"], pm["q"], pm["L"],
    )
    return exc_py, exc_c


def test_excess_feo():
    py, c = _build_case(["FE", "O", "VA"])
    assert abs(c - py) <= 1e-6 * max(1.0, abs(py)), (c, py)


def test_excess_full_shishin():
    py, c = _build_case(["FE", "SB", "S", "O", "VA"])
    assert abs(c - py) <= 1e-6 * max(1.0, abs(py)), (c, py)


if __name__ == "__main__":
    for comps in (["FE", "O", "VA"], ["FE", "SB", "S", "O", "VA"]):
        py, c = _build_case(comps)
        print(f"{'+'.join(comps):20s} py={py:.6f}  C={c:.6f}  diff={abs(c-py):.3e}")
