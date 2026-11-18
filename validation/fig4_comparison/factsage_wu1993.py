"""The FeO-MgO-SiO2 ternary peritectic of the shipped database against Wu, Eriksson, Pelton and
Blander, ISIJ Int. 33 (1993) 26-35, the FactSage-lineage assessment of this system, and against
the measurement it quotes (Bowen and Schairer 1935).

Wu et al. state in their text the calculated peritectic, liquid + olivine + pyroxene + tridymite
at 1310 degC (1583 K), liquid 10.5 wt% MgO, 45 FeO, 44.5 SiO2, olivine 61 wt% Fe2SiO4,
pyroxene 50 wt% FeSiO3, against the measured 1306 degC (1579 K), 9/46/45, 68 and 62. Their
Table 3 lists the olivine solidus along the Mg2SiO4-Fe2SiO4 join, measured and calculated.

Here the peritectic is the liquid composition and temperature at which olivine,
orthopyroxene and silica all have zero driving force. The liquid is the lower of the two
codes' liquid-only equilibria; the solids' energies come from pycalphad (dense sampling). The
database has no tridymite, so silica is cristobalite.

    python validation/fig4_comparison/factsage_wu1993.py
"""
import json
import sys
import warnings
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "python"))
DAT = ROOT / "data" / "feo-mgo-sio2" / "FeO-MgO-SiO2-combined.dat"
OUT = HERE / "factsage_wu1993.json"
LIQ = "FEO-MGO-SIO2-LIQUID"
SOLIDS = ["OLIVINE", "ORTHOPYROXENE", "CRISTOBALITE"]
ALL = [LIQ, "OLIVINE", "ORTHOPYROXENE", "MAGNESIOWUSTITE", "CRISTOBALITE"]
COMPS = ["FE", "MG", "SI", "O"]
M = {"FeO": 71.844, "MgO": 40.304, "SiO2": 60.084, "Fe2SiO4": 203.771, "Mg2SiO4": 140.693,
     "FeSiO3": 131.928, "MgSiO3": 100.388}
PDENS = 2000

WU = {"T_K": 1583.15, "liquid_wt": {"MgO": 10.5, "FeO": 45.0, "SiO2": 44.5},
      "olivine_wt_Fe2SiO4": 61.0, "pyroxene_wt_FeSiO3": 50.0}
MEASURED = {"T_K": 1579.15, "liquid_wt": {"MgO": 9.0, "FeO": 46.0, "SiO2": 45.0},
            "olivine_wt_Fe2SiO4": 68.0, "pyroxene_wt_FeSiO3": 62.0}
# Wu et al. Table 3: olivine solidus on the join, degC and wt% Fe2SiO4
SOLIDUS_C = [1495, 1465, 1440, 1410, 1318, 1276]
SOLIDUS_EXP = [41, 45, 47.5, 54, 70, 80]
SOLIDUS_WU = [40.5, 45, 49, 54, 71.5, 81]

warnings.filterwarnings("ignore")
import mqmqa                                                    # noqa: E402
from mqmqa import gem                                           # noqa: E402
from pycalphad import Database, calculate, equilibrium, variables as v   # noqa: E402

dbf = Database(str(DAT))
db = mqmqa.Database.read(str(DAT))


def cations_from_wt(wt):
    n = {"FE": wt["FeO"] / M["FeO"], "MG": wt["MgO"] / M["MgO"], "SI": wt["SiO2"] / M["SiO2"]}
    s = sum(n.values())
    return n["FE"] / s, n["SI"] / s


def wt_from_cations(x_fe, x_si):
    x_mg = 1 - x_fe - x_si
    w = {"MgO": x_mg * M["MgO"], "FeO": x_fe * M["FeO"], "SiO2": x_si * M["SiO2"]}
    s = sum(w.values())
    return {k: 100 * w[k] / s for k in w}


def liquid_mu(x_fe, x_si, T):
    """Chemical potentials of the lower of the two codes' liquid-only states. gem sets mu_O to
    zero; every phase here is charge balanced, so the tangent plane is the same in either gauge."""
    x_mg = 1 - x_fe - x_si
    tot = 1 + x_fe + x_mg + 2 * x_si
    eq = equilibrium(dbf, COMPS, [LIQ], {v.T: T, v.P: 1e5, v.N: 1, v.X("FE"): x_fe / tot,
                                         v.X("MG"): x_mg / tot, v.X("SI"): x_si / tot},
                     calc_opts={"pdens": PDENS})
    mu_p = dict(zip(eq.component.values.astype(str), eq.MU.values.ravel()))
    g_p = float(eq.GM.values.squeeze())
    b = {"FE": x_fe / tot, "MG": x_mg / tot, "SI": x_si / tot, "O": (x_fe + x_mg + 2 * x_si) / tot}
    try:
        r = gem.equilibrium(db, T, b, suspend=ALL[1:])
    except RuntimeError:
        return mu_p
    if r.G < g_p:
        return {"O": 0.0} | {e.upper(): u for e, u in r.mu.items()}
    return mu_p


