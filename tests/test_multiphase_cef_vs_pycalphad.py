"""Validate CEF phases inside the multiphase equilibrium solver.

The engine's binary hull solver (equilibrium.binary_hull_equilibrium /
miscibility_conjugates) is fed a CEF solid-solution G(x) curve evaluated by the C kernel
(via the ChemSage SUBL reader). The test target is the olivine metastable solvus: below
the consolute the forsterite-fayalite phase unmixes into two olivines, a genuine
two-phase equilibrium of a CEF phase. The conjugate compositions must match pycalphad's
own equilibrium() on the same .dat.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
sys.path.insert(0, str(ROOT / "cef"))
sys.path.insert(0, str(ROOT / "data" / "olivine"))

pytest.importorskip("pycalphad")
from pycalphad import Database as PycDatabase, equilibrium, variables as v

import mqmqa
from mqmqa import equilibrium as eq

X_SI, X_O = 1.0 / 7.0, 4.0 / 7.0


def _dat():
    import build_subl_dat
    d = ROOT / "data" / "olivine" / "Olivine-CEF.dat"
    d.write_text(build_subl_dat.build(), encoding="ascii")
    return d


def _curve(cdb, p, T, n=401):
    pts = []
    for x_fo in np.linspace(1e-4, 1 - 1e-4, n):
        g = cdb.cef_gibbs(p, [1 - x_fo, x_fo, 1.0, 1.0], T, per_mole_atoms=False)
        pts.append((float(x_fo), g, "OLIVINE", float(x_fo)))
    return pts


def _pyc_conjugates(pdb, T):
    res = equilibrium(pdb, ["FE", "MG", "SI", "O"], "OLIVINE",
                      {v.T: T, v.P: 101325, v.X("SI"): X_SI, v.X("O"): X_O,
                       v.X("MG"): (0.005, 0.281, 0.0025)})
    phase = res.Phase.values
    XMG = res.X.sel(component="MG").values.reshape(-1, phase.shape[-1])
    XFE = res.X.sel(component="FE").values.reshape(-1, phase.shape[-1])
    flatP = phase.reshape(-1, phase.shape[-1])
    xfos = []
    for i in range(flatP.shape[0]):
        stable = [k for k in range(flatP.shape[1]) if flatP[i, k] == "OLIVINE"]
        if len(stable) >= 2:
            for k in stable:
                m, f = XMG[i, k], XFE[i, k]
                if m + f > 0:
                    xfos.append(m / (m + f))
    return (min(xfos), max(xfos)) if xfos else None


def test_olivine_solvus_matches_pycalphad():
    dat = _dat()
    cdb = mqmqa.Database.read(str(dat))
    p = cdb.phase_index("OLIVINE")
    pdb = PycDatabase(str(dat))

    worst = 0.0
    for T in (300.0, 400.0):
        conj = eq.miscibility_conjugates(_curve(cdb, p, T), min_span=2e-3)
        assert conj, f"engine found no solvus at {T} K"
        xL, _, xR, _ = max(conj, key=lambda c: c[2] - c[0])
        pyc = _pyc_conjugates(pdb, T)
        assert pyc is not None, f"pycalphad found no solvus at {T} K"
        worst = max(worst, abs(xL - pyc[0]), abs(xR - pyc[1]))
    assert worst < 0.01, f"solvus binodal disagreement {worst}"


def test_hull_assemblage_reports_two_olivines_in_gap():
    """binary_hull_equilibrium returns a two-phase olivine+olivine tie-line for an
    overall composition inside the solvus, and a single phase above the consolute."""
    dat = _dat()
    cdb = mqmqa.Database.read(str(dat))
    p = cdb.phase_index("OLIVINE")

    inside = eq.binary_hull_equilibrium(_curve(cdb, p, 300.0), 0.35)
    assert inside["phases"] == ["OLIVINE", "OLIVINE"]
    assert inside["endpoints"][0] < 0.35 < inside["endpoints"][1]

    above = eq.binary_hull_equilibrium(_curve(cdb, p, 470.0), 0.35)  # > consolute ~447 K
    assert above["phases"] == ["OLIVINE"]
