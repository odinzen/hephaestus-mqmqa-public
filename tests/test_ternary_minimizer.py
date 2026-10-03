"""Validate the 2-D ternary global minimizer (mqmqa.ternary) for FeO-MgO-SiO2.

The minimizer samples each phase's Gibbs energy over composition and takes the lower convex
hull; each lower facet is an equilibrium tie-triangle/edge. Every phase's Gibbs energy is
validated elsewhere (liquid vs pycalphad to ~1e-10; the CEF solids in their own tests), so
this checks the HULL logic:
  - the liquid<->olivine tie-line on the x_Si=1/3 section matches the model's equilibrium
    tie-line, computed by pycalphad on the committed combined .dat;
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


def _pycalphad_olivine_tieline(T, x_fe, x_si):
    """Join X_Fe = Fe/(Fe+Mg) of each phase at equilibrium, from pycalphad on the committed
    combined .dat, which holds the same liquid and the same olivine (identical CEF
    parameters) the 2-D minimizer pools."""
    from pycalphad import Database, equilibrium, variables as v
    dbf = Database(str(ROOT / "data" / "feo-mgo-sio2" / "FeO-MgO-SiO2-combined.dat"))
    x_mg = 1.0 - x_fe - x_si
    tot = 1.0 + x_fe + x_mg + 2.0 * x_si          # cations plus oxygen
    eq = equilibrium(dbf, ["FE", "MG", "SI", "O"],
                     ["FEO-MGO-SIO2-LIQUID", "OLIVINE", "ORTHOPYROXENE", "CRISTOBALITE",
                      "MAGNESIOWUSTITE"],
                     {v.T: T, v.P: 1e5, v.N: 1,
                      v.X("FE"): x_fe / tot, v.X("MG"): x_mg / tot, v.X("SI"): x_si / tot})
    names = np.ravel(eq.Phase.values.squeeze())
    X = eq.X.values.squeeze().reshape(len(names), -1)
    comp = list(eq.component.values)
    out = {}
    for name, row in zip(names, X):
        if str(name) and str(name) != "nan":
            d = dict(zip(comp, row))
            out[str(name)] = d["FE"] / (d["FE"] + d["MG"])
    return out


@pytest.mark.skipif(not TD.exists(), reason="ternary diagram driver missing")
def test_olivine_tieline_matches_model_equilibrium():
    pytest.importorskip("pycalphad")
    from mqmqa import ternary as tern
    td = _load("ternary_diagram", TD)

    T, x_fe, x_si = 1900.0, 0.20, 1.0 / 3.0
    pts, facets = td.build(T, nsamp=4000)
    asm = tern.assemblage(pts, facets, x_fe, x_si)
    agg = defaultdict(lambda: [0.0, 0.0])
    for ph, amt, xf, xs in asm:
        agg[ph][0] += amt
        agg[ph][1] += amt * xf
    assert "LIQUID" in agg and "OLIVINE" in agg, f"expected liquid+olivine, got {list(agg)}"
    # convert cation x_Fe on x_Si=1/3 to join X_Fe = Fe/(Fe+Mg)
    join = lambda xfe: xfe / (2.0 / 3.0)
    sol2d = join(agg["OLIVINE"][1] / agg["OLIVINE"][0])
    liq2d = join(agg["LIQUID"][1] / agg["LIQUID"][0])

    # The model's own tie-line: solidus 0.0827, liquidus 0.4171, the same at any bulk on the
    # tie-line. The 2-D minimizer reads the solidus off an 81-point olivine grid (spacing
    # 0.0125) and the liquid end off its liquid samples. On random quadruplet draws alone
    # the liquidus ranged 0.337 to 0.451 over seeds and densities; the exact lattice minima
    # liquid_points now adds bound it by the lattice spacing.
    ref = _pycalphad_olivine_tieline(T, x_fe, x_si)
    assert set(ref) == {"FEO-MGO-SIO2-LIQUID", "OLIVINE"}, ref
    sol_ref, liq_ref = ref["OLIVINE"], ref["FEO-MGO-SIO2-LIQUID"]
    assert abs(sol2d - sol_ref) < 0.03, f"solidus 2D {sol2d:.3f} vs model {sol_ref:.4f}"
    assert abs(liq2d - liq_ref) < 0.04, f"liquidus 2D {liq2d:.3f} vs model {liq_ref:.4f}"


@pytest.mark.skipif(not TD.exists(), reason="ternary diagram driver missing")
def test_three_phase_triangle_and_opx_appear():
    from mqmqa import ternary as tern
    td = _load("ternary_diagram2", TD)
    T = 1800.0
    pts, facets = td.build(T, nsamp=4000)

    # a low-silica bulk between olivine and magnesiowustite gives liquid + olivine +
    # magnesiowustite (3 phases)
    asm = tern.assemblage(pts, facets, 0.40, 0.20)
    phases = {ph for ph, amt, xf, xs in asm if amt > 1e-3}
    assert phases == {"LIQUID", "OLIVINE", "MAGNESIOWUSTITE"}, phases
    assert abs(sum(amt for _, amt, _, _ in asm) - 1.0) < 1e-6  # lever rule

    # a Mg-rich composition near the enstatite point (below its ~1830 K peritectic) brings
    # in orthopyroxene; pycalphad on the same file gives liquid + orthopyroxene here too
    asm2 = tern.assemblage(pts, facets, 0.03, 0.52)
    phases2 = {ph for ph, amt, xf, xs in asm2 if amt > 1e-3}
    assert "ORTHOPYROXENE" in phases2, phases2
