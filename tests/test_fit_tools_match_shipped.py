"""The fitting code and the shipped files must agree on every solid.

Each binary assessment (data/<system>/phase_diagram.py, used by its assess.py) evaluates the
solids itself; the shipped combined files carry the same phases, written by the builders. If
the two disagree, the fit is made against energies no user ever sees. From 2026-08-22 to
2026-09-29 the MgO-SiO2 and CaO-SiO2 fitting code applied the quartz-to-cristobalite shift to
pure cristobalite, 2.3 kJ that no shipped file carried; this test is the guard. Energies are
compared per mole of oxide formula units, at print precision."""
import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
import mqmqa

FMS = ROOT / "data" / "feo-mgo-sio2" / "FeO-MgO-SiO2-combined.dat"
QUAT = ROOT / "data" / "cao-feo-mgo-sio2" / "CaO-FeO-MgO-SiO2-combined.dat"
TEMPS = (800.0, 1300.0, 1800.0, 2200.0)
LOCAL = ("phase_diagram", "build_dat", "_activity", "silicates", "endmembers")

# (binary folder, fit-tool solid, shipped file, shipped phase, how to read it, oxide units)
CASES = [
    ("mgo-sio2", "SiO2(cristobalite)", FMS, "CRISTOBALITE", "stoich", 1),
    ("mgo-sio2", "MgO(periclase)", FMS, "MAGNESIOWUSTITE", ("cef", 1.0), 1),
    ("mgo-sio2", "M2S(forsterite)", FMS, "OLIVINE", ("cef", 1.0), 3),
    ("mgo-sio2", "MS(enstatite)", FMS, "ORTHOPYROXENE", ("cef", 1.0), 4),
    ("cao-sio2", "SiO2(cristobalite)", QUAT, "CRISTOBALITE", "stoich", 1),
    ("cao-sio2", "CaO(lime)", QUAT, "LIME", "stoich", 1),
    ("cao-sio2", "CS(pseudowoll)", QUAT, "WOLLASTONITE", "stoich", 2),
    ("cao-sio2", "C3S2(rankinite)", QUAT, "RANKINITE", "stoich", 5),
    ("cao-sio2", "C2S", QUAT, "LARNITE", "stoich", 3),
    ("cao-sio2", "C3S", QUAT, "HATRURITE", "stoich", 4),
    ("feo-sio2", "Fa(fayalite)", FMS, "OLIVINE", ("cef", 0.0), 3),
]


def _fit_tool(folder):
    """data/<folder>/phase_diagram.py with its own build_dat and helpers, not another
    binary's modules of the same name."""
    for name in LOCAL:
        sys.modules.pop(name, None)
    here = str(ROOT / "data" / folder)
    sys.path.insert(0, here)
    try:
        return importlib.import_module("phase_diagram")
    finally:
        sys.path.remove(here)
        for name in LOCAL:
            sys.modules.pop(name, None)


@pytest.fixture(scope="module")
def tools():
    return {f: _fit_tool(f) for f in {c[0] for c in CASES}}


@pytest.fixture(scope="module")
def shipped():
    return {p: mqmqa.Database.read(str(p)) for p in {c[2] for c in CASES}}


@pytest.mark.parametrize("folder,solid,path,phase,how,units", CASES,
                         ids=[f"{c[0]}:{c[1]}" for c in CASES])
def test_fit_tool_solid_is_the_shipped_solid(tools, shipped, folder, solid, path, phase, how, units):
    pdg, db = tools[folder], shipped[path]
    for T in TEMPS:
        if how == "stoich":
            g = db.stoich_gibbs(db.stoich.index(phase), T)
        else:
            g, _ = db.cef_line_gibbs(db.phase_index(phase), how[1], T, per_mole_atoms=False)
        g_tool, _ = pdg.solid_gibbs_per_formula_unit(solid, T)
        assert g / units == pytest.approx(g_tool, abs=1.0), (solid, T, g / units - g_tool)
