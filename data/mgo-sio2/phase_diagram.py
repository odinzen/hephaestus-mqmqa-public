"""MgO-SiO2 solid Gibbs functions + liquid-vs-solid machinery for the v0.2 fit.

Mirrors data/cao-sio2/phase_diagram.py. The stable state at each (composition,
temperature) is the lower convex hull of the liquid G(x) curve - from the MQMQA
engine - together with the fixed-composition solid oxides and Mg-silicates.

Solid Gibbs energies are built by Neumann-Kopp on our OWN MgO and SiO2(cristobalite)
solid endmembers plus each compound's measured enthalpy and entropy of formation from
the oxides, so every solid sits on exactly the engine's endmember scale:

    G_compound(T) = n_MgO * G_MgO_solid(T) + n_SiO2 * G_SiO2_solid(T)
                    + dHf_ox - T * dSf_ox
    dSf_ox = S298_compound - n_MgO*S298_MgO - n_SiO2*S298_SiO2      (per formula)

with dHf_ox on the cristobalite reference (Charlu-Newton-Kleppa report it vs
alpha-quartz; the small quartz->cristobalite enthalpy shift converts it). Neumann-Kopp
(dCp_ox = 0) is the standard, good approximation for silicate compounds; solid-solid
polymorph transitions are not resolved (a documented refinement).

Open sources (all measured/evaluated, no TDB parameters):
  - MgO, SiO2 endmembers: as in build_dat.py (CODATA, NIST-JANAF, Robie-Hemingway 1995).
  - Compound dHf_ox(298), measured: Charlu, Newton & Kleppa (1975), Geochim.
    Cosmochim. Acta 39, 1487 (high-T oxide-melt solution calorimetry): forsterite
    Mg2SiO4 -60.25, enstatite MgSiO3 -36.86 kJ/mol from the oxides.
  - Compound S298: Robie-Hemingway 1995 / Robie et al. 1982 (forsterite 94.11,
    enstatite 66.27 J/mol/K; periclase 26.95, cristobalite 43.4).
  - Published invariants for validation: forsterite congruent melting 2163 K,
    periclase-forsterite eutectic 2123 K (Bowen & Andersen 1914); enstatite peritectic
    ~1830 K (evaluated). Greig 1927 silica-rich miscibility gap deferred to v0.4.
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "python"))

import mqmqa
from mqmqa import equilibrium as eq
import build_dat as bd
import _activity as act

T0 = 298.15
COMPONENTS = ["MG", "SI", "O"]
S298_MGO, S298_SIO2 = bd.OXIDES["MgO"]["S298"], bd.OXIDES["SiO2"]["S298"]

# alpha-quartz -> cristobalite enthalpy shift (our SiO2 endmember is cristobalite;
# Charlu-Newton-Kleppa dHf_ox is vs alpha-quartz). dHf(cristobalite) - dHf(quartz)
# ~ +2300 J/mol (R&H 1995: -908400 vs -910700), so forming a compound from
# cristobalite releases 2300 J/mol-SiO2 more heat.
DHF_QZ_TO_CRIST = -2300.0


def solid_oxide_gibbs(ox, T):
    """Pure solid oxide Gibbs per formula unit (H - T*S from the R&H/JANAF Cp)."""
    a, b, c = ox["a"], ox["b"], ox["c"]
    H = ox["dHf"] + a * (T - T0) + 0.5 * b * (T * T - T0 * T0) - c * (1.0 / T - 1.0 / T0)
    S = (ox["S298"] + a * np.log(T / T0) + b * (T - T0)
         - 0.5 * c * (1.0 / (T * T) - 1.0 / (T0 * T0)))
    return H - T * S


# Solid phases: name -> (n_MgO, n_SiO2, dHf_ox_quartz[J/mol], S298[J/mol/K], note).
# x_SiO2 of the compound = n_SiO2 / (n_MgO + n_SiO2); formula units = n_MgO + n_SiO2.
SOLIDS = {
    "MgO(periclase)":       (1, 0,       0.0,  S298_MGO,  "endmember"),
    "SiO2(cristobalite)":   (0, 1,       0.0,  S298_SIO2, "endmember"),
    "M2S(forsterite)":      (2, 1,  -60250.0,  94.11, "Mg2SiO4; congruent melt 2163 K"),
    "MS(enstatite)":        (1, 1,  -36860.0,  66.27, "MgSiO3 orthoenstatite; peritectic"),
}


def solid_gibbs_per_formula_unit(name, T):
    """Solid Gibbs per mole of OXIDE FORMULA UNIT (so it plots on the same x-G axes
    as the liquid), and its x_SiO2."""
    n_mgo, n_sio2, dHf_ox_qz, S298, _ = SOLIDS[name]
    nunits = n_mgo + n_sio2
    x = n_sio2 / nunits
    dHf_ox = dHf_ox_qz + DHF_QZ_TO_CRIST * n_sio2  # to cristobalite reference
    dSf_ox = S298 - n_mgo * S298_MGO - n_sio2 * S298_SIO2
    g = (n_mgo * solid_oxide_gibbs(bd.OXIDES["MgO"], T)
         + n_sio2 * solid_oxide_gibbs(bd.OXIDES["SiO2"], T)
         + dHf_ox - T * dSf_ox)
    return g / nunits, x


def liquid_gibbs_per_formula_unit(inp, x, T):
    """Absolute liquid Gibbs per mole of oxide formula unit at x_SiO2."""
    g_mgo = act.g_pure_liquid(inp, "MgO")
    g_sio2 = act.g_pure_liquid(inp, "SiO2")
    return act.delta_g_mix(inp, x) + (1 - x) * g_mgo + x * g_sio2


def _load():
    db = mqmqa.Database.read(str(HERE / "MgO-SiO2-liquid.dat"))
    p = db.phase_index("MGO-SIO2-LIQUID")
    return db, p


def congruent_melting(db, p, name, set_L=None, T_lo=1400.0, T_hi=2600.0):
    """T where liquid at the compound composition equals the solid (bisection on
    G_liq - G_solid, both per formula unit). inp is rebuilt at each T so the pure
    endmember Gibbs energies (baked at build time) stay consistent; set_L(inp, T)
    injects the excess coefficients evaluated at T, if given."""
    _n_mgo, n_sio2, _, _, _ = SOLIDS[name]
    x = n_sio2 / (SOLIDS[name][0] + n_sio2)

    def f(T):
        inp = eq.build_inputs(db, p, T, components=COMPONENTS)
        if set_L is not None:
            set_L(inp, T)
        gs, _ = solid_gibbs_per_formula_unit(name, T)
        return liquid_gibbs_per_formula_unit(inp, x, T) - gs

    lo, hi = T_lo, T_hi
    if f(lo) * f(hi) > 0:
        return None
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        (lo, hi) = (mid, hi) if f(lo) * f(mid) > 0 else (lo, mid)
    return 0.5 * (lo + hi)


if __name__ == "__main__":
    db, p = _load()
    print("Solid phases and their compositions:")
    for name, (nm, ns, dHfq, S, note) in SOLIDS.items():
        x = ns / (nm + ns)
        print(f"  {name:20s} x_SiO2={x:.3f}  dHf_ox(qz)={dHfq:9.0f}  S298={S:6.1f}  [{note}]")
    print("\nCongruent-melting check (needs the fitted liquid; ideal v0.1 will be off):")
    for name in ("M2S(forsterite)", "MS(enstatite)"):
        Tm = congruent_melting(db, p, name)
        print(f"  {name:18s} congruent T = {Tm:.0f} K" if Tm else f"  {name}: none in range")
