"""The CaO-Al2O3 compounds reproduce their measured enthalpies of formation from the oxides at the
temperature each was measured: Coughlin 1956 at 298 K, Geiger 1988 (CaAl4O7) at 1063 K. Until
2026-10-02 Geiger's 1063 K value was entered as a 298 K one, leaving CaAl4O7 3.7 kJ too stable.
The shipped solids carry the dry assessment's shifts (build_dat.DHF_SHIFT); the anchoring is
checked on the measured values underneath them (build_dat.MEASURED, also what data/wet-slag reads)."""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))


@pytest.fixture(scope="module")
def bd():
    s = importlib.util.spec_from_file_location("caal_bd_test", ROOT / "data" / "cao-al2o3" / "build_dat.py")
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def _measured(bd, formula):
    return bd.MEASURED[formula]


def test_shipped_solids_are_measured_plus_stored_shift(bd):
    for f, cf in bd.MEASURED.items():
        assert bd.SOLIDS[f][2]["dHf"] - cf["dHf"] == pytest.approx(bd.DHF_SHIFT.get(f, 0.0), abs=1e-9)


def test_ca2_reproduces_geiger_at_1063_k(bd):
    assert bd.dh_ox("CaAl4O7", _measured(bd, "CaAl4O7"), 1063.0) == pytest.approx(-25600.0, abs=100.0)


@pytest.mark.parametrize("formula,dhf_ox", [("CaAl2O4", -15440.0), ("Ca3Al2O6", -6650.0)])
def test_coughlin_compounds_at_298_k(bd, formula, dhf_ox):
    # within the 3-term heat-content fit's residual at the bottom of the table
    assert bd.dh_ox(formula, _measured(bd, formula), 298.15) == pytest.approx(dhf_ox, abs=600.0)
