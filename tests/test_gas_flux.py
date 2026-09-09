"""Chloride flux coupled to its furnace vapour (gas_flux).

The fume partial pressure of each salt is p_i = a_i * p_i^o: the engine's melt activity times
the measured pure-component vapour pressure. Checks, without needing an external oracle:

  1. Pure-component vapour pressures reproduce the measured normal boiling points (p = 1 atm at
     the boiling point) for NaCl and KCl.
  2. Activities obey the pure limit: a_i -> x_i as the melt approaches pure i (unit activity
     coefficient), the definitional anchor of a Raoultian activity.
  3. The NaCl-KCl binary shows the measured small negative deviation from ideality (gamma below
     one, deepest near equimolar, returning to one at the edges).
  4. In the 40/40/20 flux MgCl2's activity is far below its mole fraction (chlorocomplexing),
     so the fume is alkali-chloride rich even though a fifth of the flux is magnesium.
  5. The total fume rises monotonically and steeply with temperature.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
from mqmqa import gas_flux  # noqa: E402

FLUX = {"NaCl": 0.4, "KCl": 0.4, "MgCl2": 0.2}


def test_pure_vapor_pressure_reproduces_boiling_points():
    # normal boiling points (K): NaCl 1738, KCl 1680; p = 1 atm = 1.01325 bar there
    assert abs(gas_flux.pure_vapor_pressure("NaCl", 1738) - 1.01325) < 0.02
    assert abs(gas_flux.pure_vapor_pressure("KCl", 1680) - 1.01325) < 0.02
    # MgCl2 climbs steeply and stays positive over the tabulated range
    assert 0 < gas_flux.pure_vapor_pressure("MgCl2", 1000) < gas_flux.pure_vapor_pressure("MgCl2", 1400)


def test_activity_pure_limit():
    # as x(NaCl) -> 1 the activity coefficient -> 1, so a -> x
    for x in (0.99, 0.999):
        comp = {"NaCl": x, "KCl": (1 - x) / 2, "MgCl2": (1 - x) / 2}
        a = gas_flux.salt_activities(1200.0, comp)["NaCl"]
        assert abs(a - x) < 5e-3, (x, a)


def test_nacl_kcl_binary_small_negative_deviation():
    # NaCl-KCl is a near-ideal system with a small negative deviation: gamma < 1, minimum near
    # equimolar, tending to 1 at the dilute edges.
    g = {}
    for xN in (0.25, 0.5, 0.75):
        a = gas_flux.salt_activities(1200.0, {"NaCl": xN, "KCl": 1 - xN})["NaCl"]
        g[xN] = a / xN
    assert all(0.8 < g[x] < 1.0 for x in g)          # small negative deviation
    assert g[0.5] < g[0.75]                            # deeper toward the middle
    assert g[0.75] > 0.95                              # returning to ideal at the edge


def test_mgcl2_is_suppressed_in_the_flux():
    a = gas_flux.salt_activities(1200.0, FLUX)
    # NaCl close to its mole fraction (near-ideal), MgCl2 far below its 0.20 (complexing)
    assert abs(a["NaCl"] - 0.4) < 0.05
    assert a["MgCl2"] < 0.05
    assert a["MgCl2"] < 0.2 * a["NaCl"]               # well under a Raoultian magnesium fume


def test_flux_fume_is_alkali_rich_and_grows_with_T():
    lo = gas_flux.flux_vapor(1100.0, FLUX)
    hi = gas_flux.flux_vapor(1350.0, FLUX)
    assert hi["total"] > 20 * lo["total"]            # steep climb with temperature
    for v in (lo, hi):
        assert v["MgCl2"] / v["total"] < 0.1          # magnesium a small slice of the fume
        assert (v["NaCl"] + v["KCl"]) / v["total"] > 0.9
