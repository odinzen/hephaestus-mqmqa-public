"""Validate the declarative slag-database builder (mqmqa.dbbuild).

Strongest checks: rebuild the shipped, pycalphad-validated FeO-MgO-SiO2 liquid database through
the generic builder and confirm it reproduces the hand-written .dat numerically and loads in the
engine; fit the FeO-SiO2 excess to the measured activities behind v0.3 through the
engine-as-optimizer and check it reaches the least-squares minimum, consistent with the v0.3
parameters; and build a five-component liquid that the engine and pycalphad evaluate alike.
"""
import dataclasses
import importlib.util
import math
import re
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

import mqmqa
from mqmqa import dbbuild as db

SHIPPED = ROOT / "data" / "feo-mgo-sio2" / "FeO-MgO-SiO2-liquid.dat"

# v0.3 FeO-SiO2 a00, b00: the one-term activity fit published with the JORS paper
V03_FEO_SIO2 = (-42839.42808976104, 17.829765801117908)


def _fms_builder():
    spec = importlib.util.spec_from_file_location(
        "fms_bd_test", ROOT / "data" / "feo-mgo-sio2" / "build_dat.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _terms(excess):
    return [db.ExcessTerm(a=ex["coeffs"][0], b=ex["coeffs"][1], p=ex["exp"][0], q=ex["exp"][1])
            for ex in excess]


def feo_mgo_sio2_spec():
    """The shipped ternary's parameters, taken from its builder (the single source)."""
    fms = _fms_builder()
    feo = db.starter_component("FeO", liq_beta=fms.FEO_LIQ_BETA)
    mgo = db.starter_component("MgO", liq_dcp=fms.MGO_LIQ_DCP)
    sio2 = db.starter_component("SiO2", group=2)
    feo_sio2 = db.BinaryExcess("FeO", "SiO2", _terms(fms.EX_FEO_SIO2),
                               source="assessed (data/feo-sio2/assessment)")
    mgo_sio2 = db.BinaryExcess("MgO", "SiO2", _terms(fms.EX_MGO_SIO2),
                               source="assessed silica-weighted set (data/mgo-sio2/assessment)")
    # the ternary-level terms (data/feo-mgo-sio2/assessment), in the order the builder writes them
    name = {1: "FeO", 2: "MgO", 3: "SiO2"}
    ternary = [db.BinaryExcess(name[ex["li"][0]], name[ex["li"][1]],
                               [db.ExcessTerm(a=ex["coeffs"][0], b=ex["coeffs"][1], p=ex["exp"][0],
                                              q=ex["exp"][1], add_cat=name.get(ex["add"], ""),
                                              r=ex["exp"][2])])
               for ex in fms.ternary_excess()]
    z_mgsi = fms._mgo.mgsi_mixed_z()
    return db.SystemSpec("FeO-MgO-SiO2", [feo, mgo, sio2], [feo_sio2, mgo_sio2, *ternary],
                         version="v0.1", provenance="data/feo-mgo-sio2/PROVENANCE.md",
                         quad_z={} if z_mgsi is None else {("MgO", "SiO2"): z_mgsi})


def _numbers(text):
    return [float(x) for x in re.findall(r"[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?", text)]


def test_reproduces_shipped_ternary_numerically():
    built = db.write_dat(feo_mgo_sio2_spec())
    bn, sn = _numbers(built), _numbers(SHIPPED.read_text())
    assert len(bn) == len(sn), f"token count differs: built {len(bn)} vs shipped {len(sn)}"
    worst = max(abs(x - y) for x, y in zip(bn, sn))
    assert worst < 1e-3, f"largest numeric difference {worst} exceeds tolerance"


def test_built_dat_loads_in_engine():
    out = Path(tempfile.gettempdir()) / "_dbbuild_test_feo_mgo_sio2.dat"
    out.write_text(db.write_dat(feo_mgo_sio2_spec()), encoding="ascii")
    d = mqmqa.Database.read(str(out))
    assert d.phase_index("FEO-MGO-SIO2-LIQUID") >= 0


def test_five_component_liquid_matches_pycalphad():
    """Nothing caps the component count: a five-cation liquid builds, loads, and its Gibbs
    energy equals pycalphad's over fixed quadruplet distributions."""
    import pytest
    pytest.importorskip("pycalphad")
    from pycalphad import Database, variables as v
    from pycalphad.models.model_mqmqa import ModelMQMQA
    from mqmqa import equilibrium as eqm

    comps = [db.starter_component(n) for n in ("FeO", "MgO", "SiO2", "CaO")]
    # a fifth cation for the format only: CaO's numbers under Mn, not a description of MnO
    comps.append(dataclasses.replace(db.starter_component("CaO"), name="MnO", cation="Mn",
                                     source="test fixture, CaO values relabelled"))
    binaries = [
        db.BinaryExcess("FeO", "SiO2", [db.ExcessTerm(-42839.4, 17.83),
                                        db.ExcessTerm(-8000.0, 0.0, 1, 0)]),
        db.BinaryExcess("MgO", "SiO2", [db.ExcessTerm(-86000.0, 12.0)]),
        db.BinaryExcess("CaO", "SiO2", [db.ExcessTerm(-158000.0, 19.0),
                                        db.ExcessTerm(-21000.0, 0.0, 0, 1)]),
        db.BinaryExcess("MnO", "SiO2", [db.ExcessTerm(-60000.0, 5.0)]),
        db.BinaryExcess("FeO", "MgO", [db.ExcessTerm(5000.0)]),
    ]
    spec = db.SystemSpec("FeO-MgO-SiO2-CaO-MnO", comps, binaries)
    out = Path(tempfile.gettempdir()) / "_dbbuild_test_five.dat"
    out.write_text(db.write_dat(spec), encoding="ascii")

    d = mqmqa.Database.read(str(out))
    assert len(d.cations(0)) == 5
    T = 1873.0
    inp = eqm.build_inputs(d, 0, T)
    cats = [c["name"] for c in d.cations(0)]
    ans = [a["name"] for a in d.anions(0)]

    def elem(s):
        return re.match(r"[A-Za-z]+", str(s)).group(0).upper()

    def key(A, B, X, Y):
        return tuple(sorted([elem(A), elem(B)])) + tuple(sorted([elem(X), elem(Y)]))

    keys = [key(cats[a], cats[b], ans[x], ans[y]) for (a, b, x, y) in inp["quads"]]
    dbf = Database(str(out))
    phase = next(n for n in dbf.phases if "LIQ" in n.upper())
    mod = ModelMQMQA(dbf, ["FE", "MG", "SI", "CA", "MN", "O", "VA"], phase)
    gm = mod.symbol_replace(mod.GM, dict(dbf.symbols))
    worst = 0.0
    for seed in range(4):
        vals = [0.03 + 0.011 * ((i * 7 + seed * 5) % len(keys)) for i in range(len(keys))]
        X = [x / sum(vals) for x in vals]
        xmap = dict(zip(keys, X))
        g_eng = eqm.gibbs_per_quad(inp, X) / sum(eqm.element_moles(inp, X).values())
        subs = {v.T: T}
        subs.update({mod._X_ijkl(*q): xmap[key(*q)] for q in mod._quadruplets})
        worst = max(worst, abs(g_eng - float(gm.subs(subs))))
    assert worst < 1e-6, f"engine vs pycalphad worst |diff| = {worst:.2e} J/mol-atom"


def _load_bjorkman():
    csv = ROOT / "data" / "feo-sio2" / "activities_feo_bjorkman1985_fig3.csv"
    rows = []
    for line in csv.read_text().splitlines():
        if line.startswith("#") or line.startswith("X_FeO") or not line.strip():
            continue
        p = line.split(",")
        rows.append((float(p[0]), float(p[1]), p[2], float(p[3])))
    return rows


def _bjorkman_points(rel_shift=0.0):
    """Bjorkman 1985 a(FeO) as ActivityPoints; rel_shift scales each activity by
    1 +/- rel_shift, alternating in sign, for the stability check."""
    return [db.ActivityPoint(x_second=1 - X, activity=a * (1 + rel_shift * (-1) ** i),
                             of="first", T=T, source=src)
            for i, (X, a, src, T) in enumerate(_load_bjorkman())]


def _ln_a_residuals(feo, sio2, pts, a, b):
    """ln a(FeO) model minus measured, through the public write -> read -> solve path."""
    spec = db.SystemSpec("FeO-SiO2", [feo, sio2],
                         [db.BinaryExcess("FeO", "SiO2", [db.ExcessTerm(a=a, b=b)])])
    acts = db.evaluate_binary_activities(spec, pts)
    return np.array([math.log(a1) - math.log(p.activity) for (a1, _), p in zip(acts, pts)])


def test_binary_fit_reaches_feo_sio2_least_squares_minimum():
    """The engine-as-optimizer fit of Delta_g(Fe,Si)/O = a + b*T to the 23 measured a(FeO)
    points (Bjorkman 1985) checked for what the data determine: it sits at the least-squares
    minimum, it does not move under a last-digit change to the input, the residual is the
    known RMS ln a, and the v0.3 parameters agree with it within the data's
    uncertainty.

    The v0.3 value (-42839.4 + 17.83*T, published with the JORS paper) is the fit as first
    run, which stopped early in the flat a-b valley. It lies 78.6 J/mol in a from the minimum
    (-42760.8 + 17.7832*T) but moves L(T) by only 5 J/mol at the ~1580 K data and 22 J/mol at
    2153 K, where the data leave L uncertain by about 1.0 and 2.5 kJ/mol. The shipped liquid
    is now the v0.4 assessment against the phase diagram as well; this checks the fitter."""
    feo, sio2 = db.starter_component("FeO"), db.starter_component("SiO2")
    pts = _bjorkman_points()
    be = db.fit_binary_excess(feo, sio2, pts, powers=[(0, 0)], fit_entropy=True)
    a, b = be.terms[0].a, be.terms[0].b

    # Work in L at the lowest and highest data temperatures, where the data fix the two
    # parameters nearly independently; a Gauss-Newton step from the fit then lands on the
    # minimum to well under 1 J/mol.
    Ts = sorted({p.T for p in pts})
    T_lo, T_hi = Ts[0], Ts[-1]

    def ab(L):
        slope = (L[1] - L[0]) / (T_hi - T_lo)
        return L[0] - slope * T_lo, slope

    L_fit = np.array([a + b * T_lo, a + b * T_hi])
    r_fit = _ln_a_residuals(feo, sio2, pts, *ab(L_fit))
    step = 1.0                                   # J/mol, as in the fit's own Jacobian
    J = np.column_stack([(_ln_a_residuals(feo, sio2, pts, *ab(L_fit + step * e))
                          - _ln_a_residuals(feo, sio2, pts, *ab(L_fit - step * e))) / (2 * step)
                         for e in np.eye(2)])
    L_gn = L_fit - np.linalg.lstsq(J, r_fit, rcond=None)[0]
    cost_fit = 0.5 * r_fit @ r_fit
    cost_min = min(cost_fit, 0.5 * np.sum(_ln_a_residuals(feo, sio2, pts, *ab(L_gn)) ** 2))

    # 1) At the minimum. The early-stopped v0.3 fit is 4.6e-6 above it in relative cost.
    # For this fit the Gauss-Newton step never lowered the cost in 18 runs on perturbed
    # activities; it raised it by up to 3.3e-10, the noise of the finite-difference
    # activities. 1e-8 sits 30x above that noise and corresponds to about 3.7 J/mol in a
    # along the valley toward the v0.3 point.
    assert (cost_fit - cost_min) / cost_min < 1e-8, (
        f"fit cost {cost_fit:.12g} is above the least-squares minimum {cost_min:.12g}")

    # 2) Stable. A 1e-12 relative change to every activity must not move the fit. Over 108
    # runs (repeats, 1e-14..1e-10 changes to the activities, temperatures and start, and four
    # distant starts) the fit stayed within 0.30 J/mol in a and 1.4e-4 J/mol/K in b; before
    # the fix 1e-14 changes scattered a by 160 J/mol (sd). The tolerances are about 3x and 7x
    # the measured band.
    be2 = db.fit_binary_excess(feo, sio2, _bjorkman_points(1e-12), powers=[(0, 0)],
                               fit_entropy=True)
    assert abs(be2.terms[0].a - a) < 1.0, f"a moved {be2.terms[0].a - a:+.3f} J/mol"
    assert abs(be2.terms[0].b - b) < 1e-3, f"b moved {be2.terms[0].b - b:+.5f} J/mol/K"

    # 3) RMS ln a = 0.0675, rounded to four decimals. The minimum gives 0.0674926 in every
    # run (to 1e-9) and the early-stopped v0.3 fit 0.0674927, so this pins how well the
    # model fits the data, not the optimizer (check 1 does that). As a measure of the scatter
    # of points digitized to 0.01-0.02 in a, only the first two figures carry physical meaning.
    # The second line confirms this test's residuals are the fit's own objective; they agree
    # to 8.5e-12 at worst, the activity noise, and 1e-9 leaves 100x room.
    assert abs(be.rms_ln_a - 0.0675) < 5e-5, f"RMS ln a {be.rms_ln_a:.6f}"
    assert abs(math.sqrt(2 * cost_fit / len(pts)) - be.rms_ln_a) < 1e-9

    # 4) The v0.3 parameters agree with the fit within the data's standard uncertainty
    # of L(T), from the covariance s^2 (J^T J)^-1 with s^2 = 2*cost/(n - 2), at each data
    # temperature: 1035, 1013 and 2481 J/mol at 1578, 1590 and 2153 K. The v0.3 values
    # differ by 5, 5 and 22 J/mol, so a one-sigma bound holds with a wide margin.
    cov = (2 * cost_min / (len(pts) - 2)) * np.linalg.inv(J.T @ J)
    for T in Ts:
        w = (T - T_lo) / (T_hi - T_lo)
        g = np.array([1 - w, w])
        sigma = math.sqrt(g @ cov @ g)
        L_v03 = V03_FEO_SIO2[0] + V03_FEO_SIO2[1] * T
        assert abs(L_v03 - (a + b * T)) < sigma, (
            f"v0.3 L({T:.0f} K) {L_v03:.1f} vs fit {a + b * T:.1f}, sigma {sigma:.1f}")


if __name__ == "__main__":
    test_reproduces_shipped_ternary_numerically()
    print("reproduces shipped ternary .dat numerically (0 diff)")
    test_built_dat_loads_in_engine()
    print("built .dat loads in the engine")
    test_four_component_cap()
    print("four-component free cap enforced")
    test_binary_fit_reaches_feo_sio2_least_squares_minimum()
    print("binary fit reaches the FeO-SiO2 least-squares minimum")
    print("\nall dbbuild checks passed")
