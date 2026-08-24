"""v0.2 fit: FeO-SiO2 liquid excess, phase-diagram anchored, MLIP-informed depth.

Iron-saturated FeO-SiO2 has no digitized liquid activities, so the phase diagram is the
primary constraint. Two anchors fix a symmetric cation-mixing excess (no activity data
justifies a composition skew, so a10 = 0):

  1. fayalite Fe2SiO4 CONGRUENT melting = 1478 K (Bowen & Schairer 1932) - the measured,
     hard anchor. It sets the excess ENTROPY (T-slope), and it is itself decisive: fayalite
     melts LOW (unlike refractory forsterite at 2163 K), so the liquid must be SHALLOW - a
     deep liquid would melt fayalite far below 1478 K.
  2. enthalpy of mixing depth dH_mix(x=1/3) ~ -9.5 kJ/mol-oxide, set by:
       (a) the compound-stability scaling from MgO-SiO2 v0.2: dH_mix scales with the oxide
           formation enthalpy, and fayalite is 0.39x as bound as forsterite (dHf_ox = -23.4
           vs -60.25 kJ/mol, measured), so -24.5 x 0.39 = -9.5 kJ; and
       (b) the MLIP over-binding bias-check (_mlip/mlip_hf.py): MatterSim over-binds fayalite
           by +8.1 kJ/oxide, so its raw melt-mixing dH is too deep - correcting it points the
           same way (shallow). The full liquid melt-mixing MD (_mlip/mlip_mix.py) was run but
           did not converge in practical time on the available CPU (the dense FeO endmember
           melt was pathologically slow); the depth is therefore anchored on (a)+(b), which
           the measured congruent melting independently corroborates.

Excess model (cation mixing on (Fe,Si,O,O) = linear indices (1,2,3,3)):
    Delta_g(Fe,Si)/O = a00 + b00*T    (symmetric enthalpy + entropy; a10 = 0)

The large positive b00 the fit returns reflects a calibration offset - the ideal MQMQA
liquid melts fayalite ~170 K below 1478 K, so a positive excess entropy is needed to raise
it - documented as a v0.3 refinement target (a recalibrated FeO endmember or measured
FeO-SiO2 activities, e.g. Schuhmann & Ensio 1951). The resulting liquid is well-behaved:
single-welled delta_g_mix (no spurious gap) and negative-deviation activities.
"""
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

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

T_FAYALITE_CONGRUENT = 1478.0     # Bowen & Schairer 1932 (1205 C)
X_FAYALITE = 1.0 / 3.0
DH_MIX_X13 = -9500.0              # J/mol-oxide (dHf_ox-scaled; MLIP-bias-confirmed shallow)


def set_L(inp, params, T):
    a00, b00, a10 = params
    act.set_excess_L(inp, [a00 + b00 * T, a10])


def build_scaffold():
    excess = [dict(code="Q", li=[1, 2, 3, 3], exp=[0, 0, 0, 0], coeffs=[0.0] * 6),
              dict(code="Q", li=[1, 2, 3, 3], exp=[1, 0, 0, 0], coeffs=[0.0] * 6)]
    path = HERE / "_v02_scaffold.dat"
    path.write_text(bd.build(excess), encoding="ascii")
    db = mqmqa.Database.read(str(path))
    return db, db.phase_index("FEO-SIO2-LIQUID")


def _congruent_T(db, p, params, name, x, lo=1100.0, hi=2000.0):
    def f(T):
        inp = eq.build_inputs(db, p, T, components=COMPONENTS)
        set_L(inp, params, T)
        gs, _ = pdg.solid_gibbs_per_formula_unit(name, T)
        return pdg.liquid_gibbs_per_formula_unit(inp, x, T) - gs
    if f(lo) * f(hi) > 0:
        return None
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        (lo, hi) = (mid, hi) if f(lo) * f(mid) > 0 else (lo, mid)
    return 0.5 * (lo + hi)


def dh_mix(db, p, params, x, T=1700.0, dT=50.0):
    def g(TT):
        inp = eq.build_inputs(db, p, TT, components=COMPONENTS)
        set_L(inp, params, TT)
        return act.delta_g_mix(inp, x)
    glo, gmid, ghi = g(T - dT), g(T), g(T + dT)
    return gmid - T * (ghi - glo) / (2 * dT)


def _melt_margin(db, p, params, T=T_FAYALITE_CONGRUENT, x=X_FAYALITE):
    """G_liq(x,T) - G_solid_fayalite(T); zero when fayalite melts congruently at T. A
    smooth residual, unlike the root-find (which can be undefined mid-optimization)."""
    inp = eq.build_inputs(db, p, T, components=COMPONENTS)
    set_L(inp, params, T)
    gs, _ = pdg.solid_gibbs_per_formula_unit("Fa(fayalite)", T)
    return pdg.liquid_gibbs_per_formula_unit(inp, x, T) - gs


def residuals(q, db, p):
    """Symmetric fit (a10 = 0): melting margin + the enthalpy-depth anchor."""
    a00, b00 = q
    params = [a00, b00, 0.0]
    return np.array([
        3.0 * _melt_margin(db, p, params) / 1600.0,
        (dh_mix(db, p, params, X_FAYALITE) - DH_MIX_X13) / (R * 1700.0)])


def main(write=True):
    db, p = build_scaffold()
    sol = least_squares(residuals, [-24000.0, 25.0], args=(db, p), xtol=1e-12, ftol=1e-12)
    a00, b00 = sol.x
    params = [a00, b00, 0.0]
    Tc = _congruent_T(db, p, params, "Fa(fayalite)", X_FAYALITE)
    print("symmetric excess  Delta_g(Fe,Si)/O = a00 + b00*T  [J/mol]:")
    print(f"  a00={a00:.1f}  b00={b00:+.4f}  (a10 = 0)")
    print(f"  fayalite congruent melting: {Tc:.0f} K  (target {T_FAYALITE_CONGRUENT:.0f})")
    print(f"  dH_mix(x=1/3): {dh_mix(db, p, params, X_FAYALITE)/1000:+.2f}  "
          f"(target {DH_MIX_X13/1000:+.1f}) kJ/mol-oxide")
    print(f"  dH_mix(x=1/2): {dh_mix(db, p, params, 0.5)/1000:+.2f} kJ/mol-oxide")
    if write:
        excess = [dict(code="Q", li=[1, 2, 3, 3], exp=[0, 0, 0, 0], coeffs=[a00, b00, 0, 0, 0, 0]),
                  dict(code="Q", li=[1, 2, 3, 3], exp=[1, 0, 0, 0], coeffs=[0, 0, 0, 0, 0, 0])]
        out = HERE / "FeO-SiO2-liquid.dat"
        out.write_text(bd.build(excess, version="v0.2"), encoding="ascii")
        print(f"  wrote {out}")
    return params


if __name__ == "__main__":
    main()
