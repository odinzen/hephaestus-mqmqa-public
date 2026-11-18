"""Excess coefficients exposed as fit parameters: listing, in-memory set, and writers."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

import mqmqa
from mqmqa import equilibrium as eqm

FMS = ROOT / "data" / "feo-mgo-sio2" / "FeO-MgO-SiO2-liquid.dat"
ALZN = ROOT / "data" / "al-zn" / "AlZn.tdb"
T = 1873.0


def _gm(db):
    p = db.phase_index(db.phase_names[0])
    inp = eqm.build_inputs(db, p, T, components=["FE", "MG", "SI", "O"])
    fe, mg, si = 0.3, 0.2, 0.5
    o = fe + mg + 2 * si
    s = fe + mg + si + o
    return mqmqa.c_equilibrate(inp, {"FE": fe / s, "MG": mg / s, "SI": si / s, "O": o / s})["GM"]


def test_params_cover_every_mqmx_coefficient():
    db = mqmqa.Database.read(FMS)
    p = db.phase_index(db.phase_names[0])
    n_terms = len(db.mqmx(p, T)["L"])
    params = db.params()
    assert n_terms > 0
    assert len(params) % n_terms == 0 and len(params) >= n_terms
    assert {q["kind"] for q in params} == {"mqmx"}
    assert [q["index"] for q in params] == list(range(len(params)))


def test_set_param_moves_the_energy_and_the_written_file_keeps_it(tmp_path):
    db = mqmqa.Database.read(FMS)
    g0 = _gm(db)
    # the constant slot of the first term
    q = next(q for q in db.params() if q["tfun"] == 1)
    db.set_param(q["index"], q["value"] + 5000.0)
    assert db.params()[q["index"]]["value"] == pytest.approx(q["value"] + 5000.0, abs=0, rel=1e-15)
    g1 = _gm(db)
    assert abs(g1 - g0) > 1.0

    out = tmp_path / "moved.dat"
    db.write_dat(out)
    assert _gm(mqmqa.Database.read(out)) == pytest.approx(g1, rel=1e-9, abs=0)

    db.set_param(q["index"], q["value"])
    assert _gm(db) == pytest.approx(g0, rel=1e-12, abs=0)


def test_bad_index_and_non_finite_value_are_refused():
    db = mqmqa.Database.read(FMS)
    n = len(db.params())
    with pytest.raises(IndexError):
        db.set_param(n, 1.0)
    with pytest.raises(IndexError):
        db.set_param(-1, 1.0)
    with pytest.raises(IndexError):
        db.set_param(0, float("nan"))


def test_cef_parameters_are_listed_and_move_the_energy():
    db = mqmqa.Database.read(ALZN)
    cef = [q for q in db.params() if q["kind"] == "cef"]
    assert cef
    q = next(q for q in cef if q["tfun"] == 1)
    p = db.phase_index(q["phase"])
    line = lambda: db.cef_line_gibbs(p, 0.5, 700.0)[0]
    g0 = line()
    db.set_param(q["index"], q["value"] + 4000.0)
    assert abs(line() - g0) > 1.0
