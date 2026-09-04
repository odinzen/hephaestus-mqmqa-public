"""Ideal-gas thermochemistry and equilibrium from NASA 7-coefficient polynomials.

The combustion school ships its data as NASA/CHEMKIN thermo.dat cards, a genuinely
open format (NASA CEA, Burcat, GRI-Mech). This module reads those cards, evaluates the
standard-state Gibbs energy of each species, and finds the ideal-gas equilibrium at a
fixed temperature and pressure by the element-potential (RAND/CEA) method. Cantera is
the validation oracle, exactly as pycalphad is for the condensed phases.

Standard-state reference pressure is 1 atm (101325 Pa), matching the NASA polynomials.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

R = 8.314462618          # J/mol-K
P_REF = 101325.0         # Pa, NASA standard state (1 atm)


@dataclass
class GasSpecies:
    name: str
    comp: dict            # element -> atom count
    t_lo: float
    t_mid: float
    t_hi: float
    low: np.ndarray       # 7 coefficients, valid t_lo..t_mid
    high: np.ndarray      # 7 coefficients, valid t_mid..t_hi

    def g_rt(self, T: float) -> float:
        """Standard-state Gibbs energy over RT, G deg(T) / RT."""
        a = self.low if T < self.t_mid else self.high
        h_rt = (a[0] + a[1] * T / 2 + a[2] * T**2 / 3 + a[3] * T**3 / 4
                + a[4] * T**4 / 5 + a[5] / T)
        s_r = (a[0] * math.log(T) + a[1] * T + a[2] * T**2 / 2
               + a[3] * T**3 / 3 + a[4] * T**4 / 4 + a[6])
        return h_rt - s_r


def _floats(line: str, n: int):
    # NASA cards pack 5 x 15-char scientific-notation fields per data line
    return [float(line[i:i + 15]) for i in range(0, 15 * n, 15)]


def _parse_comp(field: str) -> dict:
    comp = {}
    for i in range(0, 20, 5):
        el = field[i:i + 2].strip()
        num = field[i + 2:i + 5].strip()
        if el and num and num not in ("0", "0.", "00"):
            try:
                c = int(float(num))
            except ValueError:
                continue
            if c:
                comp[el] = comp.get(el, 0) + c
    return comp


def read_nasa_thermo(path: str) -> dict:
    """Parse a NASA/CHEMKIN thermo.dat file into {name: GasSpecies}."""
    with open(path, encoding="utf-8") as fh:
        lines = [ln.rstrip("\n") for ln in fh]
    species = {}
    i = 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip() or ln.strip().upper().startswith(("THERMO", "END")):
            i += 1
            continue
        # species header card: name in column 1, the "1" line-number tag last, and
        # three parseable temperatures in columns 46-73
        if ln[:1].strip() and ln.rstrip()[-1:] == "1" and len(ln) >= 73:
            name = ln[:18].split()[0]
            comp = _parse_comp(ln[24:44])
            t_lo, t_hi, t_mid = float(ln[45:55]), float(ln[55:65]), float(ln[65:73])
            hi = _floats(lines[i + 1], 5) + _floats(lines[i + 2], 5)[:2]
            lo = _floats(lines[i + 2], 5)[2:] + _floats(lines[i + 3], 4)
            species[name] = GasSpecies(name, comp, t_lo, t_mid, t_hi,
                                       np.array(lo), np.array(hi))
            i += 4
        else:
            i += 1
    return species


def gas_equilibrium(species: dict, names, T: float, P: float, elem_moles: dict,
                    p_ref: float = P_REF):
    """Ideal-gas equilibrium mole fractions at fixed T and P.

    Element-potential (RAND/CEA) Newton on the element balance, with an outer
    fixed point on total moles for the pressure term. Returns {species: X}.
    """
    # every element the candidate species span must appear, so a species built
    # from an element that is not fed (b_e = 0) is driven to zero by its balance
    els = list(elem_moles.keys())
    for s in names:
        for e in species[s].comp:
            if e not in els:
                els.append(e)
    A = np.array([[species[s].comp.get(e, 0.0) for e in els] for s in names])
    b = np.array([elem_moles.get(e, 0.0) for e in els], float)
    g_rt = np.array([species[s].g_rt(T) for s in names])
    xt = max(b.sum(), 1e-12)
    pi = np.zeros(len(els))
    for _ in range(200):
        c = g_rt + math.log(P / p_ref) - math.log(xt)
        for _ in range(100):
            x = np.exp(np.clip(A @ pi - c, -80, 80))
            resid = A.T @ x - b
            if np.max(np.abs(resid)) < 1e-13 * max(1.0, b.sum()):
                break
            jac = A.T @ (x[:, None] * A)
            step = np.linalg.solve(jac + 1e-14 * np.eye(len(els)), -resid)
            pi = pi + np.clip(step, -2.0, 2.0)
        xt_new = x.sum()
        if abs(xt_new - xt) < 1e-12 * xt:
            break
        xt = xt_new
    x = np.exp(np.clip(A @ pi - (g_rt + math.log(P / p_ref) - math.log(xt)), -80, 80))
    return dict(zip(names, x / x.sum()))
