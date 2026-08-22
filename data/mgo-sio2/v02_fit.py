"""v0.2 fit: MgO-SiO2 liquid excess, phase-diagram + MLIP triangulation.

MgO-SiO2 has no measured liquid activities, so the phase diagram + an independent MLIP
are the constraints (the reference-state / activity arbitration that CaO-SiO2 needed
does not arise here). We fit a cation-mixing excess with an entropy term on the
MgO-rich / central side, where a negative-deviation excess is the right model form (the
silica-rich liquid-liquid gap needs SiO2-specific coordination Z = v0.4, deferred).

Three targets fix the three excess coefficients, cleanly separating enthalpy from
entropy (as in CaO-SiO2 v0.3, where melting pins the T-scale and the MLIP pins depth):

  1. forsterite Mg2SiO4 CONGRUENT melting = 2163 K (Bowen & Andersen 1914) -> the excess
     ENTROPY (T-slope of G_liq - G_solid), i.e. b00.
  2. bias-corrected MLIP dH_mix(x = 1/3)  -> the enthalpy at the forsterite composition.
  3. bias-corrected MLIP dH_mix(x = 1/2)  -> the composition dependence (chi_Mg skew).

The MLIP melt-mixing MD (MatterSim/ORB, _mlip/mlip_mix.py) is bias-corrected by the
dHf spot-check (mlip_hf.py: MatterSim under-binds the Mg-silicates - forsterite by
+2.7, enstatite by +6.2 kJ/mol-oxide-unit - so the raw liquid dH_mix is deepened by
that amount). The periclase-forsterite eutectic and the enstatite peritectic are NOT
fit; they are read off the hull classifier and reported with their (solid-model-limited)
temperature offsets - the MgO endmember is too refractory to resolve the shallow 40 K
eutectic valley, a documented v0.2 limit. The Greig silica-rich gap is deferred to v0.4.

Excess model (cation mixing on (Mg,Si,O,O) = linear indices (1,2,3,3)):
    g00 = a00 + b00*T   (symmetric enthalpy + entropy)
    g10 = a10           (chi_Mg skew, enthalpy only)
    Delta_g(Mg,Si)/O = (a00 + b00*T) + a10 * chi_Mg
"""

import sys
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares, minimize_scalar

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "python"))

import build_dat as bd
import mqmqa
from mqmqa import equilibrium as eq
import _activity as act
import phase_diagram as pdg

R = 8.3145
COMPONENTS = pdg.COMPONENTS

# published anchors
T_FORST_CONGRUENT = 2163.0          # Bowen-Andersen 1914
X_FORST = 1.0 / 3.0
T_PF_EUTECTIC = 2123.0              # Bowen-Andersen 1914 (reported, not fit)
# eutectic liquid 65 wt% MgO / 35 wt% SiO2 -> x_SiO2 (MW SiO2 60.084, MgO 40.304)
_nSi = 35.0 / 60.084
_nMg = 65.0 / 40.304
X_PF_EUTECTIC = _nSi / (_nSi + _nMg)                  # ~0.265

# Bias-corrected MLIP dH_mix per mole of oxide unit, at the forsterite (x=1/3) and
# enstatite (x=1/2) compositions. Filled from _mlip/mix_*.log after the MD, then
# deepened by the dHf-spot-check under-binding bias (mlip_hf.py): forsterite +2.7,
# enstatite +6.2 kJ/mol-oxide-unit. These ARE fit anchors (targets 2 and 3).
MLIP_BIAS = {X_FORST: -2670.0, 0.5: -6150.0}   # J/mol-oxide-unit, added to raw MD dH
# Raw MatterSim melt-mixing MD at 3200 K (_mlip/mix_mattersim.log; seed 1234,
# 1.5/3/6 ps melt/eq/samp): dH_mix(x=1/3) = -21.8, dH_mix(x=1/2) = -16.2 kJ/mol-oxide.
MLIP_RAW = {X_FORST: -21800.0, 0.5: -16200.0}
MLIP_DH = {X_FORST: None, 0.5: None}           # bias-corrected values (set in set_mlip)
W_MELT, W_DH = 3.0, 1.0


