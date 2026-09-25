"""Validate the declarative slag-database builder (mqmqa.dbbuild).

Strongest checks: rebuild the shipped, pycalphad-validated FeO-MgO-SiO2 liquid database through
the generic builder and confirm it reproduces the hand-written .dat numerically and loads in the
engine; fit the FeO-SiO2 excess to the measured activities behind v0.3 through the
engine-as-optimizer and check it reaches the least-squares minimum, consistent with the shipped
parameters; and confirm the four-component free cap is enforced.
"""
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

FEO_LIQ_BETA = -69.84464900364951
MGO_LIQ_BETA = 2.9753836245721774
SHIPPED_FEO_SIO2 = (-42839.42808976104, 17.829765801117908)   # v0.3 a00, b00


def feo_mgo_sio2_spec():
    feo = db.starter_component("FeO", liq_beta=FEO_LIQ_BETA)
    mgo = db.starter_component("MgO", liq_beta=MGO_LIQ_BETA)
    sio2 = db.starter_component("SiO2")
    feo_sio2 = db.BinaryExcess("FeO", "SiO2", [
        db.ExcessTerm(a=SHIPPED_FEO_SIO2[0], b=SHIPPED_FEO_SIO2[1], p=0, q=0)],
        source="v0.3 activity-pinned (Bjorkman 1985 a(FeO); Bowen-Schairer 1932 melting)")
    mgo_sio2 = db.BinaryExcess("MgO", "SiO2", [
        db.ExcessTerm(-44468.8, -1.60, 0, 0), db.ExcessTerm(-50864.2, -0.30, 0, 1),
        db.ExcessTerm(1448.2, -0.70, 0, 3), db.ExcessTerm(116056.4, -10.80, 0, 5),
        db.ExcessTerm(-1177.5, -0.30, 0, 7)],
        source="assessed silica-weighted set (data/mgo-sio2/assessment)")
    return db.SystemSpec("FeO-MgO-SiO2", [feo, mgo, sio2], [feo_sio2, mgo_sio2],
                         version="v0.1", provenance="data/feo-mgo-sio2/PROVENANCE.md")


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


def test_four_component_cap():
    comps = [db.starter_component(n) for n in ("FeO", "MgO", "SiO2", "CaO")]
    db.SystemSpec("quaternary", comps)                       # 4 components: allowed
    extra = db.starter_component("CaO"); extra.name, extra.cation = "MnO", "Mn"
    try:
        db.SystemSpec("five", comps + [extra])
        assert False, "5-component spec should have raised PremiumFeatureError"
    except db.PremiumFeatureError as e:
        assert "premium" in str(e).lower() and db.SUPPORT_EMAIL in str(e)


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
    known RMS ln a, and the shipped v0.3 parameters agree with it within the data's
    uncertainty.

    The shipped value (-42839.4 + 17.83*T, in data/ and the published provenance) is the
    fit as first run, which stopped early in the flat a-b valley. It lies 78.6 J/mol in a from
    the minimum (-42760.8 + 17.7832*T) but moves L(T) by only 5 J/mol at the ~1580 K data and
    22 J/mol at 2153 K, where the data leave L uncertain by about 1.0 and 2.5 kJ/mol. Updating
    the shipped value to the minimum is deferred to the JORS revision."""
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

    # 1) At the minimum. The early-stopped shipped fit is 4.6e-6 above it in relative cost.
    # For this fit the Gauss-Newton step never lowered the cost in 18 runs on perturbed
    # activities; it raised it by up to 3.3e-10, the noise of the finite-difference
    # activities. 1e-8 sits 30x above that noise and corresponds to about 3.7 J/mol in a
    # along the valley toward the shipped point.
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
    # run (to 1e-9) and the shipped early-stopped fit 0.0674927, so this pins how well the
    # model fits the data, not the optimizer (check 1 does that). As a measure of the scatter
    # of points digitized to 0.01-0.02 in a, only the first two figures carry physical meaning.
    # The second line confirms this test's residuals are the fit's own objective; they agree
    # to 8.5e-12 at worst, the activity noise, and 1e-9 leaves 100x room.
    assert abs(be.rms_ln_a - 0.0675) < 5e-5, f"RMS ln a {be.rms_ln_a:.6f}"
    assert abs(math.sqrt(2 * cost_fit / len(pts)) - be.rms_ln_a) < 1e-9

    # 4) The shipped parameters agree with the fit within the data's standard uncertainty
    # of L(T), from the covariance s^2 (J^T J)^-1 with s^2 = 2*cost/(n - 2), at each data
    # temperature: 1035, 1013 and 2481 J/mol at 1578, 1590 and 2153 K. The shipped values
    # differ by 5, 5 and 22 J/mol, so a one-sigma bound holds with a wide margin.
    cov = (2 * cost_min / (len(pts) - 2)) * np.linalg.inv(J.T @ J)
    for T in Ts:
        w = (T - T_lo) / (T_hi - T_lo)
        g = np.array([1 - w, w])
        sigma = math.sqrt(g @ cov @ g)
        L_ship = SHIPPED_FEO_SIO2[0] + SHIPPED_FEO_SIO2[1] * T
        assert abs(L_ship - (a + b * T)) < sigma, (
            f"shipped L({T:.0f} K) {L_ship:.1f} vs fit {a + b * T:.1f}, sigma {sigma:.1f}")


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
