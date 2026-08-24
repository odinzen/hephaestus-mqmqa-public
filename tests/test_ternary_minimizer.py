"""Validate the 2-D ternary global minimizer (mqmqa.ternary) for FeO-MgO-SiO2.

The minimizer samples each phase's Gibbs energy over composition and takes the lower convex
hull; each lower facet is an equilibrium tie-triangle/edge. Every phase's Gibbs energy is
validated elsewhere (liquid vs pycalphad to ~1e-10; the CEF solids in their own tests), so
this checks the HULL logic:
  - the liquid<->olivine tie-line on the x_Si=1/3 section matches the independently validated
    1-D olivine loop (data/feo-mgo-sio2/olivine_join.py);
  - a genuine three-phase tie-triangle is found with lever-rule-consistent amounts;
  - orthopyroxene appears as a stable phase in the silica-rich field.
"""
import importlib.util
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

TD = ROOT / "data" / "feo-mgo-sio2" / "ternary_diagram.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.mark.skipif(not TD.exists(), reason="ternary diagram driver missing")
def test_olivine_tieline_matches_1d_loop():
    from mqmqa import ternary as tern
    import mqmqa
    td = _load("ternary_diagram", TD)
    oj = _load("olivine_join", ROOT / "data" / "feo-mgo-sio2" / "olivine_join.py")

    T = 1900.0
    pts, facets = td.build(T, nsamp=4000)
    asm = tern.assemblage(pts, facets, 0.20, 1.0 / 3.0)
    agg = defaultdict(lambda: [0.0, 0.0])
    for ph, amt, xf, xs in asm:
        agg[ph][0] += amt
        agg[ph][1] += amt * xf
    assert "LIQUID" in agg and "OLIVINE" in agg, f"expected liquid+olivine, got {list(agg)}"
    # convert cation x_Fe on x_Si=1/3 to join X_Fe = Fe/(Fe+Mg)
    join = lambda xfe: xfe / (2.0 / 3.0)
    sol2d = join(agg["OLIVINE"][1] / agg["OLIVINE"][0])
    liq2d = join(agg["LIQUID"][1] / agg["LIQUID"][0])

    cdb = mqmqa.Database.read(str(ROOT / "data" / "olivine" / "Olivine-CEF.dat"))
    pol = cdb.phase_index("OLIVINE")
    ldb = mqmqa.Database.read(str(ROOT / "data" / "feo-mgo-sio2" / "FeO-MgO-SiO2-liquid.dat"))
    lp = ldb.phase_index("FEO-MGO-SIO2-LIQUID")
    xs = np.linspace(1e-3, 1 - 1e-3, 41)
    g_ol = np.array([oj.olivine_G(cdb, pol, float(x), T) for x in xs])
    g_liq = oj._liquid_curve(ldb, lp, T, xs)
    ok = np.isfinite(g_liq)
    sol1d, liq1d = oj._fine_tie_line(xs[ok], g_ol[ok], g_liq[ok])

    assert abs(sol2d - sol1d) < 0.03, f"solidus 2D {sol2d:.3f} vs 1D {sol1d:.3f}"
    assert abs(liq2d - liq1d) < 0.04, f"liquidus 2D {liq2d:.3f} vs 1D {liq1d:.3f}"


@pytest.mark.skipif(not TD.exists(), reason="ternary diagram driver missing")
def test_three_phase_triangle_and_opx_appear():
    from mqmqa import ternary as tern
    td = _load("ternary_diagram2", TD)
    T = 1800.0
    pts, facets = td.build(T, nsamp=4000)

    # a MgO-rich low-silica bulk should give liquid + olivine + periclase (3 phases)
    asm = tern.assemblage(pts, facets, 0.10, 0.10)
    phases = {ph for ph, amt, xf, xs in asm if amt > 1e-3}
    assert phases == {"LIQUID", "OLIVINE", "PERICLASE"}, phases
    assert abs(sum(amt for _, amt, _, _ in asm) - 1.0) < 1e-6  # lever rule

    # a Mg-rich composition near the enstatite point (below its ~1830 K peritectic) brings
    # in orthopyroxene
    asm2 = tern.assemblage(pts, facets, 0.06, 0.50)
    phases2 = {ph for ph, amt, xf, xs in asm2 if amt > 1e-3}
    assert "ORTHOPYROXENE" in phases2, phases2