def set_mlip(raw_x13=None, raw_x05=None):
    """Record bias-corrected MLIP dH_mix from raw MD values (J/mol-oxide-unit)."""
    r13 = MLIP_RAW[X_FORST] if raw_x13 is None else raw_x13
    r05 = MLIP_RAW[0.5] if raw_x05 is None else raw_x05
    MLIP_DH[X_FORST] = r13 + MLIP_BIAS[X_FORST]
    MLIP_DH[0.5] = r05 + MLIP_BIAS[0.5]


def set_L(inp, params, T):
    a00, b00, a10 = params
    act.set_excess_L(inp, [a00 + b00 * T, a10])


def _congruent_T(db, p, params, name, x, lo=1600.0, hi=2700.0):
    def f(T):
        inp = eq.build_inputs(db, p, T, components=COMPONENTS)
        set_L(inp, params, T)
        gs, _ = pdg.solid_gibbs_per_formula_unit(name, T)
        return pdg.liquid_gibbs_per_formula_unit(inp, x, T) - gs
    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:
        return None
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        (lo, hi) = (mid, hi) if f(lo) * f(mid) > 0 else (lo, mid)
    return 0.5 * (lo + hi)


def _tie(n1, n2, T):
    """Periclase-forsterite tie line g(x) between the two solids at T."""
    g1, x1 = pdg.solid_gibbs_per_formula_unit(n1, T)
    g2, x2 = pdg.solid_gibbs_per_formula_unit(n2, T)
    return lambda x: g1 + (g2 - g1) * (x - x1) / (x2 - x1), x1, x2


def _eutectic_margin_and_x(db, p, params, T, n1="MgO(periclase)", n2="M2S(forsterite)"):
    """Min of (G_liq - tie) over the interval, and the argmin composition."""
    tie, x1, x2 = _tie(n1, n2, T)
    xa, xb = sorted((x1, x2))
    inp = eq.build_inputs(db, p, T, components=COMPONENTS)
    set_L(inp, params, T)

    def m(x):
        return pdg.liquid_gibbs_per_formula_unit(inp, float(x), T) - tie(float(x))

    res = minimize_scalar(m, bounds=(xa + 1e-3, xb - 1e-3), method="bounded",
                          options={"xatol": 1e-5})
    return res.fun, res.x


def _eutectic(db, p, params, lo=1800.0, hi=2400.0):
    """Eutectic temperature (liquid tangent to the periclase-forsterite tie) and
    the eutectic composition, by bisection on the sign of the min-margin."""
    def mm(T):
        return _eutectic_margin_and_x(db, p, params, T)[0]
    mlo, mhi = mm(lo), mm(hi)
    # margin < 0: liquid dips below the tie (T above eutectic); > 0: no melt yet
    if mlo * mhi > 0:
        return None, None
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        (lo, hi) = (mid, hi) if (mm(lo) < 0) == (mm(mid) < 0) else (lo, mid)
    Te = 0.5 * (lo + hi)
    _, xe = _eutectic_margin_and_x(db, p, params, Te)
    return Te, float(xe)


def build_scaffold(cao_tm=None):
    excess = [dict(code="Q", li=[1, 2, 3, 3], exp=[0, 0, 0, 0], coeffs=[0.0] * 6),
              dict(code="Q", li=[1, 2, 3, 3], exp=[1, 0, 0, 0], coeffs=[0.0] * 6)]
    path = HERE / "_v02_scaffold.dat"
    path.write_text(bd.build(excess), encoding="ascii")
    db = mqmqa.Database.read(str(path))
    return db, db.phase_index("MGO-SIO2-LIQUID")


def residuals(params, db, p, report=False):
    Tc = _congruent_T(db, p, params, "M2S(forsterite)", X_FORST)
    dh13 = dh_mix(db, p, params, X_FORST)
    dh05 = dh_mix(db, p, params, 0.5)
    r = []
    r.append(W_MELT * (Tc - T_FORST_CONGRUENT) / 40.0 if Tc else 5.0)
    r.append(W_DH * (dh13 - MLIP_DH[X_FORST]) / (R * 2100.0))
    r.append(W_DH * (dh05 - MLIP_DH[0.5]) / (R * 2100.0))
    if report:
        return np.array(r), dict(Tc=Tc, dh13=dh13, dh05=dh05)
    return np.array(r)


