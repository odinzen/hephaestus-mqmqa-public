"""The fully self-contained C multiphase equilibrium (mqmqa_equilibrium_ternary):
every candidate generated in C - liquid on a composition grid via mqmqa_equilibrate_db,
CEF solid solutions via cef_gibbs, stoichiometric compounds direct - then the C lower
hull and assemblage. Validated against pycalphad on FeO-MgO-SiO2: stable phase sets and
equilibrium Gibbs at the interior tie-triangle / solid-solid points."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("pycalphad")
pytest.importorskip("scipy")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
DDIR = ROOT / "data" / "feo-mgo-sio2"

from mqmqa._abi import _ffi, _lib                       # noqa: E402
_ffi.cdef("int mqmqa_equilibrium_ternary(const void*,int,const int*,int,double,int,int,"
          "int,int,double,double,int*,double*,int,double*);", override=True)

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


@pytest.mark.skipif(not (DDIR / "build_combined_dat.py").exists(), reason="combined driver missing")
def test_self_contained_c_equilibrium_matches_pycalphad():
    from pycalphad import Database, equilibrium, variables as v
    _load("bc", DDIR / "build_combined_dat.py").build()
    dbf = Database(str(DDIR / "FeO-MgO-SiO2-combined.dat"))
    text = open(DDIR / "FeO-MgO-SiO2-combined.dat", encoding="utf-8").read()
    cdb = _lib.mqmqa_db_read_string(text.encode())
    try:
        els = [_ffi.string(_lib.mqmqa_db_element(cdb, e)).decode()
               for e in range(_lib.mqmqa_db_num_elements(cdb))]
        iFE, iSI = els.index("FE"), els.index("SI")
        liq = _lib.mqmqa_db_phase_index(cdb, b"FEO-MGO-SIO2-LIQUID")
        cefs = _ffi.new("int[]", [_lib.mqmqa_db_phase_index(cdb, b"OLIVINE"),
                                  _lib.mqmqa_db_phase_index(cdb, b"ORTHOPYROXENE")])

        def tagname(t):
            if t >= 0:
                return _key(_ffi.string(_lib.mqmqa_db_phase_name(cdb, t)).decode())
            return _ffi.string(_lib.mqmqa_db_stoich_name(cdb, -t - 1)).decode()

        for x_fe, x_si, expected in INTERIOR:
            po = _ffi.new("int[]", 8); am = _ffi.new("double[]", 8); gm = _ffi.new("double[]", 1)
            m = _lib.mqmqa_equilibrium_ternary(cdb, liq, cefs, 2, 1600.0, 120, 60,
                                               iFE, iSI, x_fe, x_si, po, am, 8, gm)
            assert m > 0
            cset = {tagname(po[k]) for k in range(m) if am[k] > 1e-3}
            cgm = gm[0] / (2.0 + x_si)
            assert cset == expected, (x_fe, x_si, cset)
            x_mg = 1 - x_fe - x_si
            O = x_fe + x_mg + 2 * x_si
            tot = 1 + O
            eq = equilibrium(dbf, ["FE", "MG", "SI", "O"],
                             ["FEO-MGO-SIO2-LIQUID", "OLIVINE", "ORTHOPYROXENE",
                              "CRISTOBALITE", "PERICLASE", "WUSTITE"],
                             {v.T: 1600.0, v.P: 1e5, v.N: 1,
                              v.X("FE"): x_fe / tot, v.X("MG"): x_mg / tot, v.X("SI"): x_si / tot})
            pset = {_key(str(p)) for p in np.ravel(eq.Phase.values.squeeze())
                    if str(p) and str(p) != "nan"}
            assert cset == pset, (x_fe, x_si, cset, pset)
            assert abs(cgm - float(eq.GM.values.squeeze())) < 10.0
    finally:
        _lib.mqmqa_db_free(cdb)
