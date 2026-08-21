"""Validate the single-phase equilibrium solver against pycalphad.

The whole stack is ours: the ChemSage reader builds the phase, the C core supplies
the energy, and equilibrium.equilibrate minimizes it over the quadruplet fractions
at a fixed composition. pycalphad's own equilibrium is the oracle for the molar
Gibbs energy. The Fe-O sub-slag (2 cations with a redox degree of freedom, 1 anion)
is the test system.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

pytest.importorskip("pycalphad")
pytest.importorskip("scipy")
from pycalphad import Database, equilibrium, variables as v

import mqmqa
from mqmqa import equilibrium as eqm

DAT = Path("C:/Users/busta/Code/pycalphad/pycalphad/tests/databases/Shishin_Fe-Sb-O-S_slag.dat")
T = 1873.0


def _pycalphad_GM(xO):
    dbf = Database(str(DAT))
    eq = equilibrium(dbf, ["FE", "O", "VA"], "SLAG-LIQ",
                     {v.T: T, v.P: 1e5, v.N: 1, v.X("O"): xO})
    return float(eq.GM.values.squeeze())


@pytest.mark.parametrize("xO", [0.50, 0.55])
def test_equilibrium_GM_matches_pycalphad(xO):
    db = mqmqa.Database.read(DAT)
    p = db.phase_index("SLAG-LIQ")
    inp = eqm.build_inputs(db, p, T, components=["FE", "O"])
    res = eqm.equilibrate(inp, {"FE": 1 - xO, "O": xO})
    assert res["success"], res
    gm_py = _pycalphad_GM(xO)
    assert abs(res["GM"] - gm_py) <= 1e-4 * max(1.0, abs(gm_py)), (res["GM"], gm_py)


def test_equilibrium_composition_is_honored():
    db = mqmqa.Database.read(DAT)
    p = db.phase_index("SLAG-LIQ")
    inp = eqm.build_inputs(db, p, T, components=["FE", "O"])
    res = eqm.equilibrate(inp, {"FE": 0.45, "O": 0.55})
    els = res["elements"]
    xO = els["O"] / (els["FE"] + els["O"])
    assert abs(xO - 0.55) < 1e-6, xO
    assert abs(sum(res["X"]) - 1.0) < 1e-9


if __name__ == "__main__":
    db = mqmqa.Database.read(DAT)
    p = db.phase_index("SLAG-LIQ")
    inp = eqm.build_inputs(db, p, T, components=["FE", "O"])
    for xO in (0.50, 0.55, 0.60):
        res = eqm.equilibrate(inp, {"FE": 1 - xO, "O": xO})
        print(f"xO={xO}: GM={res['GM']:.3f}  X={res['X'].round(5)}  ok={res['success']}")
