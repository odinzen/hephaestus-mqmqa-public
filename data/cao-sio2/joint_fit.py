"""Joint fit of the CaO-SiO2 liquid excess to activities AND compound melting.

v0.2 fit the excess to activities alone and came out ~30 kJ too shallow to melt the
Ca-silicates (see phase_diagram.py). The standard assessment fix is a JOINT fit: the
liquid must reproduce the measured activities AND put the liquid level with the solid
compound at each measured melting point. Two things control whether that joint fit is
consistent or a forced compromise, and both were flagged, so we resolve them here by
fitting across the 2x2 and reading off which combination reconciles the data:

  - Stolyarova activity reference: pure LIQUID oxide (v0.2 assumption) vs pure SOLID
    oxide (the physics - a KEMS run references the vapor over the stable pure phase,
    which is solid at 1933 K).
  - CaO liquid endmember melting point: the flagged JANAF estimate Tm = 3200 K vs a
    modern value ~2845 K (CRC Handbook, 2572 C).

Objective (least squares, all terms dimensionless):
  - activity: ln(a_engine) - ln(a_measured), Stolyarova (single-phase points) in the
    chosen reference + Kay-Taylor a(SiO2) in its native solid-SiO2 reference.
  - melting: [G_liq(x_compound, Tm) - G_solid(compound, Tm)] / (R Tm) at the published
    melting points of pseudowollastonite (1817 K) and C2S (2403 K).

Only open measured data enters (activities: Stolyarova 1991, Kay-Taylor 1960; compound
melting + formation: Abdul 2023 / Adamkovicova; endmembers: R&H, JANAF, CRC).
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

R = 8.3145
EXPONENTS = [(0, 0), (1, 0), (2, 0)]

# Each excess term carries L(T) = a + b*T: a is the excess ENTHALPY, b the excess
# ENTROPY (negative b -> positive excess entropy). A constant L (b=0) forces zero
# excess entropy, which cannot match activities near 1900 K AND compound melting at
# 1817/2403 K simultaneously - the T-slope of G_liq-G_solid is the entropy term.
# The fit vector is [a0, b0, a1, b1, ...] over the EXPONENTS terms.


def set_L(inp, params, T):
    """Write L_k(T) = a_k + b_k*T into the prebuilt inp at temperature T."""
    L = [params[2 * k] + params[2 * k + 1] * T for k in range(len(params) // 2)]
    act.set_excess_L(inp, L)

# melting anchors: compound -> (x_SiO2, Tm_published K)
MELTS = {"CS(pseudowoll)": (0.5, 1817.0), "C2S(gamma)": (1.0 / 3.0, 2403.0)}
W_MELT = 1.0  # weight per melting residual relative to one ln(a) residual


def dgfus(ox_name, T):
    ox = bd.OXIDES[ox_name]
    return ox["dHfus"] * (1.0 - T / ox["Tm"])


def build_scaffold(n_params, cao_tm):
    """Write + read a scaffold .dat with the given CaO melting point and n excess
    Q-terms (L=0), returning liquid inputs at the two activity-data temperatures."""
    tm_saved = bd.OXIDES["CaO"]["Tm"]
    bd.OXIDES["CaO"]["Tm"] = cao_tm
    try:
        excess = [dict(code="Q", li=[1, 2, 3, 3], exp=[p, q, 0, 0], coeffs=[0.0] * 6)
                  for (p, q) in EXPONENTS[:n_params]]
        path = HERE / "_joint_scaffold.dat"
        path.write_text(bd.build(excess), encoding="ascii")
        db = mqmqa.Database.read(str(path))
        p = db.phase_index("CAO-SIO2-LIQUID")
        inp_s = eq.build_inputs(db, p, fx.T_STOL, components=["CA", "SI", "O"])
        inp_k = eq.build_inputs(db, p, fx.T_KT, components=["CA", "SI", "O"])
    finally:
        bd.OXIDES["CaO"]["Tm"] = tm_saved
    return db, p, inp_s, inp_k


def residuals(params, inp_s, inp_k, db, p, ref, cao_tm, report=False):
    set_L(inp_s, params, fx.T_STOL)
    set_L(inp_k, params, fx.T_KT)
    res, rows = [], []

    # Stolyarova activities, single-phase points, in the chosen reference
    for x, (aC, aS) in sorted(fx.STOL.items()):
        if x in fx.STOL_DROP:
            continue
        cC, cS = act.activities(inp_s, x, fx.T_STOL)  # engine liquid-ref
        if ref == "solid":
            cC *= np.exp(dgfus("CaO", fx.T_STOL) / (R * fx.T_STOL))
            cS *= np.exp(dgfus("SiO2", fx.T_STOL) / (R * fx.T_STOL))
        res.append(np.log(cC) - np.log(aC))
        res.append(0.5 * (np.log(cS) - np.log(aS)))
        rows.append(("Stol aCaO", x, aC, cC))
        rows.append(("Stol aSiO2", x, aS, cS))

    # Kay-Taylor a(SiO2): native solid-SiO2 reference (compare engine solid-SiO2 ref)
    for cao, sio2, a_sol, T, _run in fx.KAYTAYLOR:
        n_cao, n_sio2 = cao / fx.MW_CAO, sio2 / fx.MW_SIO2
        x = n_sio2 / (n_cao + n_sio2)
        if x > fx.KT_XMAX:
            continue
        set_L(inp_k, params, T)
        _cC, cS = act.activities(inp_k, x, T)
        cS *= np.exp(dgfus("SiO2", T) / (R * T))  # engine liquid-ref -> solid-SiO2 ref
        res.append(np.log(cS) - np.log(a_sol))
        rows.append(("KT aSiO2", x, a_sol, cS))

    # melting anchors: G_liq(x, Tm) == G_solid(compound, Tm)
    for name, (x, Tm) in MELTS.items():
        inp_m = eq.build_inputs(db, p, Tm, components=["CA", "SI", "O"])
        set_L(inp_m, params, Tm)
        gl = pdg.liquid_gibbs_per_formula_unit(inp_m, x, Tm)
        gs, _ = pdg.solid_gibbs_per_formula_unit(name, Tm)
        res.append(W_MELT * (gl - gs) / (R * Tm))
        rows.append(("melt " + name, x, 0.0, (gl - gs)))

    if report:
        return np.array(res), rows
    return np.array(res)


def fit(n_terms, ref, cao_tm, with_entropy=True):
    """n_terms excess terms; with_entropy adds a b*T coefficient to each term."""
    tm_saved = bd.OXIDES["CaO"]["Tm"]
    bd.OXIDES["CaO"]["Tm"] = cao_tm
    try:
        db, p, inp_s, inp_k = build_scaffold(n_terms, cao_tm)
        # params [a0,b0,a1,b1,...]; seed enthalpies negative, entropies 0
        x0, scale = [], []
        for k in range(n_terms):
            x0 += [-60000.0 if k == 0 else 0.0, 0.0]
            scale += [1e4, 1e1]
        sol = least_squares(residuals, x0, args=(inp_s, inp_k, db, p, ref, cao_tm),
                            method="trf", x_scale=scale,
                            diff_step=1e-2, xtol=1e-10, ftol=1e-10)
        res, rows = residuals(sol.x, inp_s, inp_k, db, p, ref, cao_tm, report=True)
    finally:
        bd.OXIDES["CaO"]["Tm"] = tm_saved
    return sol, res, rows


def summarize(rows):
    act_ln = [np.log(c / m) for (lab, x, m, c) in rows if lab.startswith(("Stol", "KT"))]
    melts = [(lab, c) for (lab, x, m, c) in rows if lab.startswith("melt")]
    rms = float(np.sqrt(np.mean(np.square(act_ln))))
    return rms, melts


def show(tag, sol, rows, n_terms):
    rms, melts = summarize(rows)
    ms = ", ".join(f"{lab.split()[1][:3]}:{c/1000:+.1f}kJ" for lab, c in melts)
    terms = ", ".join(f"g{EXPONENTS[k][0]}{EXPONENTS[k][1]}: "
                      f"{sol.x[2*k]:+.0f}{sol.x[2*k+1]:+.2f}*T"
                      for k in range(n_terms))
    print(f"\n{tag}")
    print(f"   {terms}")
    print(f"   activity RMS ln(a) = {rms:.3f}   melting residual: {ms}")


if __name__ == "__main__":
    print("Effect of an EXCESS ENTROPY term (L = a + b*T), solid reference, CaO Tm=2845")
    print("=" * 74)

    sol, res, rows = fit(2, "solid", 2845.0)
    # zero the b coefficients to emulate the constant-L fit is not trivial post-hoc;
    # instead compare against the earlier constant result reported in the diagnosis.
    show("2 terms, WITH entropy (a+b*T each):", sol, rows, 2)

    sol1, _, rows1 = fit(1, "solid", 2845.0)
    show("1 term (g00 = a+b*T only):", sol1, rows1, 1)

    print("\n(Compare: the constant-L joint fit gave activity RMS 0.317 with melting")
    print(" residuals +14.8/+7.8 kJ - it could not close melting without wrecking")
    print(" activities. The entropy term should lower BOTH at once.)")
