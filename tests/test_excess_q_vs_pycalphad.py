"""Validate the C cation-mixing Q-code excess term against pycalphad.

The Fe-O sub-slag's excess parameters are exactly two cation-mixing Q-code MQMX
terms (FE2/FE3 on O), so pycalphad's full excess_mixing_energy here equals the
sum this C routine computes.
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


def _build_case():
    dbf = Database(str(DAT))
    mod = ModelMQMQA(dbf, ["FE", "O", "VA"], "SLAG-LIQ")
    cations = list(mod.cations)
    anions = list(mod.anions)
    ci = {c: i for i, c in enumerate(cations)}
    ai = {a: i for i, a in enumerate(anions)}
    quads = list(mod._quadruplets)

    quad_ca = [ci[A] for (A, B, X, Y) in quads]
    quad_cb = [ci[B] for (A, B, X, Y) in quads]
    quad_ax = [ai[X] for (A, B, X, Y) in quads]
    quad_ay = [ai[Y] for (A, B, X, Y) in quads]
    Zx = [float(mod.Z(dbf, q[2], *q)) for q in quads]
    Zy = [float(mod.Z(dbf, q[3], *q)) for q in quads]

    Xval = {q: 0.05 + 0.01 * i for i, q in enumerate(quads)}
    Xarr = [Xval[q] for q in quads]

    def evalG(expr):
        return float(mod.symbol_replace(expr, dict(dbf.symbols)).subs({v.T: T}))

    params = dbf._parameters.search(
        (where("phase_name") == "SLAG-LIQ")
        & (where("parameter_type") == "MQMX")
        & (where("constituent_array").test(mod._array_validity))
    )
    par_A, par_B, par_X, par_p, par_q, par_L = [], [], [], [], [], []
    for prm in params:
        (A, B), (X, Y) = prm["constituent_array"]
        assert prm["mixing_code"] == "Q" and A != B and X == Y, "first cut: cation Q only"
        par_A.append(ci[A])
        par_B.append(ci[B])
        par_X.append(ai[X])
        par_p.append(prm["exponents"][0])
        par_q.append(prm["exponents"][1])
        par_L.append(evalG(prm["parameter"]))

    subs = {v.T: T}
    subs.update({mod._X_ijkl(*q): Xval[q] for q in quads})
    exc_py = float(mod.excess_mixing_energy(dbf).subs(subs))

    exc_c = mqmqa.excess_energy_q_cation(
        len(cations), len(anions),
        quad_ca, quad_cb, quad_ax, quad_ay, Xarr,
        Zx, Zy,
        par_A, par_B, par_X, par_p, par_q, par_L,
    )
    return exc_py, exc_c


def test_excess_q_cation_matches_pycalphad():
    exc_py, exc_c = _build_case()
    assert abs(exc_c - exc_py) <= 1e-6 * max(1.0, abs(exc_py)), (exc_c, exc_py)


if __name__ == "__main__":
    py, c = _build_case()
    print(f"pycalphad = {py:.6f}\nC         = {c:.6f}\ndiff      = {abs(c - py):.3e}")
