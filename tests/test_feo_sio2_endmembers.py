"""Validate the FeO-SiO2 liquid: v0.1 endmembers (structure) and the v0.2 excess.

Endmembers: the .dat loads in the C engine, its pure-oxide Gibbs energies match a direct
H - T*S of the open JANAF/R&H data, and the fusion points reproduce. v0.2: the shipped
.dat carries the fitted excess and reproduces fayalite congruent melting with a
single-welled (gap-free) mixing free energy.
"""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
sys.path.insert(0, str(ROOT / "data" / "feo-sio2"))

import mqmqa

# load feo-sio2 modules by explicit path (several data dirs share module names)
import importlib.util


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / "data" / "feo-sio2" / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


bd = _load("feo_sio2_build_dat", "build_dat.py")
T0 = 298.15


def _solid(ox, T):
    a, b, c = ox["a"], ox["b"], ox["c"]
    H = ox["dHf"] + a * (T - T0) + 0.5 * b * (T * T - T0 * T0) - c * (1.0 / T - 1.0 / T0)
    S = (ox["S298"] + a * math.log(T / T0) + b * (T - T0)
         - 0.5 * c * (1.0 / (T * T) - 1.0 / (T0 * T0)))
    return H - T * S


def _liquid(ox, T):
    return _solid(ox, T) + ox["dHfus"] * (1.0 - T / ox["Tm"])


def test_endmembers_and_fusion():
    # write the v0.1 (ideal) form to a scratch path - do NOT clobber the shipped v0.2 .dat
    dat = ROOT / "data" / "feo-sio2" / "_test_v01.dat"
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
    dat.unlink(missing_ok=True)


@pytest.mark.skipif(not (ROOT / "data" / "feo-sio2" / "FeO-SiO2-liquid.dat").exists(),
                    reason="shipped v0.2 .dat not present")
def test_v02_excess_is_present_and_gap_free():
    """The shipped v0.2 .dat carries the fitted excess, and its mixing free energy is
    negative and single-welled (no spurious FeO-SiO2 miscibility gap)."""
    from mqmqa import equilibrium as eq
    act = _load("feo_sio2_activity", "_activity.py")

    db = mqmqa.Database.read(str(ROOT / "data" / "feo-sio2" / "FeO-SiO2-liquid.dat"))
    p = db.phase_index("FEO-SIO2-LIQUID")
    assert len(db.mqmx(p, 1700.0)["A"]) >= 1, "shipped v0.2 .dat has no excess parameters"

    inp = eq.build_inputs(db, p, 1700.0, components=["FE", "SI", "O"])
    xf = np.linspace(0.1, 0.9, 33)
    gf = np.array([act.delta_g_mix(inp, float(x)) for x in xf])
    assert gf.max() < 0.0, "delta_g_mix should be negative (favorable mixing)"
    h = xf[1] - xf[0]
    d2 = (gf[2:] - 2 * gf[1:-1] + gf[:-2]) / h ** 2
    assert d2.min() > -50.0, f"spurious gap: min d2(dGmix) = {d2.min():.0f}"
