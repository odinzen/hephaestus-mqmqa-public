"""The OCASI-compatible TQ interface (src/tq.c) driven end to end must reproduce
pycalphad: tq_init -> tq_read_string -> tq_set_TP -> tq_set_composition ->
tq_compute_equilibrium -> tq_G / tq_stable_phase. This is the embedding surface an
OCASI-built application would bind, running on the Hephaestus engine."""
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
_ffi.cdef("""
  void* tq_init(void);
  int tq_read_string(void*, const char*);
  void tq_free(void*);
  const char* tq_error(const void*);
  int tq_num_phases(const void*);
  const char* tq_phase_name(const void*, int);
  int tq_num_components(const void*);
  const char* tq_component(const void*, int);
  int tq_set_TP(void*, double, double);
  int tq_set_composition(void*, const double*);
  int tq_compute_equilibrium(void*);
  double tq_G(const void*);
  int tq_num_stable_phases(const void*);
  int tq_stable_phase(const void*, int, double*);
""", override=True)

INTERIOR = [(0.20, 0.30), (0.12, 0.46), (0.06, 0.52), (0.30, 0.10), (0.08, 0.12)]


def _load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def _key(nm):
    return "LIQUID" if nm.startswith("FEO-MGO-SIO2") else nm


@pytest.mark.skipif(not (DDIR / "build_combined_dat.py").exists(), reason="combined driver missing")
def test_tq_interface_matches_pycalphad():
    from pycalphad import Database, equilibrium, variables as v
    _load("bc", DDIR / "build_combined_dat.py").build()
    dbf = Database(str(DDIR / "FeO-MgO-SiO2-combined.dat"))
    text = open(DDIR / "FeO-MgO-SiO2-combined.dat", encoding="utf-8").read()

    ctx = _lib.tq_init()
    try:
        assert _lib.tq_read_string(ctx, text.encode()) == 0, _ffi.string(_lib.tq_error(ctx)).decode()
        comps = [_ffi.string(_lib.tq_component(ctx, i)).decode()
                 for i in range(_lib.tq_num_components(ctx))]
        iFE, iMG, iSI, iO = (comps.index(e) for e in ("FE", "MG", "SI", "O"))

        for x_fe, x_si in INTERIOR:
            x_mg = 1 - x_fe - x_si
            O = x_fe + x_mg + 2 * x_si
            amt = _ffi.new("double[]", len(comps))
            amt[iFE] = x_fe; amt[iMG] = x_mg; amt[iSI] = x_si; amt[iO] = O
            _lib.tq_set_TP(ctx, 1600.0, 101325.0)
            _lib.tq_set_composition(ctx, amt)
            assert _lib.tq_compute_equilibrium(ctx) == 0, _ffi.string(_lib.tq_error(ctx)).decode()
            am = _ffi.new("double[]", 1)
            cset = set()
            for k in range(_lib.tq_num_stable_phases(ctx)):
                ph = _lib.tq_stable_phase(ctx, k, am)
                if am[0] > 1e-3:
                    cset.add(_key(_ffi.string(_lib.tq_phase_name(ctx, ph)).decode()))
            cgm = _lib.tq_G(ctx) / (2.0 + x_si)

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
        _lib.tq_free(ctx)
