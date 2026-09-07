"""Stage 4 (phase-status conditions) and Stage 5 (adaptive refinement) of the C
equilibrium engine, mqmqa_equilibrium_ternary_ex.

Stage 4: suspending a phase excludes it from the hull and yields the metastable
equilibrium without it - the stable phase SET must match pycalphad run without that
phase in its list.

Stage 5: refinement densifies the liquid sampling around the liquid hull vertices; the
liquid-boundary Gibbs error against pycalphad must decrease (or hold) with more passes.
It improves the flat-liquid tie-line endpoint but does not fully resolve it (that needs
a common-tangent construction), so the assertion is monotone improvement, not a bound.
"""
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
_ffi.cdef("int mqmqa_equilibrium_ternary_ex(const void*,int,const int*,int,double,int,int,"
          "int,int,double,double,const int*,int,int*,double*,int,double*);", override=True)

ALL = ["FEO-MGO-SIO2-LIQUID", "OLIVINE", "ORTHOPYROXENE",
       "CRISTOBALITE", "PERICLASE", "WUSTITE"]


def _load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def _key(nm):
    return "LIQUID" if nm.startswith("FEO-MGO-SIO2") else nm


@pytest.fixture(scope="module")
def engine():
    _load("bc", DDIR / "build_combined_dat.py").build()
    from pycalphad import Database
    dbf = Database(str(DDIR / "FeO-MgO-SiO2-combined.dat"))
    text = open(DDIR / "FeO-MgO-SiO2-combined.dat", encoding="utf-8").read()
    cdb = _lib.mqmqa_db_read_string(text.encode())
    els = [_ffi.string(_lib.mqmqa_db_element(cdb, e)).decode()
           for e in range(_lib.mqmqa_db_num_elements(cdb))]
    ctx = dict(dbf=dbf, cdb=cdb, iFE=els.index("FE"), iSI=els.index("SI"),
               liq=_lib.mqmqa_db_phase_index(cdb, b"FEO-MGO-SIO2-LIQUID"),
               cefs=_ffi.new("int[]", [_lib.mqmqa_db_phase_index(cdb, b"OLIVINE"),
                                       _lib.mqmqa_db_phase_index(cdb, b"ORTHOPYROXENE")]),
               nst=_lib.mqmqa_db_num_stoich(cdb))
    ctx["stnames"] = [_ffi.string(_lib.mqmqa_db_stoich_name(cdb, j)).decode()
                      for j in range(ctx["nst"])]
    yield ctx
    _lib.mqmqa_db_free(cdb)


def _tagname(cdb, t):
    if t >= 0:
        return _key(_ffi.string(_lib.mqmqa_db_phase_name(cdb, t)).decode())
    return _ffi.string(_lib.mqmqa_db_stoich_name(cdb, -t - 1)).decode()


def _c_eq(ctx, x_fe, x_si, suspend=None, refine=0, nliq=60):
    sm = _ffi.NULL
    if suspend:
        sm = _ffi.new("int[]", [1 if ctx["stnames"][j] in suspend else 0 for j in range(ctx["nst"])])
    po = _ffi.new("int[]", 8); am = _ffi.new("double[]", 8); gm = _ffi.new("double[]", 1)
    m = _lib.mqmqa_equilibrium_ternary_ex(ctx["cdb"], ctx["liq"], ctx["cefs"], 2, 1600.0,
                                          nliq, 60, ctx["iFE"], ctx["iSI"], x_fe, x_si,
                                          sm, refine, po, am, 8, gm)
    s = {_tagname(ctx["cdb"], po[k]) for k in range(m) if am[k] > 1e-3}
    return s, gm[0] / (2.0 + x_si)


def _pyc_gm_set(ctx, x_fe, x_si, phases):
    from pycalphad import equilibrium, variables as v
    x_mg = 1 - x_fe - x_si; O = x_fe + x_mg + 2 * x_si; tot = 1 + O
    eq = equilibrium(ctx["dbf"], ["FE", "MG", "SI", "O"], phases,
                     {v.T: 1600.0, v.P: 1e5, v.N: 1,
                      v.X("FE"): x_fe / tot, v.X("MG"): x_mg / tot, v.X("SI"): x_si / tot})
    s = {_key(str(p)) for p in np.ravel(eq.Phase.values.squeeze()) if str(p) and str(p) != "nan"}
    return s, float(eq.GM.values.squeeze())


@pytest.mark.skipif(not (DDIR / "build_combined_dat.py").exists(), reason="combined driver missing")
def test_stage4_phase_suspension_matches_pycalphad(engine):
    """Suspending WUSTITE at (0.20,0.30) flips OLIVINE+WUSTITE to the metastable
    LIQUID+OLIVINE, and the phase set matches pycalphad run without WUSTITE."""
    base, _ = _c_eq(engine, 0.20, 0.30)
    assert base == {"OLIVINE", "WUSTITE"}
    susp, _ = _c_eq(engine, 0.20, 0.30, suspend={"WUSTITE"})
    assert "WUSTITE" not in susp
    pset, _ = _pyc_gm_set(engine, 0.20, 0.30, [p for p in ALL if p != "WUSTITE"])
    assert susp == pset


@pytest.mark.skipif(not (DDIR / "build_combined_dat.py").exists(), reason="combined driver missing")
def test_stage5_refinement_reduces_liquid_error(engine):
    """On the liquid-bearing metastable state, more refinement passes do not increase
    the liquid-boundary Gibbs error against pycalphad (monotone improvement)."""
    _, pg = _pyc_gm_set(engine, 0.20, 0.30, [p for p in ALL if p != "WUSTITE"])
    errs = []
    for refine in (0, 2):
        _, g = _c_eq(engine, 0.20, 0.30, suspend={"WUSTITE"}, refine=refine)
        errs.append(abs(g - pg))
    assert errs[1] <= errs[0] + 1e-6
