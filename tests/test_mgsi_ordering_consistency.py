"""The Mg-Si ordering composition (data/mgo-sio2/build_dat.MGSI_SRO_X) is written into every file with
an MgO-SiO2 liquid as one explicit (Mg,Si/O,O) coordination row. Off its default the FeO-MgO-SiO2
liquid on its Fe-free edge must stay the binary liquid; leaving the row out of the ternary costs
about 550 J/mol at x 0.32 (2026-10-03)."""
import importlib
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
import mqmqa                                   # noqa: E402
from mqmqa import equilibrium as eq, vis3d     # noqa: E402

LOCAL = ("assess", "phase_diagram", "build_dat", "_activity", "silicates", "endmembers", "dataset",
         "phase_hull", "v05_fit", "validate")
X_SRO = 0.32


def _load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def pair(tmp_path_factory):
    for name in LOCAL:
        sys.modules.pop(name, None)
    here = str(ROOT / "data" / "mgo-sio2" / "assessment")
    sys.path.insert(0, here)
    try:
        a = importlib.import_module("assess")
        pp = a.assessed_liquid()
        pp += [X_SRO - 1.0 / 3.0, a.bd.MGO_LIQ_DCP, 0.0, a.pdg.em.ENSTATITE_DG_1830]
        db, p, _ = a.build_db(pp)
        fms = _load("fms_sro_test", ROOT / "data" / "feo-mgo-sio2" / "build_dat.py")
        fms._mgo.MGSI_SRO_X = X_SRO
        path = tmp_path_factory.mktemp("sro") / "fms.dat"
        path.write_text(fms.build(), encoding="ascii")
        yield a, db, p, mqmqa.Database.read(str(path))
    finally:
        sys.path.remove(here)
        for name in LOCAL:
            sys.modules.pop(name, None)


@pytest.mark.parametrize("T", [1700.0, 2300.0])
@pytest.mark.parametrize("x", [0.1, 0.265, 0.45, 0.8])
def test_fms_edge_is_the_binary_liquid(pair, T, x):
    a, db, p, dbt = pair
    g_bin = a.pdg.liquid_gibbs_per_formula_unit(eq.build_inputs(db, p, T, components=a.COMP), x, T)
    g_fms, _ = vis3d.liquid_gibbs(dbt, "FEO-MGO-SIO2-LIQUID", T, 1.0 - x, x)
    assert g_fms == pytest.approx(g_bin, abs=0.1)


def test_default_writes_no_mixed_row():
    bd = _load("mgo_bd_sro_test", ROOT / "data" / "mgo-sio2" / "build_dat.py")
    if abs(bd.MGSI_SRO_X - 1.0 / 3.0) > 1e-12:
        pytest.skip("an assessed ordering composition is stored")
    assert bd.mgsi_mixed_z() is None
    z = bd.mgsi_mixed_z(X_SRO)
    assert 2.0 / z[0] + 4.0 / z[1] == pytest.approx(4.0 / z[2], abs=1e-12)
