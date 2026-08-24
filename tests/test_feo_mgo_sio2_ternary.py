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


@pytest.mark.skipif(not DAT.exists(), reason="ternary .dat not built")
def test_olivine_join_endpoints_reproduce_congruent_melting():
    """Both ends of the Mg2SiO4-Fe2SiO4 olivine join melt congruently at their measured
    temperatures against the olivine CEF endmembers: forsterite 2163 K (after the MgO(l)
    reconciliation), fayalite 1478 K. Uses the exact binary-subsystem solve, so it is fast
    and minimizer-noise-free."""
    import importlib.util
    from scipy.optimize import brentq
    import mqmqa
    from mqmqa import equilibrium as eqm

    def _load(name, rel):
        spec = importlib.util.spec_from_file_location(name, ROOT / rel)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    olv = _load("olv_join_em", "data/olivine/endmembers.py")
    actM = _load("mgo_act_join", "data/mgo-sio2/_activity.py")
    db = mqmqa.Database.read(str(DAT))
    p = db.phase_index("FEO-MGO-SIO2-LIQUID")

    def melt(components, endmember, lo, hi):
        def f(T):
            inp = eqm.build_inputs(db, p, T, components=components)
            return actM.gm(inp, 1.0 / 3.0) * 7.0 - olv.gibbs(endmember, T)
        return brentq(f, lo, hi, xtol=0.05)

    T_fo = melt(["MG", "SI", "O"], "forsterite", 1900, 2400)
    T_fa = melt(["FE", "SI", "O"], "fayalite", 1300, 1700)
    assert abs(T_fo - 2163) < 5, f"forsterite congruent {T_fo:.0f} K != 2163"
    assert abs(T_fa - 1478) < 5, f"fayalite congruent {T_fa:.0f} K != 1478"
