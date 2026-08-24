"""FeO-SiO2 solid Gibbs functions + liquid-vs-solid machinery for the v0.2 fit.

Mirrors data/mgo-sio2/phase_diagram.py. The only compound the v0.2 fit needs is fayalite
(Fe2SiO4), whose CONGRUENT melting (1478 K, Bowen & Schairer 1932) anchors the excess
entropy. Solid Gibbs is Neumann-Kopp on the engine's own FeO and SiO2(cristobalite) solid
endmembers plus fayalite's enthalpy and entropy of formation from the oxides:

    G_fayalite(T) = 2 G_FeO_solid(T) + G_SiO2_solid(T) + dHf_ox - T*dSf_ox
    dSf_ox = S298_fayalite - 2 S298_FeO - S298_SiO2      (per formula)

with dHf_ox derived from the open standard enthalpies (fayalite R&H 1995, FeO JANAF,
SiO2 cristobalite) - all adopted-evaluated single-substance values. Neumann-Kopp
(dCp_ox = 0) is the standard silicate approximation; solid polymorph transitions are not
resolved. Energies per mole of oxide formula unit, so solid and liquid share the x-G axes.
"""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "python"))

import build_dat as bd
import _activity as act

T0 = 298.15
COMPONENTS = ["FE", "SI", "O"]
S298_FEO, S298_SIO2 = bd.OXIDES["FeO"]["S298"], bd.OXIDES["SiO2"]["S298"]

# fayalite Fe2SiO4, S298 = 151.0 J/mol/K (Robie-Hemingway 1995 / NEA iron 2013).
S298_FAYALITE = 151.0
# dHf of fayalite from the oxides (cristobalite basis), from the open standard enthalpies:
#   dHf_ox = dHf(fayalite, elements) - 2 dHf(FeO) - dHf(SiO2)
#          = -1478.2 - 2(-272.044) - (-908.4) kJ/mol = -25.71 kJ/mol.
DHF_FAYALITE_ELEM = -1478200.0  # R&H 1995 (NEA iron 2013: -1476.8; within ~1.4 kJ)
DHF_OX_FAYALITE = DHF_FAYALITE_ELEM - 2 * bd.OXIDES["FeO"]["dHf"] - bd.OXIDES["SiO2"]["dHf"]


def solid_oxide_gibbs(ox, T):
    """Pure solid oxide Gibbs per formula (H - T*S from the Haas-Fisher Cp = a+bT+cT^-2)."""
    a, b, c = ox["a"], ox["b"], ox["c"]
    H = ox["dHf"] + a * (T - T0) + 0.5 * b * (T * T - T0 * T0) - c * (1.0 / T - 1.0 / T0)
    S = (ox["S298"] + a * np.log(T / T0) + b * (T - T0)
         - 0.5 * c * (1.0 / (T * T) - 1.0 / (T0 * T0)))
    return H - T * S


# name -> (n_FeO, n_SiO2, dHf_ox[J/mol], S298[J/mol/K])
SOLIDS = {
    "Fa(fayalite)": (2, 1, DHF_OX_FAYALITE, S298_FAYALITE),
}


def solid_gibbs_per_formula_unit(name, T):
    """Solid Gibbs per mole of OXIDE FORMULA UNIT and its x_SiO2."""
    n_feo, n_sio2, dHf_ox, S298 = SOLIDS[name]
    nunits = n_feo + n_sio2
    x = n_sio2 / nunits
    dSf_ox = S298 - n_feo * S298_FEO - n_sio2 * S298_SIO2
    g = (n_feo * solid_oxide_gibbs(bd.OXIDES["FeO"], T)
         + n_sio2 * solid_oxide_gibbs(bd.OXIDES["SiO2"], T)
         + dHf_ox - T * dSf_ox)
    return g / nunits, x


def liquid_gibbs_per_formula_unit(inp, x, T):
    """Absolute liquid Gibbs per mole of oxide formula unit at x_SiO2."""
    g_feo = act.g_pure_liquid(inp, "FeO")
    g_sio2 = act.g_pure_liquid(inp, "SiO2")
    return act.delta_g_mix(inp, x) + (1 - x) * g_feo + x * g_sio2
