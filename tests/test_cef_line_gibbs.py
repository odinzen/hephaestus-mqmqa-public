"""mqmqa_ph_cef_line_gibbs on a synthetic database: a two-site (M1/M2 ordering) phase is taken
at internal equilibrium, matching pycalphad's own minimization, and a one-site phase is
exactly the plain CEF value. The numbers are made up; only their structure matters."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

pycalphad = pytest.importorskip("pycalphad")
from pycalphad import Database, equilibrium, variables as v

import mqmqa


def _g(c0, c1):
    return f"   6000.0000   {c0:.10E}   {c1:.10E}   0   0   0   0"


def _text():
    ff, mm = (-2.50e6, 400.0), (-3.00e6, 380.0)
    avg = [(a + b) / 2 for a, b in zip(ff, mm)]
    ex_h, ex_s, rec = 12000.0, 3.0, -5000.0
    fm = (avg[0] + 0.5 * (rec + ex_h), avg[1] - 0.5 * ex_s)
    mf = (avg[0] + 0.5 * (rec - ex_h), avg[1] + 0.5 * ex_s)
    L = [" synthetic two-site and one-site CEF phases", "   4   2   4   2   0",
         "   FE   MG   SI   O", "   55.845000   24.305000   28.085000   15.999400",
         "   6   1   2   3   4   5   6", "   6   1   2   3   4   5   6",
         " TWOSITE", " SUBL"]
    for name, st, g in (("FEFE", "2.0   0.0", ff), ("FEMG", "1.0   1.0", fm),
                        ("MGFE", "1.0   1.0", mf), ("MGMG", "0.0   2.0", mm)):
        L += [f" {name}", f"   1   1   {st}   2.0   6.0", _g(*g)]
    L += ["   4", "   1.0   1.0   2.0   6.0", "   2   2   1   1", "   FE   MG", "   FE   MG",
          "   SI", "   O", "   1   1   2   2", "   1   2   1   2", "   1   1   1   1", "   1   1   1   1"]
    for idx, w in (([1, 2, 4, 5, 6], 6000.0), ([1, 2, 3, 5, 6], 6000.0),
                   ([2, 3, 4, 5, 6], 5000.0), ([1, 3, 4, 5, 6], 5000.0)):
        L += ["   " + "   ".join(str(i) for i in [len(idx)] + idx), "   1",
              f"   {w:.10E}   0   0   0   0   0"]
    L += ["   0", " ONESITE", " SUBL"]
    for name, st, g in (("FE2", "2.0   0.0", (-1.5e6, 300.0)), ("MG2", "0.0   2.0", (-2.2e6, 280.0))):
        L += [f" {name}", f"   1   1   {st}   1.0   4.0", _g(*g)]
    L += ["   3", "   2.0   1.0   4.0", "   2   1   1", "   FE   MG", "   SI", "   O",
          "   1   2", "   1   1", "   1   1", "   4   1   2   3   4", "   1",
          f"   {9000.0:.10E}   0   0   0   0   0", "   0"]
    return "\n".join(L) + "\n"


@pytest.fixture(scope="module")
def dbs(tmp_path_factory):
    path = tmp_path_factory.mktemp("cefline") / "twosite.dat"
    path.write_text(_text(), encoding="ascii")
    return mqmqa.Database.read(str(path)), Database(str(path))


def test_two_site_line_is_the_internal_equilibrium(dbs):
    db, pdb = dbs
    p = db.phase_index("TWOSITE")
    for T in (800.0, 1500.0):
        for x in (0.1, 0.5, 0.8):
            g, Y = db.cef_line_gibbs(p, 1 - x, T, per_mole_atoms=True)
            r = equilibrium(pdb, ["FE", "MG", "SI", "O"], ["TWOSITE"],
                            {v.T: T, v.P: 101325, v.N: 1, v.X("FE"): 0.2 * x,
                             v.X("MG"): 0.2 * (1 - x), v.X("SI"): 0.2})
            assert g == pytest.approx(float(r.GM.values.ravel()[0]), abs=1e-3), (T, x)
            assert Y[0] + Y[2] == pytest.approx(2 * x, abs=1e-12)     # Fe on M1 + M2
            assert Y[2] > Y[0]                                         # Fe prefers M2
            # the minimum: moving Fe between the sites raises G
            for d in (-1e-3, 1e-3):
                Yd = list(Y)
                Yd[0] += d; Yd[1] -= d; Yd[2] -= d; Yd[3] += d
                assert db.cef_gibbs(p, Yd, T, per_mole_atoms=True) > g


def test_one_site_line_is_the_plain_cef_value(dbs):
    db, _ = dbs
    p = db.phase_index("ONESITE")
    for y in (0.0, 0.2, 0.5, 0.9, 1.0):
        g, Y = db.cef_line_gibbs(p, y, 1200.0, per_mole_atoms=False)
        assert Y == [1 - y, y, 1.0, 1.0]
        assert g == db.cef_gibbs(p, Y, 1200.0, per_mole_atoms=False)


def test_a_missing_phase_raises_instead_of_reading_past_the_table(dbs):
    db, _ = dbs
    with pytest.raises(IndexError):
        db.cef_sublattices(db.phase_index("NOT-A-PHASE"))
    with pytest.raises(IndexError):
        db.pairs(99, 1000.0)
    with pytest.raises(ValueError):
        db.cef_gibbs(db.phase_index("ONESITE"), [0.5, 0.5], 1000.0)
