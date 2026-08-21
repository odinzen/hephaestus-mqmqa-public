"""Validate the C single-phase equilibrium solver against pycalphad.

Same stack and oracle as test_equilibrium_vs_pycalphad, but the minimization runs
in the C core (mqmqa.c_equilibrate) rather than the Python/scipy reference. This is
the solver the browser build ships, so pycalphad's equilibrium() is the oracle for
the molar Gibbs energy on the Fe-O sub-slag (2 cations with a redox degree of
freedom, 1 anion).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

pytest.importorskip("pycalphad")
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
def test_c_equilibrium_GM_matches_pycalphad(xO):
    db = mqmqa.Database.read(DAT)
    p = db.phase_index("SLAG-LIQ")
    inp = eqm.build_inputs(db, p, T, components=["FE", "O"])
    res = mqmqa.c_equilibrate(inp, {"FE": 1 - xO, "O": xO})
    assert res["comp_error"] < 1e-6, res
    gm_py = _pycalphad_GM(xO)
    assert abs(res["GM"] - gm_py) <= 1e-4 * max(1.0, abs(gm_py)), (res["GM"], gm_py)


def test_c_equilibrium_matches_python_reference():
    db = mqmqa.Database.read(DAT)
    p = db.phase_index("SLAG-LIQ")
    inp = eqm.build_inputs(db, p, T, components=["FE", "O"])
    for xO in (0.50, 0.55):
        c = mqmqa.c_equilibrate(inp, {"FE": 1 - xO, "O": xO})
        r = eqm.equilibrate(inp, {"FE": 1 - xO, "O": xO})
        assert abs(c["GM"] - r["GM"]) <= 1e-4 * max(1.0, abs(r["GM"])), (xO, c["GM"], r["GM"])


if __name__ == "__main__":
    db = mqmqa.Database.read(DAT)
    p = db.phase_index("SLAG-LIQ")
    inp = eqm.build_inputs(db, p, T, components=["FE", "O"])
    for xO in (0.50, 0.55):
        res = mqmqa.c_equilibrate(inp, {"FE": 1 - xO, "O": xO})
        gm_py = _pycalphad_GM(xO)
        print(f"xO={xO}: C GM={res['GM']:.3f}  pycalphad GM={gm_py:.3f}  "
              f"|d|={abs(res['GM'] - gm_py):.3e}  comp_err={res['comp_error']:.1e}")
