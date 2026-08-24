"""v0.3 fit: FeO-SiO2 liquid excess pinned on MEASURED iron-saturated activities.

v0.2 fixed the excess depth by scaling the MgO-SiO2 liquid (no FeO-SiO2 activity data
were digitized then) and carried an unphysical b00 = +78 J/mol/K that compensated an
ideal-liquid melting offset. v0.3 replaces that with the measured a(FeO) curve.

Two independent, decoupled steps:

  1. EXCESS from activities. The measured iron-saturated a(FeO) vs X(FeO)
     (Bjorkman 1985 Fig 3, replotting Bodsworth 1959 at 1578 K + Schuhmann-Ensio 1951
     at 1590 K + Distin 1971 at 2153 K; digitized symbols only, in
     activities_feo_bjorkman1985_fig3.csv) fix the cation-mixing excess
        Delta_g(Fe,Si)/O = a00 + b00*T   (symmetric; a10 skew added only if it earns it)
     The two temperatures (~1580 K and 2153 K) give a 573 K lever that separates the
     enthalpy a00 from a physical excess entropy b00 - retiring v0.2's +78.

  2. FeO(l) BELOW-MELTING CALIBRATION from the fayalite liquidus. The activity-matched
     liquid is ~7 kJ/mol-oxide too stable to melt fayalite at its measured 1478 K
     (Bowen & Schairer 1932) with the JANAF-fusion FeO(l) endmember extrapolated below
     its own 1650 K melting point. Bjorkman's assessment fixes dfG(FeO,l) below ~1644 K
     from the iron-silicate liquidus rather than from that extrapolation; we do the same
     with a single below-1650 K correction dG = beta*(T - 1650) on the FeO liquid
     endmember (build_dat feo_liq_beta). Crucially this correction is EXACTLY orthogonal
     to the activities: it shifts the pure-FeO reference and the FeO chemical potential
     by the same amount, so a(FeO) and a(SiO2) are unchanged - it only sets the absolute
     liquid stability / melting. So beta is fit to melting AFTER the excess is fixed,
     with no feedback onto step 1. The fayalite solid dHf_ox stays at its measured
     -25.7 kJ (from the oxides); the recalibrated block is the uncertain supercooled
     FeO liquid, not the calorimetric solid.
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq, least_squares

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "python"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# load the FeO-SiO2 build_dat by explicit path (several data/*/build_dat.py collide)
bd = _load("build_dat_feosio2", HERE / "build_dat.py")
import mqmqa
from mqmqa import equilibrium as eq
import _activity as act
import phase_diagram as pdg

R = 8.3145
COMPONENTS = pdg.COMPONENTS
T_FAYALITE_CONGRUENT = 1478.0
X_FAYALITE = 1.0 / 3.0
DATA_CSV = HERE / "activities_feo_bjorkman1985_fig3.csv"


def load_activities():
    """(X_FeO, a_FeO, source, T) rows of the digitized measured points."""
    rows = []
    for line in DATA_CSV.read_text().splitlines():
        if line.startswith("#") or line.startswith("X_FeO") or not line.strip():
            continue
        p = line.split(",")
        rows.append((float(p[0]), float(p[1]), p[2], float(p[3])))
    return rows


def build_db(excess_coeffs, beta=0.0):
    """Assemble a database with the given excess coefficients and FeO beta."""
    excess = [dict(code="Q", li=[1, 2, 3, 3], exp=[0, 0, 0, 0], coeffs=list(excess_coeffs[0])),
              dict(code="Q", li=[1, 2, 3, 3], exp=[1, 0, 0, 0], coeffs=list(excess_coeffs[1]))]
    path = HERE / "_v03_scaffold.dat"
    path.write_text(bd.build(excess, feo_liq_beta=beta), encoding="ascii")
    db = mqmqa.Database.read(str(path))
    return db, db.phase_index("FEO-SIO2-LIQUID")


def _excess_coeffs(a00, b00, a10):
    return ([a00, b00, 0, 0, 0, 0], [a10, 0, 0, 0, 0, 0])


def model_afeo(db, p, X_feo, T):
    inp = eq.build_inputs(db, p, T, components=COMPONENTS)
    a_feo, _ = act.activities(inp, 1.0 - X_feo, T)
    return a_feo


def congruent_T(db, p, x=X_FAYALITE, lo=1000.0, hi=2000.0):
    def f(T):
        inp = eq.build_inputs(db, p, T, components=COMPONENTS)
        gs, _ = pdg.solid_gibbs_per_formula_unit("Fa(fayalite)", T)
        return pdg.liquid_gibbs_per_formula_unit(inp, x, T) - gs
    if f(lo) * f(hi) > 0:
        return None
    return brentq(f, lo, hi, xtol=1e-4)


def dgmix(db, p, x, T):
    inp = eq.build_inputs(db, p, T, components=COMPONENTS)
    return act.delta_g_mix(inp, x)


def dh_mix(db, p, x, T=1580.0, dT=40.0):
    def g(TT):
        inp = eq.build_inputs(db, p, TT, components=COMPONENTS)
        return act.delta_g_mix(inp, x)
    return g(T) - T * (g(T + dT) - g(T - dT)) / (2 * dT)


def fit_excess(data, use_skew):
    """Least-squares fit of the excess to the measured ln a(FeO); returns (a00,b00,a10)."""
    def resid(q):
        a00, b00 = q[0], q[1]
        a10 = q[2] if use_skew else 0.0
        db, p = build_db(_excess_coeffs(a00, b00, a10))
        return np.array([np.log(model_afeo(db, p, X, T)) - np.log(a)
                         for X, a, src, T in data])
    x0 = [-40000.0, 15.0] + ([0.0] if use_skew else [])
    sol = least_squares(resid, x0, xtol=1e-12, ftol=1e-12)
    a00, b00 = sol.x[0], sol.x[1]
    a10 = sol.x[2] if use_skew else 0.0
    return (a00, b00, a10), np.sqrt(np.mean(sol.fun ** 2))


def fit_beta(excess_coeffs):
    """Fit the FeO below-1650 K correction beta so fayalite melts at 1478 K."""
    def melt_err(beta):
        db, p = build_db(excess_coeffs, beta=beta)
        Tc = congruent_T(db, p)
        return (Tc if Tc is not None else 900.0) - T_FAYALITE_CONGRUENT
    return brentq(melt_err, -80.0, 0.0, xtol=1e-4)


def main(write=True):
    data = load_activities()
    low = [d for d in data if d[3] < 1700]
    print(f"digitized measured a(FeO): {len(data)} points "
          f"({len(low)} at ~1580 K, {len(data)-len(low)} at 2153 K)\n")

    # --- decide symmetric vs skew ---
    (a00s, b00s, _), rms_s = fit_excess(data, use_skew=False)
    (a00k, b00k, a10k), rms_k = fit_excess(data, use_skew=True)
    print(f"symmetric  a00={a00s:.0f}  b00={b00s:+.3f}          rms ln a = {rms_s:.3f}")
    print(f"+skew      a00={a00k:.0f}  b00={b00k:+.3f}  a10={a10k:.0f}  rms ln a = {rms_k:.3f}")
    # keep the skew only if it cuts the residual meaningfully below the ~0.02 read noise
    use_skew = (rms_s - rms_k) > 0.015
    a00, b00, a10 = (a00k, b00k, a10k) if use_skew else (a00s, b00s, 0.0)
    print(f"-> using {'a00+b00*T + a10 skew' if use_skew else 'symmetric a00+b00*T'}\n")

    excess_coeffs = _excess_coeffs(a00, b00, a10)
    beta = fit_beta(excess_coeffs)
    db, p = build_db(excess_coeffs, beta=beta)
    Tc = congruent_T(db, p)

    print("excess  Delta_g(Fe,Si)/O = a00 + b00*T  [J/mol]  (+ a10*chi_Fe skew):")
    print(f"  a00={a00:.1f}  b00={b00:+.4f}  a10={a10:.1f}")
    print(f"FeO(l) below-1650 K correction  dG = beta*(T-1650):  beta={beta:+.4f} J/mol/K")
    print(f"  (FeO liquid destabilized by {beta*(1478-1650):+.0f} J/mol at 1478 K; 0 at/above 1650)")
    print(f"\nfayalite congruent melting: {Tc:.0f} K  (target {T_FAYALITE_CONGRUENT:.0f})")
    for T in (1580.0, 1833.0):
        print(f"dGmix(1/3,{T:.0f}K) = {dgmix(db,p,X_FAYALITE,T)/1000:+.2f} kJ/mol-ox   "
              f"dHmix(1/3) = {dh_mix(db,p,X_FAYALITE,T)/1000:+.2f}")
    print(f"dGmix(1/2,1580K) = {dgmix(db,p,0.5,1580.0)/1000:+.2f} kJ/mol-ox")

    print("\nper-point fit (X_FeO  T  a_meas  a_model  dln_a):")
    for X, a, src, T in data:
        am = model_afeo(db, p, X, T)
        print(f"  {X:.3f}  {T:.0f}  {a:.3f}  {am:.3f}  {np.log(am/a):+.3f}  {src}")

    if write:
        excess = [dict(code="Q", li=[1, 2, 3, 3], exp=[0, 0, 0, 0], coeffs=list(excess_coeffs[0])),
                  dict(code="Q", li=[1, 2, 3, 3], exp=[1, 0, 0, 0], coeffs=list(excess_coeffs[1]))]
        out = HERE / "FeO-SiO2-liquid.dat"
        out.write_text(bd.build(excess, version="v0.3", feo_liq_beta=beta), encoding="ascii")
        print(f"\nwrote {out}")
    return (a00, b00, a10), beta


if __name__ == "__main__":
    main()
