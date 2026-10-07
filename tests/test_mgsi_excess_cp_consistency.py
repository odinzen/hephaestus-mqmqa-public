"""An excess heat capacity on an MgO-SiO2 liquid term (data/mgo-sio2/build_dat.excess_coeffs) must reach
the FeO-MgO-SiO2 liquid exactly as the fit tool evaluates it: on the Fe-free edge the ternary file is the
binary liquid. A ternary written without the heat capacity is caught (the planted case below)."""
import importlib
import importlib.util
import math
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
import mqmqa                                   # noqa: E402
from mqmqa import equilibrium as eq, vis3d     # noqa: E402

LOCAL = ("assess", "phase_diagram", "build_dat", "_activity", "silicates", "endmembers", "dataset",
         "phase_hull", "v05_fit", "validate")
CP_TERM, DCP = (0, 7), 12.0


def _load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def files(tmp_path_factory):
    for name in LOCAL:
        sys.modules.pop(name, None)
    here = str(ROOT / "data" / "mgo-sio2" / "assessment")
    sys.path.insert(0, here)
    old = os.environ.get("MGO_SIO2_CP_TERMS")
    os.environ["MGO_SIO2_CP_TERMS"] = ",".join(map(str, CP_TERM))
    try:
        a = importlib.import_module("assess")
        pp = a.assessed_liquid()
        pp[a.OFFSET[a.TERMS.index(CP_TERM)] + 2] = DCP
        pp += [a.bd.MGSI_SRO_X - 1.0 / 3.0, a.bd.MGO_LIQ_DCP, 0.0, a.pdg.em.ENSTATITE_DG_1830]
        db, p, _ = a.build_db(pp)

        fms = _load("fms_cp_test", ROOT / "data" / "feo-mgo-sio2" / "build_dat.py")
        planted = fms.build()                  # its excess was read at import, without the heat capacity
        fms._mgo.ASSESSED_EXCESS = [(pw, q, aa, b, DCP if (pw, q) == CP_TERM else dcp)
                                    for pw, q, aa, b, dcp in fms._mgo.assessed_terms()]
        good = fms.build(excess=fms.EX_FEO_SIO2 + fms._mgo.assessed_excess(li=(2, 3, 4, 4))
                         + fms.ternary_excess())
        tmp = tmp_path_factory.mktemp("xscp")
        out = []
        for name, text in (("good", good), ("planted", planted)):
            (tmp / f"{name}.dat").write_text(text, encoding="ascii")
            out.append(mqmqa.Database.read(str(tmp / f"{name}.dat")))
        yield a, db, p, out[0], out[1]
    finally:
        if old is None:
            os.environ.pop("MGO_SIO2_CP_TERMS", None)
        else:
            os.environ["MGO_SIO2_CP_TERMS"] = old
        sys.path.remove(here)
        for name in LOCAL:
            sys.modules.pop(name, None)


POINTS = [(T, x) for T in (1600.0, 2600.0) for x in (0.3, 0.6, 0.9)]


def _edge(a, db, p, dbt, T, x):
    g_bin = a.pdg.liquid_gibbs_per_formula_unit(eq.build_inputs(db, p, T, components=a.COMP), x, T)
    g_fms, _ = vis3d.liquid_gibbs(dbt, "FEO-MGO-SIO2-LIQUID", T, 1.0 - x, x)
    return g_fms - g_bin


@pytest.mark.parametrize("T,x", POINTS)
def test_fms_edge_carries_the_heat_capacity(files, T, x):
    a, db, p, good, _ = files
    assert _edge(a, db, p, good, T, x) == pytest.approx(0.0, abs=0.1)


def test_planted_omission_is_caught(files):
    a, db, p, _, planted = files
    assert max(abs(_edge(a, db, p, planted, T, x)) for T, x in POINTS) > 5.0


def test_engine_reads_the_heat_capacity_coefficients(files, tmp_path):
    """The term written as a + bT + dcp*[(T-T0) - T ln(T/T0)] gives the liquid that term's value at T
    written as a constant gives."""
    a = files[0]
    base = a.bd.assessed_excess()
    i = next(k for k, t in enumerate(base) if t["exp"][:2] == list(CP_TERM))
    aa, b = base[i]["coeffs"][:2]

    def liquid(coeffs, name, T, x):
        ex = [dict(t) for t in base]
        ex[i] = dict(ex[i], coeffs=coeffs)
        (tmp_path / name).write_text(a.bd.build(ex), encoding="ascii")
        db = mqmqa.Database.read(str(tmp_path / name))
        inp = eq.build_inputs(db, db.phase_index("MGO-SIO2-LIQUID"), T, components=a.COMP)
        return a.pdg.liquid_gibbs_per_formula_unit(inp, x, T)

    for T in (1600.0, 2600.0):
        L = aa + b * T + DCP * ((T - a.bd.XS_CP_T0) - T * math.log(T / a.bd.XS_CP_T0))
        for x in (0.5, 0.9):
            assert liquid(a.bd.excess_coeffs(aa, b, DCP), "cp.dat", T, x) == pytest.approx(
                liquid([L, 0, 0, 0, 0, 0], "const.dat", T, x), abs=1e-3)
