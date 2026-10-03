"""Validate the olivine <-> orthopyroxene Fe-Mg exchange equilibrium.

Two CEF solid solutions (olivine, orthopyroxene) in one ChemSage SUBL .dat, read by the
C engine. The engine computes the exchange isotherm from the CEF kernel via the equal-
Gibbs-slope (equal exchange-potential) condition; the coexisting compositions must match
pycalphad's own two-phase equilibrium() on the same file. Also checks the reader handles
two SUBL phases at once, and that the tie-lines match the measured ones at 1473 K.
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


def test_tielines_match_nafziger_muan_1967():
    """Olivine coexisting with orthopyroxene at 1473 K, 1 atm (Nafziger & Muan 1967,
    Table 5) up to Fs 0.3, within 0.03. Above that the model's olivine runs 0.05-0.08 too
    iron-rich (the iron-rich 1 atm pyroxene is not orthopyroxene; PROVENANCE.md)."""
    cdb, p_ol, p_opx = ex._load()
    for x_ol_meas, x_opx in ((0.05, 0.05), (0.11, 0.11), (0.15, 0.14), (0.26, 0.22),
                             (0.30, 0.24), (0.36, 0.29)):
        x_ol = ex.exchange_x_ol(cdb, p_ol, p_opx, x_opx, 1473.15)
        assert abs(x_ol - x_ol_meas) < 0.03, (x_opx, x_ol, x_ol_meas)
