"""CaO-FeO-MgO-SiO2 combined multiphase file: liquid + ol/opx/cpx + oxides, vs pycalphad.

Validates the multiphase MACHINERY (faithful splice, reads, runs, crystallizes a silicate),
not a quantitative liquidus (the solid-vs-liquid reference calibration is a v0.2 step;
see data/cao-feo-mgo-sio2/PROVENANCE.md)."""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

pycalphad = pytest.importorskip("pycalphad")
from pycalphad import Database, equilibrium, variables as v

import mqmqa


def _load(rel, nm):
    s = importlib.util.spec_from_file_location(nm, ROOT / "data" / rel)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def combined():
    bc = _load("cao-feo-mgo-sio2/build_combined_dat.py", "bc")
    path = bc.build()
    return str(path), mqmqa.Database.read(str(path)), Database(str(path))


def test_eight_phases(combined):
    _, _, pdb = combined
    assert sorted(pdb.phases.keys()) == [
        "CAO-FEO-MGO-SIO2-LIQUID", "CLINOPYROXENE", "CRISTOBALITE", "LIME",
        "OLIVINE", "ORTHOPYROXENE", "PERICLASE", "WUSTITE"]


def test_splice_is_faithful(combined):
    path, db, _ = combined
    liq_src = (ROOT / "data" / "cao-feo-mgo-sio2" / "CaO-FeO-MgO-SiO2-liquid.dat"
               ).read_text().splitlines()[6:]
    lines = Path(path).read_text().splitlines()
    i0 = lines.index(" CaO-FeO-MgO-SiO2-liquid")
    assert lines[i0:i0 + len(liq_src)] == liq_src            # liquid block byte-identical
    s = mqmqa.Database.read(str(ROOT / "data" / "olivine-opx-cpx" / "Olivine-Opx-Cpx-CEF.dat"))
    for ph, Y in [("CLINOPYROXENE", [1, 0.3, 0.7, 1, 1]),
                  ("OLIVINE", [0.3, 0.7, 1, 1]), ("ORTHOPYROXENE", [0.3, 0.7, 1, 1])]:
        a = db.cef_gibbs(db.phase_index(ph), Y, 1600.0, per_mole_atoms=True)
        b = s.cef_gibbs(s.phase_index(ph), Y, 1600.0, per_mole_atoms=True)
        assert a == pytest.approx(b, abs=1e-6), ph


def test_multiphase_crystallization_runs(combined):
    """A slag melt crystallizes a silicate on cooling (fully liquid hot, solid+liquid cold)."""
    _, _, pdb = combined
    el = {"CA": 0.25, "FE": 0.1, "MG": 0.2, "SI": 0.45}
    el["O"] = el["CA"] + el["FE"] + el["MG"] + 2 * el["SI"]
    tot = sum(el.values())
    cond = lambda T: {v.T: T, v.P: 101325, v.N: 1, v.X("CA"): el["CA"] / tot,
                      v.X("FE"): el["FE"] / tot, v.X("MG"): el["MG"] / tot,
                      v.X("SI"): el["SI"] / tot}
    hot = equilibrium(pdb, ["CA", "FE", "MG", "SI", "O"], list(pdb.phases.keys()), cond(2000.0))
    assert sorted(set(str(x) for x in hot.Phase.values.ravel() if x)) == \
        ["CAO-FEO-MGO-SIO2-LIQUID"]
    cold = equilibrium(pdb, ["CA", "FE", "MG", "SI", "O"], list(pdb.phases.keys()), cond(1700.0))
    ph = set(str(x) for x in cold.Phase.values.ravel() if x)
    assert "CAO-FEO-MGO-SIO2-LIQUID" in ph and len(ph) >= 2   # a solid crystallized
