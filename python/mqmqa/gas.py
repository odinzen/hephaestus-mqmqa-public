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
from itertools import combinations

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
                    p_ref: float = P_REF, return_potentials: bool = False):
    """Ideal-gas equilibrium mole fractions at fixed T and P.

    Element-potential (RAND/CEA) Newton on the element balance, with an outer
    fixed point on total moles for the pressure term. Returns {species: X}; with
    return_potentials, also returns the element chemical potentials pi (mu_e / RT)
    as {element: value}, which drives the condensed active set in the coupled solver.
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
    tol = 1e-12 * max(1.0, b.sum())
    for _ in range(120):
        c = g_rt + math.log(P / p_ref) - math.log(xt)
        for _ in range(200):
            x = np.exp(np.clip(A @ pi - c, -80, 80))
            resid = A.T @ x - b
            if np.max(np.abs(resid)) < 1e-14 * max(1.0, b.sum()):
                break
            jac = A.T @ (x[:, None] * A)
            # ridge scaled to the diagonal so a trace element (near-zero row) does
            # not make the Gram singular; least squares as a final fallback
            ridge = 1e-10 * max(jac.diagonal().max(), 1.0)
            try:
                step = np.linalg.solve(jac + ridge * np.eye(len(els)), -resid)
            except np.linalg.LinAlgError:
                step = np.linalg.lstsq(jac, -resid, rcond=None)[0]
            pi = pi + np.clip(step, -2.0, 2.0)
        xt_new = x.sum()
        if abs(xt_new - xt) < 1e-12 * xt:
            break
        xt = xt_new
    x = np.exp(np.clip(A @ pi - (g_rt + math.log(P / p_ref) - math.log(xt)), -80, 80))
    frac = dict(zip(names, x / x.sum()))
    if return_potentials:
        return frac, dict(zip(els, pi))
    return frac


@dataclass
class Condensed:
    """A pure stoichiometric condensed species for the coupled solver: its element
    formula and its standard-state Gibbs energy over RT at the solve temperature.
    Pure condensed phases have unit activity and no pressure term, so mu/RT = g_rt."""
    name: str
    comp: dict               # element -> atom count
    g_rt: float              # G_deg(T) / RT at the solve temperature


def gas_condensed_equilibrium(species, gas_names, condensed, T, P, elem_moles,
                              p_ref=P_REF, max_outer=80, tol=1e-9):
    """Coupled ideal-gas + pure-condensed equilibrium at fixed T, P and element feed.

    One set of element potentials pi = mu_e/RT is shared between the gas and every condensed
    species, so gas and condensate settle to a common element potential, oxygen above all.
    For a given present set, a Newton solve enforces the element balance, the gas closure
    sum(X) = 1 and each present species on its saturation line a_k.pi = g_k, with pi the TRUE
    element potentials (mu_j/RT = a_j.pi) so the coupling is exact. The stable assemblage is
    then the one of lowest total Gibbs energy among the valid (non-negative, no supersaturated
    absentee) sets, found by enumerating condensed subsets up to the phase-rule limit for a
    small list, or a greedy start with single-toggle local search for a large one. This is the
    coupling the standalone gas and slag engines lacked (the Boudouard balance C(gr) + CO2 =
    2 CO, or iron-oxide reduction FeO + CO = Fe + CO2).

    condensed is a list of Condensed. Returns (gas_fractions, condensed_moles, pi) where
    condensed_moles maps only the present species to their moles and pi maps element -> mu/RT.
    """
    els = list(elem_moles.keys())
    for s in gas_names:
        for e in species[s].comp:
            if e not in els:
                els.append(e)
    for c in condensed:
        for e in c.comp:
            if e not in els:
                els.append(e)
    nE = len(els)
    Ag = np.array([[species[s].comp.get(e, 0.0) for e in els] for s in gas_names])
    gg = np.array([species[s].g_rt(T) for s in gas_names])
    b = np.array([elem_moles.get(e, 0.0) for e in els], float)
    Ac = (np.array([[c.comp.get(e, 0.0) for e in els] for c in condensed])
          if condensed else np.zeros((0, nE)))
    gc = np.array([c.g_rt for c in condensed]) if condensed else np.zeros(0)
    logP = math.log(P / p_ref)
    bscale = max(1.0, b.sum())

    def Xgas(pi):
        # gas mole fractions X_j = exp(a_j.pi - g_j - ln(P/P0)); this makes mu_j/RT = a_j.pi
        # exactly, so pi are the TRUE element potentials that the condensate must also share
        return np.exp(np.clip(Ag @ pi - gg - logP, -300, 300))

    def gibbs(pi, nt, nk, active):
        # total Gibbs over RT of a candidate assemblage, the arbiter between phase choices
        X = Xgas(pi)
        Xn = X / X.sum()
        gas_g = nt * np.sum(Xn * (gg + logP + np.log(np.clip(Xn, 1e-300, None))))
        cond_g = float(np.dot(nk, gc[active])) if active else 0.0
        return gas_g + cond_g

    def residual(pi, nt, nk, active):
        As = Ac[active] if active else np.zeros((0, nE))
        gca = gc[active] if active else np.zeros(0)
        X = Xgas(pi)
        Re = nt * (Ag.T @ X) + (As.T @ nk if active else 0.0) - b   # element balance
        R0 = X.sum() - 1.0                                          # gas closure sum X = 1
        Qk = (As @ pi - gca) if active else np.zeros(0)            # saturation lines
        return np.concatenate([Re, [R0], Qk])

    def solve_active(active, pi, nt):
        """Primal Newton over [pi, nt, condensed amounts] for the present set: element
        balance, the gas closure sum X = 1, and each present species on its saturation line
        a_k.pi = g_k. pi are the true element potentials, shared with the condensate, so the
        coupling (the Boudouard balance and the like) is exact. Backtracking keeps the gas
        fractions finite, nt positive and the residual falling."""
        m = len(active)
        As = Ac[active] if active else np.zeros((0, nE))
        nk = np.zeros(m)
        for _ in range(200):
            X = Xgas(pi)
            aX = Ag.T @ X                                # sum_j a_je X_j
            F = residual(pi, nt, nk, active)
            n = nE + 1 + m
            J = np.zeros((n, n))
            J[:nE, :nE] = nt * (Ag.T @ (X[:, None] * Ag))   # dRe/dpi
            J[:nE, nE] = aX                                  # dRe/dnt
            if m:
                J[:nE, nE + 1:] = As.T                       # dRe/dnk
                J[nE + 1:, :nE] = As                         # dQk/dpi
            J[nE, :nE] = aX                                  # dR0/dpi
            J[:nE, :nE] += 1e-12 * max(J[:nE, :nE].diagonal().max(), 1.0) * np.eye(nE)
            try:
                dz = np.linalg.solve(J, -F)
            except np.linalg.LinAlgError:
                dz = np.linalg.lstsq(J, -F, rcond=None)[0]
            f0 = np.max(np.abs(F))
            alpha = 1.0
            for _ in range(60):
                pin = pi + alpha * dz[:nE]
                ntn = nt + alpha * dz[nE]
                nkn = nk + alpha * dz[nE + 1:] if m else nk
                Fn = residual(pin, ntn, nkn, active)
                if ntn > 0 and np.all(np.isfinite(Fn)) and np.max(np.abs(Fn)) <= (1 - 1e-4 * alpha) * f0:
                    break
                alpha *= 0.5
            pi, nt = pi + alpha * dz[:nE], nt + alpha * dz[nE]
            if m:
                nk = nk + alpha * dz[nE + 1:]
            if np.max(np.abs(residual(pi, nt, nk, active))) < 1e-12 * bscale:
                break
        return pi, nt, nk

    # seed pi, nt from the gas-only equilibrium (its pi are already true element potentials);
    # a supersaturated feed just gives a starting point the active set then corrects
    try:
        _, pim = gas_equilibrium(species, gas_names, T, P, elem_moles, p_ref,
                                 return_potentials=True)
        pi_seed = np.array([pim.get(e, 0.0) for e in els])
    except Exception:
        pi_seed = np.zeros(nE)
    nt_seed = max(b.sum(), 1e-9)

    def evaluate(a):
        """Converge the candidate assemblage `a` from the neutral seed and return
        (pi, nt, nk, Gibbs) if it is a valid equilibrium (non-negative amounts, balance
        closed, saturation lines met), else None. Solving from the same seed each time
        keeps the choice of assemblage independent of the order they are tried in."""
        a = list(a)
        p, n_t, n_k = solve_active(a, pi_seed.copy(), nt_seed)
        if a and n_k.min() < -1e-7 * bscale:
            return None
        if np.max(np.abs(residual(p, n_t, n_k, a))) > 1e-6 * bscale:
            return None
        # an absent species must not be supersaturated at the solution (global optimality)
        drive = Ac @ p - gc
        for i in range(len(condensed)):
            if i not in a and drive[i] > 1e-6 * max(1.0, abs(gc[i])):
                return None
        return p, n_t, n_k, gibbs(p, n_t, n_k, a)

    # Choose the stable phase assemblage by lowest Gibbs energy among the VALID ones. The
    # driving-force greedy rule alone can land on a phase-rule-violating or non-converged set,
    # so for a small condensed list we enumerate subsets up to the phase-rule limit (at most
    # nE phases, one of them the gas) and keep the lowest-Gibbs feasible one, which is exact.
    # For a large list, fall back to a greedy start plus single-toggle local search.
    ncnd = len(condensed)
    kmax = min(ncnd, nE)
    ncombo = sum(math.comb(ncnd, k) for k in range(kmax + 1))
    best, active = None, []
    if ncnd == 0:
        best = evaluate([])
    elif ncombo <= 4000:
        for k in range(kmax + 1):
            for combo in combinations(range(ncnd), k):
                res = evaluate(combo)
                if res is not None and (best is None or res[3] < best[3]):
                    best, active = res, list(combo)
    if best is None:
        # greedy start + local search (large condensed lists, or nothing enumerated cleanly)
        active, pi, nt, nk = [], pi_seed.copy(), nt_seed, np.zeros(0)
        for _ in range(max_outer):
            pi, nt, nk = solve_active(active, pi, nt)
            if len(active) and nk.min() < -tol * bscale:
                active.pop(int(np.argmin(nk)))
                continue
            drive = Ac @ pi - gc
            cand = [(drive[i], i) for i in range(ncnd) if i not in active]
            if cand and max(cand)[0] > tol:
                active.append(max(cand)[1])
                continue
            break
        seen = evaluate(active)
        gbest = seen[3] if seen else np.inf
        for _ in range(2 * ncnd + 2):
            improved = False
            for i in range(ncnd):
                trial = [j for j in active if j != i] if i in active else active + [i]
                res = evaluate(trial)
                g = res[3] if res else np.inf
                if g < gbest - 1e-10 * max(1.0, abs(gbest)):
                    active, gbest, seen = trial, g, res
                    improved = True
                    break
            if not improved:
                break
        best = seen if seen else (pi_seed.copy(), nt_seed, np.zeros(len(active)), np.inf)
    pi, nt, nk = best[0], best[1], best[2]

    X = Xgas(pi)
    frac = dict(zip(gas_names, X / X.sum()))
    cond_moles = {condensed[active[j]].name: float(max(nk[j], 0.0)) for j in range(len(active))}
    return frac, cond_moles, dict(zip(els, pi))

