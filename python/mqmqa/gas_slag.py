"""Couple a furnace gas to the MQMQA solution slag through the iron-saturated oxygen potential.

The stoichiometric coupling in gas.py holds the gas in equilibrium with pure condensed metals
and oxides. A real slag is a solution: its FeO carries an activity below one, so the atmosphere
it sits under is not the pure Fe/FeO buffer but that buffer shifted by the slag's own FeO
activity. This module closes that loop.

The physics, for a slag held at iron saturation (the classic slag-gas equilibration): the melt,
metallic iron and the gas share one oxygen potential, set by

    1/2 O2(gas) + Fe(l) = FeO(in slag),   mu_O = mu_FeO(slag) - mu_Fe(l),

and mu_FeO(slag) = G_FeO(l) + RT ln a_FeO with a_FeO the slag's FeO activity on the liquid
reference. The activity is a pure ratio from the MQMQA model (validated against the measured
iron-saturated activities the database was fitted to), so the coupling stays in one reference
frame: the liquid FeO and Fe endmembers and the gas species, all NASA-referenced, plus a
dimensionless activity. The equilibrium gas ratio follows from CO2 = CO + O:

    CO2/CO = exp(g_CO(T) - g_CO2(T) + mu_O/RT).

A more silica-rich (lower a_FeO) slag therefore needs a more reducing gas to stay iron
saturated, exactly as measured. The pure-FeO limit (a_FeO -> 1) recovers the Fe/FeO buffer,
which agrees with Cantera's own multiphase equilibrium to under a percent.

Valid where both endmembers are liquid, about 1809 K upward (the steelmaking range); below that
the corresponding solid endmembers apply.
"""
from __future__ import annotations

import math
import os

from mqmqa.gas import read_nasa_thermo

R = 8.314462618

# Liquid endmember standard-state Gibbs over RT, from the NASA condensed database (NASA7, single
# interval each). Read, not fitted; the same values Cantera carries. FeO(l) valid >= 1650 K,
# Fe(l) >= 1809 K.
_FEO_L = [8.2022482, 0.0, 0.0, 0.0, 0.0, -33848.615, -40.079129]
_FE_L = [5.53538332, 0.0, 0.0, 0.0, 0.0, -1274.28941, -29.4772271]


def _nasa7_grt(a, T):
    h = a[0] + a[1] * T / 2 + a[2] * T**2 / 3 + a[3] * T**3 / 4 + a[4] * T**4 / 5 + a[5] / T
    s = a[0] * math.log(T) + a[1] * T + a[2] * T**2 / 2 + a[3] * T**3 / 3 + a[4] * T**4 / 4 + a[6]
    return h - s


def feo_liquid_grt(T):
    return _nasa7_grt(_FEO_L, T)


def fe_liquid_grt(T):
    return _nasa7_grt(_FE_L, T)


_GASDB = None


def _gasdb():
    global _GASDB
    if _GASDB is None:
        path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "gas", "nasa_gas.dat")
        _GASDB = read_nasa_thermo(os.path.normpath(path))
    return _GASDB


def oxygen_potential_iron_saturated(a_feo, T):
    """Oxygen chemical potential mu_O/RT of an iron-saturated slag whose FeO activity is a_feo."""
    return feo_liquid_grt(T) + math.log(a_feo) - fe_liquid_grt(T)


def gas_ratio_for_oxygen_potential(mu_o_rt, T, gasdb=None):
    """Equilibrium CO2/CO mole-fraction ratio of a gas at oxygen potential mu_o_rt (per O atom)."""
    g = gasdb or _gasdb()
    return math.exp(g["CO"].g_rt(T) - g["CO2"].g_rt(T) + mu_o_rt)


def log10_pO2_iron_saturated(a_feo, T, gasdb=None):
    """Base-10 log of the oxygen partial pressure (bar) of an iron-saturated slag of FeO activity
    a_feo. At a_feo = 1 this is the iron-wustite buffer; the pure-FeO value at 1873 K is about
    -8.6, in line with the measured buffer."""
    g = gasdb or _gasdb()
    return (2.0 * oxygen_potential_iron_saturated(a_feo, T) - g["O2"].g_rt(T)) / math.log(10.0)


def iron_saturated_gas_ratio(a_feo, T, gasdb=None):
    """CO2/CO ratio of the furnace gas in equilibrium with an iron-saturated slag of FeO activity
    a_feo, at T (K). The slag composition enters only through a_feo, so this couples any slag the
    MQMQA engine can evaluate to the atmosphere."""
    return gas_ratio_for_oxygen_potential(oxygen_potential_iron_saturated(a_feo, T), T, gasdb)


def feo_sio2_activity(T, x_sio2, dat_path=None):
    """FeO activity (liquid reference) of the shipped FeO-SiO2 slag at silica fraction x_sio2."""
    import mqmqa
    from mqmqa import equilibrium as eq
    from mqmqa.dbbuild import _binary_activity_solver
    if dat_path is None:
        dat_path = os.path.join(os.path.dirname(__file__), "..", "..",
                                "data", "feo-sio2", "FeO-SiO2-liquid.dat")
    db = mqmqa.Database.read(os.path.normpath(dat_path))
    inp = eq.build_inputs(db, 0, T)
    _, activities = _binary_activity_solver(inp, atoms_first=2, atoms_second=3)  # FeO, SiO2
    a_feo, _ = activities(x_sio2, T)
    return a_feo
