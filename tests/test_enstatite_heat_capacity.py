"""Enstatite above 800 K follows the drop-calorimetry heat capacity of Thieblot, Tequi & Richet 1999
(Am. Mineral. 84, 848, Table 3), not the Robie-Hemingway fit extrapolated past its 1000 K limit. The
R&H A5*T^2 term reached 176 J/K at 1830 K and put orthopyroxene back above the liquid near 3100 K
(2026-10-02). The switch must keep G, H and S continuous, and the two-site orthopyroxene must carry it."""
import importlib.util
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def em():
    return _load("em_cp_test", ROOT / "data" / "olivine" / "endmembers.py")


@pytest.fixture(scope="module")
def opx():
    return _load("opx_cp_test", ROOT / "data" / "olivine-opx" / "orthopyroxene.py")


def _thieblot(T):
    return 201.585 - 11.933e-3 * T + 0.46073e5 / T ** 2 - 2011.5 / T ** 0.5


def _cp_from_g(f, T, h=0.5):
    return -T * (f(T + h) - 2 * f(T) + f(T - h)) / h ** 2


@pytest.mark.parametrize("T", [900.0, 1400.0, 1830.0, 2500.0, 3300.0])
def test_cp_follows_thieblot_above_800_k(em, T):
    assert _cp_from_g(lambda t: em.gibbs("enstatite", t), T) == pytest.approx(_thieblot(T), abs=0.05)


def test_robie_hemingway_untouched_below_800_k(em):
    d = em.ENDMEMBERS["enstatite"]
    T = 600.0
    rh = d["A1"] + d["A2"] * T + d["A3"] / T ** 2 + d["A4"] / math.sqrt(T) + d["A5"] * T * T
    assert _cp_from_g(lambda t: em.gibbs("enstatite", t), T) == pytest.approx(rh, abs=0.05)


def test_g_and_s_continuous_at_the_switch(em):
    (t, low), (_, high) = em.intervals("enstatite")
    g = lambda c, T: em.eval_coeffs(c, T)
    s = lambda c, T, h=1e-3: -(g(c, T + h) - g(c, T - h)) / (2 * h)
    assert g(low, t) == pytest.approx(g(high, t), abs=1e-6)
    assert s(low, t) == pytest.approx(s(high, t), abs=1e-5)


def test_single_interval_accessor_refuses_enstatite(em):
    with pytest.raises(ValueError):
        em.gibbs_coeffs("enstatite")


@pytest.mark.parametrize("T", [700.0, 1000.0, 1500.0, 2200.0])
def test_orthopyroxene_mg_endmember_carries_it(em, opx, T):
    expected = 2.0 * (em.gibbs("enstatite", T) + em.enstatite_ht(T))
    assert opx.g_end("MG:MG", T) == pytest.approx(expected, abs=1e-6)
