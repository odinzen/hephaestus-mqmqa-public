"""Toolchain proof: C library reachable from Python and numerically correct."""

import math

from mqmqa import R, ideal_entropy_binary


def test_gas_constant():
    # CALPHAD/SGTE conventional value, matching pycalphad v.R (not CODATA 2018)
    assert abs(R() - 8.3145) < 1e-9


def test_ideal_binary_entropy_matches_hand_value():
    x = 0.3
    expected = -8.3145 * (x * math.log(x) + (1.0 - x) * math.log(1.0 - x))
    assert abs(ideal_entropy_binary(x) - expected) < 1e-12


def test_ideal_binary_entropy_endpoints_zero():
    assert ideal_entropy_binary(0.0) == 0.0
    assert ideal_entropy_binary(1.0) == 0.0
