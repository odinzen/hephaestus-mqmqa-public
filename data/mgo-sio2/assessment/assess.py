"""CALPHAD assessment of the MgO-SiO2 liquid: fit the liquid excess parameters to the
WHOLE weighted experimental dataset simultaneously (invariants + immiscibility binodal +
consolute + mixing enthalpy), instead of point-fitting a few landmarks.

Liquid excess in the verified equivalent-fraction basis: each term is L*Y_SiO2^q with
L = a + b*T (a = enthalpy omega, b = the entropy/temperature part eta), on the (Mg,Si,O,O)
quadruplet. A rich silica-side polynomial (q = 0,1,3,5,7) mirrors the published
Wu/Eriksson/Pelton form (const + linear ordering + high-power silica, each with its own
temperature dependence). Solids and endmembers are held at their measured values (the
compound calorimetry already constrains them); only the liquid is assessed here.

Run:  PYTHONPATH=python python assess.py [--fit] [--write]
"""
import sys
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[2] / "python"))

import build_dat as bd
import mqmqa
import phase_diagram as pdg
import v05_fit as vf
from mqmqa import equilibrium as eq
import _activity as act
import dataset as ds

pdg.USE_COMPOUND_CP = False
COMP = pdg.COMPONENTS

# excess term powers q (each carries a + b*T). Index maps to the parameter vector as
# [a_q0, b_q0, a_q1, b_q1, ...]. Then 3 SOLID parameters (co-assessed, bounded):
#   [-3] SiO2 dCp_fus (J/mol/K, 0..20; liquid silica Cp above cristobalite)
#   [-2] forsterite dHf_ox vs quartz (J/mol; Charlu-Newton-Kleppa -60250 +- 2000)
#   [-1] enstatite  dHf_ox vs quartz (J/mol; -36860 +- 2000)
QPOW = [0, 1, 3, 5, 7]
NLIQ = 2 * len(QPOW)
# bounds: liquid params free; solid params within measured uncertainty
LOWER = [-np.inf] * NLIQ + [0.0, -62250.0, -38860.0]
UPPER = [np.inf] * NLIQ + [20.0, -58250.0, -34860.0]


def build_db(pp):
    excess = []
    for i, q in enumerate(QPOW):
        a, b = pp[2 * i], pp[2 * i + 1]
        excess.append(dict(code="Q", li=[1, 2, 3, 3], exp=[0, q, 0, 0],
                           coeffs=[a, b, 0, 0, 0, 0]))
    dcp_fus, dHf_forst, dHf_enst = pp[-3], pp[-2], pp[-1]
    pdg.DHF_OX_OVERRIDE = {"M2S(forsterite)": dHf_forst, "MS(enstatite)": dHf_enst}
    import os
    path = HERE / f"_assess_{os.getpid()}.dat"
    path.write_text(bd.build(excess, version="assess", dcp_fus_sio2=dcp_fus), encoding="ascii")
    db = mqmqa.Database.read(str(path))
    return db, db.phase_index("MGO-SIO2-LIQUID"), excess


def cristobalite_liquidus_T(db, p, xL, lo=1750.0, hi=2600.0):
    """T at which cristobalite (x=1) sits on the common tangent to the liquid at xL -
    i.e. the cristobalite liquidus at composition xL. Targeting this at high silica
    (~0.98 -> ~1970 K) directly fights the too-high cristobalite preemption."""
    h = 3e-4
    def f(T):
        inp = eq.build_inputs(db, p, float(T), components=COMP)
        gL = pdg.liquid_gibbs_per_formula_unit(inp, xL, float(T))
        gLp = pdg.liquid_gibbs_per_formula_unit(inp, xL + h, float(T))
        gLm = pdg.liquid_gibbs_per_formula_unit(inp, xL - h, float(T))
        slope = (gLp - gLm) / (2 * h)
        tangent_at_1 = gL + (1.0 - xL) * slope           # extrapolate tangent to x=1
        gC = pdg.solid_gibbs_per_formula_unit("SiO2(cristobalite)", float(T))[0]
        return gC - tangent_at_1                           # <0: cristobalite below -> stable
    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:
        return None
    for _ in range(45):
        m = 0.5 * (lo + hi)
        lo, hi = (m, hi) if f(lo) * f(m) > 0 else (lo, m)
    return 0.5 * (lo + hi)


def dh_mix(db, p, x, T=2100.0, dT=40.0):
    g = lambda TT: act.delta_g_mix(eq.build_inputs(db, p, TT, components=COMP), x)
    return (g(T) - T * (g(T + dT) - g(T - dT)) / (2 * dT)) / 1000.0


def consolute(db, p, lo=1990.0, hi=3200.0, step=35.0):
    Tclose, xc, last = None, None, vf.gap(db, p, lo)
    T = lo
    while T <= hi:
        g = vf.gap(db, p, T)
        if g is None:
            Tclose, xc = T, (0.5 * (last[0] + last[1]) if last else None)
            break
        last = g
        T += step
    return Tclose, xc


