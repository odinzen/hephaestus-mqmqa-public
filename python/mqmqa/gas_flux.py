"""Couple a molten chloride flux to its furnace vapour through component activities.

A salt cover fumes because its own components evaporate. The partial pressure of each salt
over the melt is its activity times its pure-liquid vapour pressure,

    p_i = a_i(melt) * p_i^o(T),

so the fume needs two things: the pure-component vapour pressures (measured data) and the
melt activities (the engine's job). This module supplies both for the NaCl-KCl-MgCl2 flux.

Activities. a_i is a dimensionless ratio, the partial molar Gibbs of component i in the melt
minus the pure-liquid endmember, both from the same MQMQA model, so it carries no
reference-frame ambiguity (unlike an absolute vapour pressure, which mixes a condensed and a
gas dataset). It is computed on the robust C equilibrium solver (nullspace projection so the
composition is met exactly, then Nelder-Mead), differenced against composition. Validated: the
pure limit gives unit activity to five figures, and the NaCl-KCl binary reproduces the measured
small negative deviations from ideality (gamma ~ 0.89 at equimolar, tending to 1 at the edges).
The physical payoff is MgCl2: in the flux its activity sits far below its mole fraction because
chlorocomplexing holds it in the melt, so the fume is alkali-chloride rich even though a fifth
of the flux is magnesium.

Pure-component vapour pressures. NaCl and KCl are NIST WebBook Antoine fits (Stull 1947); MgCl2
is from the NIST-JANAF gas and liquid Gibbs of formation (Chase 1998). Each reproduces its
measured normal boiling point to about 0.3 percent.
"""
from __future__ import annotations

import math
import os

import mqmqa
from mqmqa import equilibrium as eq
from mqmqa._abi import c_equilibrate

R = 8.314462618

# Components and their element content; _ATOMS is atoms per formula unit.
COMPONENTS = {"NaCl": {"NA": 1, "CL": 1}, "KCl": {"K": 1, "CL": 1}, "MgCl2": {"MG": 1, "CL": 2}}
_ATOMS = {"NaCl": 2, "KCl": 2, "MgCl2": 3}

# Pure-liquid vapour pressure, measured. log10(p/bar) = A - B/(T+C), NIST WebBook (Stull 1947).
_ANTOINE = {"NaCl": (5.07184, 8388.497, -82.638), "KCl": (4.78236, 7440.691, -122.709)}

# MgCl2 has no simple Antoine fit at these temperatures; take its vaporisation Gibbs from the
# NIST-JANAF gas and liquid Gibbs of formation (kJ/mol) on a 100 K grid. p^o = exp(-dGvap/RT).
_MGCL2_DFG = {           # T: (dfG gas Cl-096, dfG liquid Cl-094)
    1000: (-411.422, -482.642), 1100: (-412.074, -471.331), 1200: (-412.636, -460.204),
    1300: (-413.113, -449.244), 1400: (-410.346, -435.271),
}


def _interp_mgcl2(T):
    ks = sorted(_MGCL2_DFG)
    if T <= ks[0]:
        return _MGCL2_DFG[ks[0]]
    if T >= ks[-1]:
        return _MGCL2_DFG[ks[-1]]
    for i in range(len(ks) - 1):
        if T <= ks[i + 1]:
            f = (T - ks[i]) / (ks[i + 1] - ks[i])
            a, b = _MGCL2_DFG[ks[i]], _MGCL2_DFG[ks[i + 1]]
            return a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])


def pure_vapor_pressure(salt, T):
    """Vapour pressure (bar) of the pure liquid salt at T (K), from measured data."""
    if salt in _ANTOINE:
        A, B, C = _ANTOINE[salt]
        return 10.0 ** (A - B / (T + C))
    if salt == "MgCl2":
        g, ell = _interp_mgcl2(T)
        return math.exp(-(g - ell) * 1000.0 / (R * T))
    raise KeyError(salt)


def _default_db():
    return os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..",
                                         "data", "nacl-kcl-mgcl2", "NaCl-KCl-MgCl2.dat"))


def salt_activities(T, composition, db=None, h=0.01):
    """Liquid-referenced activities of each salt component in a molten chloride flux.

    composition maps component name (NaCl, KCl, MgCl2) to mole fraction. Only components with a
    positive fraction enter the model; the model is built on that subsystem so a component held
    at exactly zero cannot destabilise the solve. Returns {component: activity}.
    """
    database = mqmqa.Database.read(db or _default_db())
    present = [s for s in COMPONENTS if composition.get(s, 0.0) > 0.0]
    elems = sorted({e for s in present for e in COMPONENTS[s]})
    inp = eq.build_inputs(database, 0, T, components=elems)
    n = {s: composition[s] for s in present}

    def gtot(nn):
        els = {}
        for s, ni in nn.items():
            if ni <= 1e-14:
                continue
            for e, c in COMPONENTS[s].items():
                els[e] = els.get(e, 0.0) + c * ni
        atoms = sum(_ATOMS[s] * ni for s, ni in nn.items() if ni > 1e-14)
        return c_equilibrate(inp, els)["GM"] * atoms

    def mu_pure(s):
        sub = eq.build_inputs(database, 0, T, components=list(COMPONENTS[s]))
        gm = eq.gibbs_per_quad(sub, [1.0]) / sum(eq.element_moles(sub, [1.0]).values())
        return gm * _ATOMS[s]

    out = {}
    for s in present:
        up, dn = dict(n), dict(n)
        up[s] += h
        dn[s] -= h
        mu = (gtot(up) - gtot(dn)) / (2.0 * h)          # partial molar Gibbs of component s
        out[s] = math.exp((mu - mu_pure(s)) / (R * T))
    return out


def flux_vapor(T, composition, db=None):
    """Partial pressures (bar) of each salt over the flux, p_i = a_i * p_i^o, and the total.

    Couples the engine's validated component activities to the measured pure-component vapour
    pressures. Returns {component: p_i, ..., 'total': sum}.
    """
    a = salt_activities(T, composition, db)
    out = {s: a[s] * pure_vapor_pressure(s, T) for s in a}
    out["total"] = sum(out.values())
    return out
