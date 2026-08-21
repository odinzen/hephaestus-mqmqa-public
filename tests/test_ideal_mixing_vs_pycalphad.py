"""Validate the C ideal-mixing (configurational entropy) term against pycalphad.

Same Fe-O sub-slag oracle as the reference-energy test.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

pytest.importorskip("pycalphad")
from pycalphad import Database, variables as v
from pycalphad.models.model_mqmqa import ModelMQMQA

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

    Xval = {q: 0.05 + 0.01 * i for i, q in enumerate(quads)}
    Xarr = [Xval[q] for q in quads]

    Za = [float(mod.Z(dbf, q[0], *q)) for q in quads]
    Zb = [float(mod.Z(dbf, q[1], *q)) for q in quads]
    Zx = [float(mod.Z(dbf, q[2], *q)) for q in quads]
    Zy = [float(mod.Z(dbf, q[3], *q)) for q in quads]

    zeta = [float(mod._zeta_ik(cations[i], anions[k]))
            for i in range(len(cations)) for k in range(len(anions))]

    soln_type = 1 if dbf.phases["SLAG-LIQ"].model_hints["mqmqa"]["type"] == "SUBQ" else 0

    subs = {v.T: T}
    subs.update({mod._X_ijkl(*q): Xval[q] for q in quads})
    ideal_py = float(mod.ideal_mixing_energy(dbf).subs(subs))

    ideal_c = mqmqa.ideal_mixing_energy(
        T, len(cations), len(anions),
        quad_ca, quad_cb, quad_ax, quad_ay, Xarr,
        Za, Zb, Zx, Zy, zeta, soln_type,
    )
    return ideal_py, ideal_c


def test_ideal_mixing_matches_pycalphad():
    ideal_py, ideal_c = _build_case()
    assert abs(ideal_c - ideal_py) <= 1e-6 * max(1.0, abs(ideal_py)), (ideal_c, ideal_py)


if __name__ == "__main__":
    py, c = _build_case()
    print(f"pycalphad = {py:.6f}\nC         = {c:.6f}\ndiff      = {abs(c - py):.3e}")
