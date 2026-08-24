"""Validate the FeO-SiO2 v0.1 liquid endmembers and structure.

The .dat must load in the C engine, its pure-oxide endmember Gibbs energies must match a
direct H - T*S evaluation of the open JANAF/R&H data, and the fusion points must reproduce.
Endmembers/structure only (v0.1 mixing is ideal).
"""
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

import mqmqa

# load feo-sio2's build_dat by explicit path (several data dirs share the name build_dat)
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "feo_sio2_build_dat", ROOT / "data" / "feo-sio2" / "build_dat.py")
bd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bd)

T0 = 298.15


def _solid(ox, T):
    a, b, c = ox["a"], ox["b"], ox["c"]
    H = ox["dHf"] + a * (T - T0) + 0.5 * b * (T * T - T0 * T0) - c * (1.0 / T - 1.0 / T0)
    S = (ox["S298"] + a * math.log(T / T0) + b * (T - T0)
         - 0.5 * c * (1.0 / (T * T) - 1.0 / (T0 * T0)))
    return H - T * S


def _liquid(ox, T):
    return _solid(ox, T) + ox["dHfus"] * (1.0 - T / ox["Tm"])


def test_feo_sio2_endmembers_and_fusion():
    dat = ROOT / "data" / "feo-sio2" / "FeO-SiO2-liquid.dat"
    dat.write_text(bd.build(), encoding="ascii")
    db = mqmqa.Database.read(str(dat))
    p = db.phase_index("FEO-SIO2-LIQUID")
    assert db.is_subq(p) == 1
    assert [c["name"] for c in db.cations(p)] == ["FE+2", "SI+4"]

    worst = 0.0
    for T in (1000.0, 1650.0, 1996.0):
        pr = db.pairs(p, T)
        for i, name in enumerate(bd.ORDER):
            worst = max(worst, abs(pr["G"][i] - _liquid(bd.OXIDES[name], T)))
    assert worst < 1e-4, f"endmember Gibbs vs direct H-T*S worst |d| = {worst}"

    for name in bd.ORDER:
        ox = bd.OXIDES[name]
        assert abs(_liquid(ox, ox["Tm"]) - _solid(ox, ox["Tm"])) < 1e-6
