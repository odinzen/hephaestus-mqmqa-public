"""Validate the open FeO-MgO-SiO2 ternary liquid.

The 3-cation SUBQ liquid assembled from the two shipped binary liquids (FeO-SiO2 v0.3 +
MgO-SiO2 assessed) plus a near-ideal FeO-MgO edge. Two model-level checks, exact because
they fix the quadruplet distribution (no minimizer involved):
  - the engine's ternary Gibbs energy matches pycalphad's ModelMQMQA.GM to machine precision;
  - at a binary edge the ternary reduces to the shipped binary .dat (transcription guard).
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

DAT = ROOT / "data" / "feo-mgo-sio2" / "FeO-MgO-SiO2-liquid.dat"


def _val():
    spec = importlib.util.spec_from_file_location(
        "feo_mgo_sio2_validate", ROOT / "data" / "feo-mgo-sio2" / "validate.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.mark.skipif(not DAT.exists(), reason="ternary .dat not built")
def test_ternary_liquid_matches_pycalphad():
    pytest.importorskip("pycalphad")
    worst = _val().check_vs_pycalphad(n=5, tol=1e-6)
    assert worst < 1e-6, f"engine vs pycalphad worst |diff| = {worst:.2e} J/mol-atom"


@pytest.mark.skipif(not DAT.exists(), reason="ternary .dat not built")
def test_ternary_reduces_to_shipped_binaries():
    worst = _val().check_binary_reduction(tol=1e-2)
    assert worst < 1e-2, f"binary reduction worst |diff| = {worst:.2e} J/mol-atom"