_solid_cache = {}


def solid_points(phase, T):
    key = (phase, round(T, 6))
    if key not in _solid_cache:
        c = calculate(dbf, COMPS, phase, T=T, P=1e5, N=1, pdens=PDENS, output="GM")
        X = c.X.values.reshape(-1, len(c.component))
        order = [list(c.component.values.astype(str)).index(e) for e in COMPS]
        _solid_cache[key] = (X[:, order], c.GM.values.ravel())
    return _solid_cache[key]


def driving(phase, mu, T):
    """Largest mu.x - G of the phase (J per mole of atoms) and the composition giving it."""
    X, G = solid_points(phase, T)
    f = X @ np.array([mu[e] for e in COMPS]) - G
    k = int(np.nanargmax(f))
    return float(f[k]), X[k]


def residual(z):
    x_fe, x_si, T = z
    mu = liquid_mu(x_fe, x_si, T)
    return np.array([driving(p, mu, T)[0] for p in SOLIDS])


def fe_fraction(X):
    return X[0] / (X[0] + X[1])


def peritectic():
    from scipy.optimize import least_squares
    x_fe, x_si = cations_from_wt(WU["liquid_wt"])
    sol = least_squares(residual, [x_fe, x_si, WU["T_K"]], bounds=([0.05, 0.3, 1450], [0.8, 0.6, 1750]),
                        x_scale=[0.01, 0.01, 5.0], diff_step=[1e-4, 1e-4, 1e-5], xtol=1e-10, ftol=1e-10)
    z = sol.x
    ier = int(np.max(np.abs(sol.fun)) < 0.5)
    res = residual(z)
    mu = liquid_mu(*z)
    y_ol = fe_fraction(driving("OLIVINE", mu, z[2])[1])
    y_px = fe_fraction(driving("ORTHOPYROXENE", mu, z[2])[1])
    wt_ol = 100 * y_ol * M["Fe2SiO4"] / (y_ol * M["Fe2SiO4"] + (1 - y_ol) * M["Mg2SiO4"])
    wt_px = 100 * y_px * M["FeSiO3"] / (y_px * M["FeSiO3"] + (1 - y_px) * M["MgSiO3"])
    return {"T_K": float(z[2]), "liquid_wt": wt_from_cations(z[0], z[1]),
            "olivine_wt_Fe2SiO4": wt_ol, "pyroxene_wt_FeSiO3": wt_px,
            "residual_J": res.tolist(), "converged": bool(ier == 1)}


def solidus_on_join(T):
    """wt% Fe2SiO4 of the olivine on the solidus at T: the olivine on the join whose
    composition the coexisting liquid shares (a true quasibinary, as Wu et al. note), found
    where the olivine-liquid equilibrium of a join bulk first leaves a liquid."""
    from scipy.optimize import brentq

    def melt(y):                       # liquid fraction of the join bulk (Fe,Mg)2SiO4 at T
        b = {"FE": 2 * y / 7, "MG": 2 * (1 - y) / 7, "SI": 1 / 7, "O": 4 / 7}
        r = gem.equilibrium(db, T, b)
        return sum(s.amount for s in r.sets if s.phase == LIQ)

    ys = np.linspace(0.02, 0.98, 49)
    f = [melt(y) for y in ys]
    k = next((i for i in range(len(ys)) if f[i] > 1e-6), None)
    if k is None or k == 0:
        return float("nan")
    y = brentq(lambda y: melt(y) - 1e-6, ys[k - 1], ys[k], xtol=1e-5)
    return 100 * y * M["Fe2SiO4"] / (y * M["Fe2SiO4"] + (1 - y) * M["Mg2SiO4"])


def solidus_T(wt_fe2sio4, lo=1300.0, hi=1950.0):
    """Temperature (K) at which olivine of this composition on the join first melts."""
    from scipy.optimize import brentq
    a = wt_fe2sio4 / M["Fe2SiO4"]
    y = a / (a + (100 - wt_fe2sio4) / M["Mg2SiO4"])
    b = {"FE": 2 * y / 7, "MG": 2 * (1 - y) / 7, "SI": 1 / 7, "O": 4 / 7}

    def melt(T):
        r = gem.equilibrium(db, T, b)
        return sum(s.amount for s in r.sets if s.phase == LIQ) - 1e-6

    return brentq(melt, lo, hi, xtol=0.01)


def main():
    out = {"wu1993_calculated": WU, "bowen_schairer_measured": MEASURED, "this_database": peritectic()}
    sol = [solidus_on_join(c + 273.15) for c in SOLIDUS_C]
    out["olivine_solidus_wt_Fe2SiO4"] = [
        {"T_C": c, "measured": e, "wu1993": w, "this_database": round(s, 1),
         "this_database_solidus_T_minus_measured_K": round(solidus_T(e) - (c + 273.15), 1)}
        for c, e, w, s in zip(SOLIDUS_C, SOLIDUS_EXP, SOLIDUS_WU, sol)]
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
