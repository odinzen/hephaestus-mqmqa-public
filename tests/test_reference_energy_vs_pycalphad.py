"""Validate the C reference-energy term against pycalphad's model_mqmqa.

Oracle: pycalphad's own ModelMQMQA.reference_energy on the Fe-O sub-slag of the
Shishin Fe-Sb-S-O database (2 cations, 1 anion, 3 quadruplets). Identical numeric
inputs are handed to the C routine; the two must agree to roundoff.

Requires the calphad conda env (pycalphad) and a built mqmqa DLL.
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

    Xval = {q: 0.05 + 0.01 * i for i, q in enumerate(quads)}
    Xarr = [Xval[q] for q in quads]

    def evalG(expr):
        return float(mod.symbol_replace(expr, dict(dbf.symbols)).subs({v.T: T}))

    params = dbf._parameters.search(
        (where("phase_name") == "SLAG-LIQ")
        & (where("parameter_type") == "MQMG")
        & (where("constituent_array").test(mod._pair_test))
    )
    pair_c, pair_a, Gax, stoich = [], [], [], []
    for prm in params:
        a = prm["constituent_array"][0][0]
        x = prm["constituent_array"][1][0]
        pair_c.append(ci[a])
        pair_a.append(ai[x])
        Gax.append(evalG(prm["parameter"]))
        stoich.append(prm["stoichiometry"][0])

    # Z(a, q) is only defined (and only used) when quadruplet q contains cation a.
    # For quads without a the C sum multiplies by count(a)=0, so any value is fine.
    Z = []
    for p in range(len(pair_c)):
        a_species = cations[pair_c[p]]
        for (A, B, X, Y) in quads:
            if a_species in (A, B):
                Z.append(float(mod.Z(dbf, a_species, A, B, X, Y)))
            else:
                Z.append(1.0)

    subs = {v.T: T}
    subs.update({mod._X_ijkl(*q): Xval[q] for q in quads})
    ref_py = float(mod.reference_energy(dbf).subs(subs))

    ref_c = mqmqa.reference_energy(
        quad_ca, quad_cb, quad_ax, quad_ay, Xarr,
        pair_c, pair_a, Gax, stoich, Z,
    )
    return ref_py, ref_c


def test_reference_energy_matches_pycalphad():
    ref_py, ref_c = _build_case()
    assert abs(ref_c - ref_py) <= 1e-6 * max(1.0, abs(ref_py)), (ref_c, ref_py)


if __name__ == "__main__":
    py, c = _build_case()
    print(f"pycalphad = {py:.6f}\nC         = {c:.6f}\ndiff      = {abs(c - py):.3e}")
