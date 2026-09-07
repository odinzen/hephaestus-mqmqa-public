"""The C multiphase geometry (lower hull + assemblage query, src/hull.c) must
reproduce pycalphad's equilibrium: the stable phase SET and the equilibrium Gibbs
energy at interior tie-triangle / solid-solid points of the FeO-MgO-SiO2 system.
Candidate points come from the validated Python generator; the geometry under test
is the C hull and the C assemblage query."""
import importlib.util
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("pycalphad")
pytest.importorskip("scipy")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
DDIR = ROOT / "data" / "feo-mgo-sio2"

from mqmqa._abi import _ffi, _lib                       # noqa: E402
_ffi.cdef("int mqmqa_lower_hull_2d(const double*,int,int*,int);"
          "int mqmqa_hull_assemblage_2d(const double*,int,const int*,int,double,double,"
          "int*,double*,double*);", override=True)

INTERIOR = [
    (0.20, 0.30, {"OLIVINE", "WUSTITE"}),
    (0.12, 0.46, {"OLIVINE", "ORTHOPYROXENE"}),
    (0.06, 0.52, {"CRISTOBALITE", "ORTHOPYROXENE"}),
    (0.30, 0.10, {"OLIVINE", "PERICLASE", "WUSTITE"}),
    (0.08, 0.12, {"OLIVINE", "PERICLASE", "WUSTITE"}),
]


def _load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def _key(nm):
    return "LIQUID" if nm.startswith("FEO-MGO-SIO2") else nm


@pytest.mark.skipif(not (DDIR / "ternary_diagram.py").exists(), reason="ternary driver missing")
def test_c_hull_assemblage_matches_pycalphad():
    from pycalphad import Database, equilibrium, variables as v
    bc = _load("bc", DDIR / "build_combined_dat.py")
    td = _load("td", DDIR / "ternary_diagram.py")
    bc.build()
    dbf = Database(str(DDIR / "FeO-MgO-SiO2-combined.dat"))
    T = 1600.0
    pts, _ = td.build(T, nsamp=8000, n_cef=161)
    n = len(pts)
    flat = _ffi.new("double[]", [c for p in pts for c in (p.x_fe, p.x_si, p.g)])
    fac = _ffi.new("int[]", 3 * (6 * n + 64))
    nf = _lib.mqmqa_lower_hull_2d(flat, n, fac, 6 * n + 64)
    assert nf > 0

    for x_fe, x_si, expected in INTERIOR:
        tri = _ffi.new("int[]", 3); w = _ffi.new("double[]", 3); g = _ffi.new("double[]", 1)
        assert _lib.mqmqa_hull_assemblage_2d(flat, n, fac, nf, x_fe, x_si, tri, w, g) == 1
        agg = defaultdict(float)
        for k in range(3):
            if w[k] > 1e-6:
                agg[_key(pts[tri[k]].phase)] += w[k]
        cset = {k for k, val in agg.items() if val > 1e-3}
        cgm = g[0] / (2.0 + x_si)
        assert cset == expected, (x_fe, x_si, cset)
        x_mg = 1 - x_fe - x_si; O = x_fe + x_mg + 2 * x_si; tot = 1 + O
        eq = equilibrium(dbf, ["FE", "MG", "SI", "O"],
                         ["FEO-MGO-SIO2-LIQUID", "OLIVINE", "ORTHOPYROXENE",
                          "CRISTOBALITE", "PERICLASE", "WUSTITE"],
                         {v.T: T, v.P: 1e5, v.N: 1,
                          v.X("FE"): x_fe / tot, v.X("MG"): x_mg / tot, v.X("SI"): x_si / tot})
        pset = {_key(str(p)) for p in np.ravel(eq.Phase.values.squeeze()) if str(p) and str(p) != "nan"}
        assert cset == pset, (x_fe, x_si, cset, pset)
        assert abs(cgm - float(eq.GM.values.squeeze())) < 10.0