def residuals(pp, detail=False):
    db, p, _ = build_db(pp)
    r = vf.all_invariants(db, p)
    out, rows = [], []

    def add(tag, res, info=""):
        out.append(res)
        rows.append((tag, res, info))

    # invariant temperatures
    inv_map = {"periclase-forsterite eutectic": "peri_forst_eut",
               "forsterite congruent": "forsterite",
               "enstatite peritectic": "enst_peri",
               "enstatite-cristobalite eutectic": "encr_eut"}
    for d in ds.INVARIANTS:
        v = r[inv_map[d["name"]]]
        add(f"T[{d['name']}]", ((v - d["T"]) / d["sigT"]) if v else vf.PENALTY,
            f"{v:.0f}/{d['T']:.0f}" if v else "none")

    # immiscibility binodal conjugates (isolated binodal at each measured T)
    for d in ds.BINODAL:
        g = vf.gap(db, p, d["T"])
        if g:
            add(f"bin_lo@{int(d['T'])}", (g[0] - d["x_lo"]) / d["sig"], f"{g[0]:.2f}/{d['x_lo']:.2f}")
            add(f"bin_hi@{int(d['T'])}", (g[1] - d["x_hi"]) / d["sig"], f"{g[1]:.2f}/{d['x_hi']:.2f}")
        else:
            add(f"bin@{int(d['T'])}", vf.PENALTY, "none"); add(f"bin2@{int(d['T'])}", vf.PENALTY, "none")

    # consolute (dome height + critical composition)
    Tc, xc = consolute(db, p)
    for d in ds.CONSOLUTE:
        add("consolute_T", ((Tc - d["T"]) / d["sigT"]) if Tc else vf.PENALTY,
            f"{Tc}/{d['T']:.0f}" if Tc else "none")
        add("consolute_x", ((xc - d["x_c"]) / d["sigx"]) if (Tc and xc) else 0.0,
            f"{xc:.2f}/{d['x_c']:.2f}" if xc else "-")

    # cristobalite liquidus at high silica = the preemption constraint. At the monotectic
    # cristobalite coexists with the silica-rich liquid (~0.985) at ~1968 K; our models put
    # this ~340 K too high (dome preempts). Target it directly.
    for xL, Ttgt, sig in [(0.985, 1975.0, 40.0), (0.90, 1955.0, 60.0)]:
        Tc = cristobalite_liquidus_T(db, p, xL)
        add(f"crist_liq@x{xL:.2f}", ((Tc - Ttgt) / sig) if Tc else vf.PENALTY,
            f"{Tc:.0f}/{Ttgt:.0f}" if Tc else "none")

    # mixing enthalpy
    for d in ds.DH_MIX:
        add(f"dHmix@x{d['x']:.2f}", (dh_mix(db, p, d["x"]) - d["value"]) / d["sig"],
            f"{dh_mix(db,p,d['x']):.1f}/{d['value']:.1f}")

    return (np.asarray(out, float), rows) if detail else np.asarray(out, float)


def fit(p0):
    vf.RES = vf.FAST
    n = [0]
    def fun(pp):
        n[0] += 1
        res = residuals(pp)
        print(f"  eval {n[0]:3d}  cost={0.5*float(res@res):8.3f}")
        return res
    xs = []
    for _ in QPOW:
        xs += [3e5, 1e2]
    xs += [10.0, 2000.0, 2000.0]              # solid-param scales
    sol = least_squares(fun, p0, diff_step=0.03, max_nfev=400, x_scale=xs,
                        bounds=(LOWER, UPPER))
    return sol.x


def report(pp, write=False):
    vf.RES = vf.FINE
    res, rows = residuals(pp, detail=True)
    print("\n  per-datum residuals (model/target):")
    for tag, rr, info in rows:
        print(f"    {tag:26s} {info:14s}  r={rr:+6.2f}")
    print(f"\n  total cost = {0.5*float(res@res):.3f}   RMS residual = {np.sqrt(np.mean(res**2)):.2f}")
    if write:
        _, _, excess = build_db(pp)
        (HERE.parent / "MgO-SiO2-liquid.dat").write_text(
            bd.build(excess, version="assess"), encoding="ascii")
        print("  wrote MgO-SiO2-liquid.dat")


if __name__ == "__main__":
    # start from the first-pass liquid result + solids at their measured values
    # (dCp_fus=0, forsterite -60250, enstatite -36860).
    p0 = [-44468.8, -1.6, -50864.2, -0.3, 1448.2, -0.7, 116056.4, -10.8, -1177.5, -0.3,
          0.0, -60250.0, -36860.0]
    pp = fit(p0) if "--fit" in sys.argv else p0
    report(pp, write=("--write" in sys.argv))
    print("\n  params:", [round(float(x), 1) for x in pp])
