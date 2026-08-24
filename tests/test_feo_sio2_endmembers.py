"""Validate the FeO-SiO2 liquid: v0.1 endmembers (structure) and the v0.3 excess.

Endmembers: the .dat loads in the C engine, its pure-oxide Gibbs energies match a direct
H - T*S of the open JANAF/R&H data, and the fusion points reproduce. v0.3: the shipped
.dat carries the activity-fitted excess, reproduces fayalite congruent melting at 1478 K
with a single-welled (gap-free) mixing free energy, and its FeO(l) endmember carries the
below-1650 K phase-diagram calibration (a second temperature interval) that is orthogonal
to the modelled activities.
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
                    reason="shipped v0.3 .dat not present")
def test_v03_excess_is_present_and_gap_free():
    """The shipped v0.3 .dat carries the fitted excess, and its mixing free energy is
    negative and single-welled (no spurious FeO-SiO2 miscibility gap)."""
    from mqmqa import equilibrium as eq
    act = _load("feo_sio2_activity", "_activity.py")

    db = mqmqa.Database.read(str(ROOT / "data" / "feo-sio2" / "FeO-SiO2-liquid.dat"))
    p = db.phase_index("FEO-SIO2-LIQUID")
    assert len(db.mqmx(p, 1700.0)["A"]) >= 1, "shipped v0.3 .dat has no excess parameters"

    inp = eq.build_inputs(db, p, 1700.0, components=["FE", "SI", "O"])
    xf = np.linspace(0.1, 0.9, 33)
    gf = np.array([act.delta_g_mix(inp, float(x)) for x in xf])
    assert gf.max() < 0.0, "delta_g_mix should be negative (favorable mixing)"
    h = xf[1] - xf[0]
    d2 = (gf[2:] - 2 * gf[1:-1] + gf[:-2]) / h ** 2
    assert d2.min() > -50.0, f"spurious gap: min d2(dGmix) = {d2.min():.0f}"


@pytest.mark.skipif(not (ROOT / "data" / "feo-sio2" / "FeO-SiO2-liquid.dat").exists(),
                    reason="shipped v0.3 .dat not present")
def test_v03_reproduces_activities_and_fayalite_melting():
    """The shipped v0.3 liquid reproduces the digitized iron-saturated a(FeO) (Bjorkman
    1985 Fig 3) and fayalite congruent melting at 1478 K."""
    fit = _load("v03_fit", "v03_fit.py")
    pdg = _load("feo_sio2_phase_diagram", "phase_diagram.py")
    from mqmqa import equilibrium as eq
    act = _load("feo_sio2_activity2", "_activity.py")

    db = mqmqa.Database.read(str(ROOT / "data" / "feo-sio2" / "FeO-SiO2-liquid.dat"))
    p = db.phase_index("FEO-SIO2-LIQUID")

    res = []
    for X, a, src, T in fit.load_activities():
        inp = eq.build_inputs(db, p, T, components=["FE", "SI", "O"])
        am, _ = act.activities(inp, 1.0 - X, T)
        res.append(math.log(am / a))
    rms = math.sqrt(sum(r * r for r in res) / len(res))
    assert rms < 0.10, f"a(FeO) RMS ln a = {rms:.3f} too large"

    Tc = fit.congruent_T(db, p)
    assert abs(Tc - 1478.0) < 5.0, f"fayalite congruent melting {Tc:.0f} K != 1478 K"

    # excess entropy is physical (v0.2's +78.6 J/mol/K is retired)
    inp1 = eq.build_inputs(db, p, 1500.0, components=["FE", "SI", "O"])
    inp2 = eq.build_inputs(db, p, 1900.0, components=["FE", "SI", "O"])
    b00 = (inp2["ex"]["L"][0] - inp1["ex"]["L"][0]) / 400.0
    assert abs(b00) < 40.0, f"excess entropy b00 = {b00:.1f} not physical"


@pytest.mark.skipif(not (ROOT / "data" / "feo-sio2" / "FeO-SiO2-liquid.dat").exists(),
                    reason="shipped v0.3 .dat not present")
def test_v03_feo_below_tm_correction_is_orthogonal_to_activities():
    """The FeO(l) below-1650 K correction moves the melting point but leaves the modelled
    a(FeO)/a(SiO2) unchanged, and vanishes at/above 1650 K."""
    from mqmqa import equilibrium as eq
    bd_feo = _load("feo_sio2_build_dat2", "build_dat.py")
    act = _load("feo_sio2_activity3", "_activity.py")

    # shipped .dat FeO endmember matches the uncorrected JANAF-fusion liquid at/above 1650 K
    db = mqmqa.Database.read(str(ROOT / "data" / "feo-sio2" / "FeO-SiO2-liquid.dat"))
    p = db.phase_index("FEO-SIO2-LIQUID")
    for T in (1650.0, 1996.0):
        g = db.pairs(p, T)["G"][bd_feo.ORDER.index("FeO")]
        assert abs(g - _liquid(bd_feo.OXIDES["FeO"], T)) < 1e-4, \
            f"FeO(l) at {T} K should be uncorrected (correction is 0 above 1650 K)"
    # and below 1650 K it is destabilized (correction > 0)
    g1500 = db.pairs(p, 1500.0)["G"][bd_feo.ORDER.index("FeO")]
    assert g1500 > _liquid(bd_feo.OXIDES["FeO"], 1500.0) + 100.0, \
        "FeO(l) below 1650 K should carry the phase-diagram destabilization"

    # activities are invariant to the correction (orthogonality): two beta give equal a(FeO)
    excess = [dict(code="Q", li=[1, 2, 3, 3], exp=[0, 0, 0, 0], coeffs=[-42839.0, 17.83, 0, 0, 0, 0]),
              dict(code="Q", li=[1, 2, 3, 3], exp=[1, 0, 0, 0], coeffs=[0.0] * 6)]
    a_by_beta = []
    for beta in (0.0, -50.0):
        d = ROOT / "data" / "feo-sio2" / f"_test_ortho_{int(beta)}.dat"
        d.write_text(bd_feo.build(excess, feo_liq_beta=beta), encoding="ascii")
        dbb = mqmqa.Database.read(str(d))
        pp = dbb.phase_index("FEO-SIO2-LIQUID")
        inp = eq.build_inputs(dbb, pp, 1580.0, components=["FE", "SI", "O"])
        a_by_beta.append(act.activities(inp, 1.0 - 0.667, 1580.0)[0])
        d.unlink(missing_ok=True)
    assert abs(a_by_beta[0] - a_by_beta[1]) < 1e-9, \
        f"FeO correction is not orthogonal to a(FeO): {a_by_beta}"