def dh_mix(db, p, params, x, T=2100.0, dT=50.0):
    """Liquid enthalpy of mixing per oxide unit at (x, T) via dG/dT finite difference."""
    def g(TT):
        inp = eq.build_inputs(db, p, TT, components=COMPONENTS)
        set_L(inp, params, TT)
        return act.delta_g_mix(inp, x)
    glo, gmid, ghi = g(T - dT), g(T), g(T + dT)
    dgdT = (ghi - glo) / (2 * dT)
    return gmid - T * dgdT


def main(write=True):
    if MLIP_DH[X_FORST] is None:
        set_mlip()  # bias-correct the recorded raw MatterSim MD values
    db, p = build_scaffold()
    x0 = [-70000.0, 8.0, -10000.0]
    sol = least_squares(residuals, x0, args=(db, p), method="trf",
                        x_scale=[1e5, 1e1, 1e5], diff_step=3e-3,
                        xtol=1e-10, ftol=1e-10)
    a00, b00, a10 = sol.x
    r, info = residuals(sol.x, db, p, report=True)

    print("=" * 72)
    print("v0.2 fit  (MgO-SiO2 central liquid, phase-diagram + MLIP triangulation)")
    print("=" * 72)
    print(f"  g00 = {a00:+.1f} {b00:+.4f}*T   g10 = {a10:+.1f}   J/mol")
    print(f"  Delta_g(Mg,Si)/O = ({a00:+.0f} {b00:+.3f}*T) {a10:+.0f}*chi_Mg  J/mol")
    print()
    print("  FIT ANCHORS:")
    print(f"    forsterite congruent melting = {info['Tc']:.0f} K   (target 2163)")
    print(f"    dH_mix(x=1/3) = {info['dh13']/1000:+.1f} kJ  (bias-corr MLIP "
          f"{MLIP_DH[X_FORST]/1000:+.1f})")
    print(f"    dH_mix(x=1/2) = {info['dh05']/1000:+.1f} kJ  (bias-corr MLIP "
          f"{MLIP_DH[0.5]/1000:+.1f})")
    print(f"    residual norm = {np.linalg.norm(r):.3f}")

    # VALIDATION: periclase-forsterite eutectic (reported; solid-model-limited T)
    Te, xe = _eutectic(db, p, sol.x)
    if Te:
        print(f"\n  VALIDATION (not fit):")
        print(f"    periclase-forsterite eutectic = {Te:.0f} K at x_SiO2={xe:.3f}  "
              f"(measured 2123 K, x~{X_PF_EUTECTIC:.3f})")

    # full-range stability (no spurious MgO-rich or interior spinodal)
    inp = eq.build_inputs(db, p, 2000.0, components=COMPONENTS)
    set_L(inp, sol.x, 2000.0)
    xs = np.linspace(0.05, 0.95, 46)
    g = np.array([act.delta_g_mix(inp, xx) for xx in xs])
    d2 = np.gradient(np.gradient(g, xs), xs)
    uns = [round(float(xx), 2) for xx, u in zip(xs, d2 < -1) if u]
    print(f"    spinodal (d2Gmix/dx2<0): {uns if uns else 'NONE (stable across join)'}")

    if write:
        excess = [dict(code="Q", li=[1, 2, 3, 3], exp=[0, 0, 0, 0],
                       coeffs=[a00, b00, 0, 0, 0, 0]),
                  dict(code="Q", li=[1, 2, 3, 3], exp=[1, 0, 0, 0],
                       coeffs=[a10, 0, 0, 0, 0, 0])]
        out = HERE / "MgO-SiO2-liquid.dat"
        out.write_text(bd.build(excess, version="v0.2"), encoding="ascii")
        print(f"\n  wrote {out} (v0.2)")
    return sol


if __name__ == "__main__":
    main()
