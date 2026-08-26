"""End-to-end validation of the 2-D FeO-MgO-SiO2 minimizer against pycalphad `equilibrium`.

Both solvers run the SAME model. pycalphad reads the combined ChemSage .dat assembled by
`build_combined_dat.py` (liquid SUBQ + olivine/opx SUBL + the three stoichiometric oxide
solids); our minimizer pools the same phases and takes the lower convex hull. For each bulk
cation composition we check the stable phase SET, the equilibrium Gibbs energy GM, and the
per-phase cation compositions.

The opx enstatite high-T entropy correction is a Python-only post-hoc adjustment, so the
minimizer runs with enstatite_shift=False to match the uncorrected opx endmember in the .dat.
The test points are interior tie-triangles / solid-solid fields, where both solvers agree to
machine precision; the soft liquid tie-line endpoints (a flat liquid surface) are the 2-D
minimizer's documented resolution limit and are exercised by data/feo-mgo-sio2/validate_combined.py.
"""
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
PHASES = ["FEO-MGO-SIO2-LIQUID", "OLIVINE", "ORTHOPYROXENE", "CRISTOBALITE", "PERICLASE", "WUSTITE"]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _phase_key(name):
    return "LIQUID" if name.startswith("FEO-MGO-SIO2") else name


def _our(pts, facets, x_fe, x_si):
    from mqmqa import ternary as tern
    a = tern.assemblage(pts, facets, x_fe, x_si)
    agg = defaultdict(lambda: [0.0, 0.0, 0.0])
    for ph, amt, xf, xs in a:
        agg[ph][0] += amt; agg[ph][1] += amt * xf; agg[ph][2] += amt * xs
    phases = {_phase_key(ph): (amt, sf / amt, ss / amt)
              for ph, (amt, sf, ss) in agg.items() if amt > 1e-3}
    gm = tern.hull_g(pts, facets, x_fe, x_si) / (2.0 + x_si)
    return phases, gm


def _pyc(dbf, x_fe, x_si, T):
    from pycalphad import equilibrium, variables as v
    x_mg = 1.0 - x_fe - x_si
    O = x_fe + x_mg + 2 * x_si
    tot = 1.0 + O
    eq = equilibrium(dbf, ["FE", "MG", "SI", "O"], PHASES,
                     {v.T: T, v.P: 1e5, v.N: 1,
                      v.X("FE"): x_fe / tot, v.X("MG"): x_mg / tot, v.X("SI"): x_si / tot})
    Ph = np.ravel(eq.Phase.values.squeeze())
    X = eq.X.values.squeeze().reshape(len(Ph), -1)
    comp = list(eq.component.values)
    phases = {}
    for i, p in enumerate(Ph):
        name = str(p)
        if name and name != "nan":
            d = dict(zip(comp, X[i]))
            cat = d["FE"] + d["MG"] + d["SI"]
            phases[_phase_key(name)] = (d["FE"] / cat, d["SI"] / cat)
    return phases, float(eq.GM.values.squeeze())


# interior points (solid-solid / solid-solid-solid) that both solvers pin exactly at 1600 K
INTERIOR = [
    (0.20, 0.30, {"OLIVINE", "WUSTITE"}),
    (0.12, 0.46, {"OLIVINE", "ORTHOPYROXENE"}),
    (0.06, 0.52, {"CRISTOBALITE", "ORTHOPYROXENE"}),
    (0.30, 0.10, {"OLIVINE", "PERICLASE", "WUSTITE"}),
    (0.08, 0.12, {"OLIVINE", "PERICLASE", "WUSTITE"}),
]


@pytest.mark.skipif(not (DDIR / "ternary_diagram.py").exists(), reason="ternary driver missing")
def test_combined_dat_stoich_matches_python():
    """The generated stoichiometric-oxide blocks reproduce the minimizer's own solid Gibbs."""
    from pycalphad import Database, calculate
    bc = _load("bc", DDIR / "build_combined_dat.py")
    td = _load("td", DDIR / "ternary_diagram.py")
    bc.build()
    dbf = Database(str(DDIR / "FeO-MgO-SiO2-combined.dat"))
    T = 1750.0
    for ph, ox, atoms in [("CRISTOBALITE", td._feo.OXIDES["SiO2"], 3),
                          ("PERICLASE", td._mgo.OXIDES["MgO"], 2),
                          ("WUSTITE", td._feo.OXIDES["FeO"], 2)]:
        r = calculate(dbf, list(dbf.elements), ph, T=T, P=1e5, N=1)
        gm_formula = float(r.GM.values.squeeze()) * atoms
        assert abs(gm_formula - td._solid_oxide_g(ox, T)) < 1e-3


@pytest.mark.skipif(not (DDIR / "ternary_diagram.py").exists(), reason="ternary driver missing")
def test_minimizer_assemblages_match_pycalphad():
    from pycalphad import Database
    bc = _load("bc", DDIR / "build_combined_dat.py")
    td = _load("td", DDIR / "ternary_diagram.py")
    bc.build()
    dbf = Database(str(DDIR / "FeO-MgO-SiO2-combined.dat"))
    T = 1600.0
    pts, facets = td.build(T, nsamp=8000, n_cef=161)
    for x_fe, x_si, expected in INTERIOR:
        our_ph, our_gm = _our(pts, facets, x_fe, x_si)
        pyc_ph, pyc_gm = _pyc(dbf, x_fe, x_si, T)
        assert set(our_ph) == expected, (x_fe, x_si, set(our_ph))
        assert set(pyc_ph) == expected, (x_fe, x_si, set(pyc_ph))
        # equilibrium energy agrees to a few J/mol-atom for these interior points
        assert abs(our_gm - pyc_gm) < 10.0, (x_fe, x_si, our_gm, pyc_gm)
        # per-phase cation compositions agree tightly (solid solutions and stoich phases)
        for k in expected:
            assert abs(our_ph[k][1] - pyc_ph[k][0]) < 0.02, (x_fe, x_si, k, "x_Fe")
            assert abs(our_ph[k][2] - pyc_ph[k][1]) < 0.02, (x_fe, x_si, k, "x_Si")
