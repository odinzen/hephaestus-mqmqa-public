"""The CaO-Al2O3 compounds reproduce their measured enthalpies of formation from the oxides at the
temperature each was measured: Coughlin 1956 at 298 K, Geiger 1988 (CaAl4O7) at 1063 K. Until
2026-10-02 Geiger's 1063 K value was entered as a 298 K one, leaving CaAl4O7 3.7 kJ too stable."""
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


def test_ca2_reproduces_geiger_at_1063_k(bd):
    cf = dict(bd.SOLIDS["CaAl4O7"][2], dHf=bd.SOLIDS["CaAl4O7"][2]["dHf"] - bd.CA2_DHF_SHIFT)
    assert bd.dh_ox("CaAl4O7", cf, 1063.0) == pytest.approx(-25600.0, abs=100.0)


@pytest.mark.parametrize("formula,dhf_ox", [("CaAl2O4", -15440.0), ("Ca3Al2O6", -6650.0)])
def test_coughlin_compounds_at_298_k(bd, formula, dhf_ox):
    # within the 3-term heat-content fit's residual at the bottom of the table
    assert bd.dh_ox(formula, bd.SOLIDS[formula][2], 298.15) == pytest.approx(dhf_ox, abs=600.0)
