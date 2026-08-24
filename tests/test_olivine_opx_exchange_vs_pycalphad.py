"""Validate the olivine <-> orthopyroxene Fe-Mg exchange equilibrium.

Two CEF solid solutions (olivine, orthopyroxene) in one ChemSage SUBL .dat, read by the
C engine. The engine computes the exchange isotherm from the CEF kernel via the equal-
Gibbs-slope (equal exchange-potential) condition; the coexisting compositions must match
pycalphad's own two-phase equilibrium() on the same file. Also checks the reader handles
two SUBL phases at once, and that K_D is near 1 (near-ideal, per the measured system).
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
sys.path.insert(0, str(ROOT / "data" / "olivine-opx"))

pytest.importorskip("pycalphad")
from pycalphad import Database as PycDatabase

import mqmqa
import exchange as ex


def test_exchange_isotherm_matches_pycalphad():
    cdb, p_ol, p_opx = ex._load()
    assert cdb.phase_names == ["OLIVINE", "ORTHOPYROXENE"]
    assert cdb.phase_kind(p_ol) == 1 and cdb.phase_kind(p_opx) == 1
    pdb = PycDatabase(str(ex.DAT))

    T = 1000.0
    worst = 0.0
    n_checked = 0
    for fe_bulk in (0.2, 0.5, 0.7):
        tie = ex.pyc_tieline(pdb, T, x_sio2_bulk=0.42, fe_frac_bulk=fe_bulk)
        assert tie is not None, f"pycalphad not two-phase at bulk Fe={fe_bulk}"
        x_ol_p, x_opx_p = tie
        x_ol_e = ex.exchange_x_ol(cdb, p_ol, p_opx, x_opx_p, T)
        worst = max(worst, abs(x_ol_e - x_ol_p))
        n_checked += 1
    assert n_checked == 3
    assert worst < 1e-6, f"exchange isotherm vs pycalphad worst |d| = {worst}"


def test_KD_near_ideal():
    """K_D should sit near 1 across composition (the measured system is near-ideal)."""
    cdb, p_ol, p_opx = ex._load()
    for x_opx in (0.1, 0.3, 0.5):
        x_ol = ex.exchange_x_ol(cdb, p_ol, p_opx, x_opx, 1273.0)
        kd = ex.K_D(x_ol, x_opx)
        assert 0.7 < kd < 1.4, f"K_D={kd} at X_Fe,opx={x_opx} is not near-ideal"
