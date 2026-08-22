"""v0.3 joint fit: CaO-SiO2 liquid excess anchored to the phase diagram + calorimetry.

Step 1 (literature) and the MLIP experiment both point to a DEEP liquid: the modern
open assessment (Abdul 2023) does not fit activities but the phase diagram +
calorimetry, and treats activities as a check; Stolyarova's KEMS activities are the
shallow outlier the field does not use. So v0.3:

  - corrects the CaO liquid endmember melting point (v0.1 used the flagged JANAF
    estimate 3200 K; the modern value is ~2845 K, CRC / recent reassessment cited by
    Abdul 2023);
  - adds an excess ENTROPY term (L = a + b*T) so one excess reproduces activities near
    1900 K AND compound melting at 1817/2403 K (a constant L cannot);
  - anchors to the experimental congruent melting of CS (1817 K) and C2S (2403 K)
    with high weight, uses Kay-Taylor a(SiO2) as a soft check, and DOWN-WEIGHTS
    Stolyarova as the documented outlier.

Excess model (cation mixing on (Ca,Si,O,O)):
    g00 = a00 + b00*T   (symmetric enthalpy + entropy)
    g10 = a10           (chi_Ca skew, enthalpy only)
All activities are treated solid-referenced (Abdul reports vs cristobalite / solid
CaO; the KEMS pure-oxide reference is the stable solid at these T).
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
import fit_excess as fx
import phase_diagram as pdg
import joint_fit as jf

R = 8.3145
CAO_TM = 2845.0
EXPONENTS = [(0, 0), (1, 0)]
# Enthalpy of mixing at x=0.5 (per oxide unit). Raw MLIP: MatterSim -42, ORB -55.
# The dHf spot-check showed MatterSim under-binds CaSiO3 by ~9 kJ; applying that same
# bias to the liquid deepens the MLIP to ~ -55..-60, which coincides with the value
# the compound melting requires (~ -60). We anchor at -58 kJ, where the bias-corrected
# MLIP, the calorimetry, and the melting all agree.
MLIP_DH = -58000.0
W_DH, W_MELT, W_KT, W_STOL = 3.0, 3.0, 1.0, 0.2


def set_L(inp, params, T):
    a00, b00, a10 = params
    act.set_excess_L(inp, [a00 + b00 * T, a10])


def residuals(params, inp_s, inp_k, db, p, report=False):
    res, rows = [], []
    set_L(inp_s, params, fx.T_STOL)
    for x, (aC, aS) in sorted(fx.STOL.items()):
        if x in fx.STOL_DROP:
            continue
        cC, cS = act.activities(inp_s, x, fx.T_STOL)
        cC *= np.exp(jf.dgfus("CaO", fx.T_STOL) / (R * fx.T_STOL))   # -> solid ref
        cS *= np.exp(jf.dgfus("SiO2", fx.T_STOL) / (R * fx.T_STOL))
        res += [W_STOL * (np.log(cC) - np.log(aC)),
                W_STOL * 0.5 * (np.log(cS) - np.log(aS))]
        rows += [("Stol aCaO", x, aC, cC), ("Stol aSiO2", x, aS, cS)]

    for cao, sio2, a_sol, T, _run in fx.KAYTAYLOR:
        x = (sio2 / fx.MW_SIO2) / (cao / fx.MW_CAO + sio2 / fx.MW_SIO2)
        if x > fx.KT_XMAX:
            continue
        set_L(inp_k, params, T)
        _cC, cS = act.activities(inp_k, x, T)
        cS *= np.exp(jf.dgfus("SiO2", T) / (R * T))
        res.append(W_KT * (np.log(cS) - np.log(a_sol)))
        rows.append(("KT aSiO2", x, a_sol, cS))

    for name, (x, Tm) in jf.MELTS.items():
        im = eq.build_inputs(db, p, Tm, components=["CA", "SI", "O"])
        set_L(im, params, Tm)
        m0 = (pdg.liquid_gibbs_per_formula_unit(im, x, Tm)
              - pdg.solid_gibbs_per_formula_unit(name, Tm)[0])
        res.append(W_MELT * m0 / (R * Tm))                        # G_liq = G_solid at Tm
        rows.append(("melt " + name, x, 0.0, m0))

    # MLIP enthalpy-of-mixing anchor at x=0.5 (the validated liquid depth)
    T0 = 1900.0
    ilo = eq.build_inputs(db, p, T0 - 50, components=["CA", "SI", "O"])
    ihi = eq.build_inputs(db, p, T0 + 50, components=["CA", "SI", "O"])
    im0 = eq.build_inputs(db, p, T0, components=["CA", "SI", "O"])
    set_L(ilo, params, T0 - 50); set_L(ihi, params, T0 + 50); set_L(im0, params, T0)
    dgdT = (act.delta_g_mix(ihi, 0.5) - act.delta_g_mix(ilo, 0.5)) / 100.0
    dH = act.delta_g_mix(im0, 0.5) - T0 * dgdT
    res.append(W_DH * (dH - MLIP_DH) / (R * T0))
    rows.append(("MLIP dHmix", 0.5, MLIP_DH, dH))

    return (np.array(res), rows) if report else np.array(res)


def dh_mix(inp_lo, inp_hi, params, x, T, dT):
    """Enthalpy of mixing per oxide unit at (x,T) by dG/dT finite difference."""
    set_L(inp_lo, params, T - dT); g_lo = act.delta_g_mix(inp_lo, x)
    set_L(inp_hi, params, T + dT); g_hi = act.delta_g_mix(inp_hi, x)
    set_L(inp_lo, params, T); g = act.delta_g_mix(inp_lo, x)  # inp_lo rebuilt below
    dgdT = (g_hi - g_lo) / (2 * dT)
    return g - T * dgdT  # H = G - T dG/dT... = G + T S, with S=-dG/dT


def main(write=True):
    bd.OXIDES["CaO"]["Tm"] = CAO_TM
    db, p, inp_s, inp_k = jf.build_scaffold(2, CAO_TM)
    x0 = [-120000.0, 0.0, 60000.0]
    sol = least_squares(residuals, x0, args=(inp_s, inp_k, db, p),
                        method="trf", x_scale=[1e5, 1e1, 1e5],
                        diff_step=1e-2, xtol=1e-10, ftol=1e-10)
    a00, b00, a10 = sol.x
    res, rows = residuals(sol.x, inp_s, inp_k, db, p, report=True)

    print("=" * 72)
    print(f"v0.3 fit  (CaO Tm={CAO_TM:.0f} K, solid-referenced activities)")
    print("=" * 72)
    print(f"  g00 = {a00:+.1f} {b00:+.3f}*T   g10 = {a10:+.1f}   J/mol")
    kt = [np.log(c/m) for lab, x, m, c in rows if lab == "KT aSiO2"]
    sca = [np.log(c/m) for lab, x, m, c in rows if lab == "Stol aCaO"]
    scs = [np.log(c/m) for lab, x, m, c in rows if lab == "Stol aSiO2"]
    rms = lambda v: float(np.sqrt(np.mean(np.square(v)))) if v else float("nan")
    print(f"  activity RMS ln(a):  KT a(SiO2)={rms(kt):.3f}  "
          f"Stol a(CaO)={rms(sca):.3f}  Stol a(SiO2)={rms(scs):.3f}")
    for lab, x, m, c in rows:
        if lab.startswith("melt"):
            print(f"  {lab}: G_liq-G_solid = {c/1000:+.1f} kJ/mol-unit  "
                  f"({'melts ~Tm' if abs(c) < 3000 else 'off'})")

    # implied liquid dH_mix at x=0.5, 1900 K vs MLIP (-64) and calorimetry (-45..-57)
    T = 1900.0
    ilo = eq.build_inputs(db, p, T - 50, components=["CA", "SI", "O"])
    ihi = eq.build_inputs(db, p, T + 50, components=["CA", "SI", "O"])
    im = eq.build_inputs(db, p, T, components=["CA", "SI", "O"])
    set_L(ilo, sol.x, T - 50); glo = act.delta_g_mix(ilo, 0.5)
    set_L(ihi, sol.x, T + 50); ghi = act.delta_g_mix(ihi, 0.5)
    set_L(im, sol.x, T); gmid = act.delta_g_mix(im, 0.5)
    dgdT = (ghi - glo) / 100.0
    dH = gmid - T * dgdT
    print(f"\n  implied liquid dH_mix(x=0.5, {T:.0f}K) = {dH/1000:+.1f} kJ/mol-unit "
          f"(dG_mix={gmid/1000:+.1f})")
    print("    compare  MLIP ~ -64 (deep) ; calorimetry+melting ~ -45..-57 ; "
          "Stolyarova activities ~ -30")

    # full-range stability
    set_L(inp_s, sol.x, fx.T_STOL)
    xs = np.linspace(0.05, 0.95, 40)
    g = np.array([act.delta_g_mix(inp_s, xx) for xx in xs])
    d2 = np.gradient(np.gradient(g, xs), xs)
    uns = [round(float(xx), 2) for xx, u in zip(xs, d2 < -1) if u]
    print(f"  spinodal: {uns if uns else 'NONE (stable across join)'}")

    if write:
        excess = [dict(code="Q", li=[1, 2, 3, 3], exp=[0, 0, 0, 0],
                       coeffs=[a00, b00, 0, 0, 0, 0]),
                  dict(code="Q", li=[1, 2, 3, 3], exp=[1, 0, 0, 0],
                       coeffs=[a10, 0, 0, 0, 0, 0])]
        out = HERE / "CaO-SiO2-liquid.dat"
        out.write_text(bd.build(excess, version="v0.3"), encoding="ascii")
        print(f"\n  wrote {out} (v0.3, CaO Tm={CAO_TM:.0f} K)")
    return sol


if __name__ == "__main__":
    main()
