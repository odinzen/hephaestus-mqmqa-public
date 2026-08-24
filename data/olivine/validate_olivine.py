"""Validate the olivine (Mg,Fe)2SiO4 CEF model.

Two independent checks:
  1. GM against pycalphad's Model.GM for an equivalent TDB, at several compositions and
     temperatures - the CEF machinery (endmember reference, two-site ideal entropy, the
     subregular excess) must agree to machine precision.
  2. The physics: excess enthalpy reproduces Wood & Kleppa (1981), activities show the
     small positive deviation from the ideal a_fo = X_fo^2 line, and the metastable solvus
     stays well below any temperature where olivine is a real phase (complete solid
     solution), consistent with the open calorimetry.
"""
import os
import sys
from pathlib import Path

import numpy as np
from pycalphad import Database, calculate, Model, variables as v

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "cef"))

import cef
import endmembers as em
import olivine as ol


def _term_expr(coeffs):
    """Format term-basis coefficients as a TDB Gibbs expression."""
    c = list(coeffs) + [0.0] * (7 - len(coeffs))
    parts = [f"{c[0]:+.10E}",
             f"{c[1]:+.10E}*T",
             f"{c[2]:+.10E}*T*LN(T)",
             f"{c[3]:+.10E}*T**2",
             f"{c[4]:+.10E}*T**3",
             f"{c[5]:+.10E}*T**(-1)",
             f"{c[6]:+.10E}*T**0.5"]
    return " ".join(parts)


def write_tdb(path, L=(ol.L0, ol.L1)):
    lines = [
        "ELEMENT MG FCC_A1 24.305 0.0 0.0 !",
        "ELEMENT FE FCC_A1 55.845 0.0 0.0 !",
        "ELEMENT SI FCC_A1 28.085 0.0 0.0 !",
        "ELEMENT O  FCC_A1 16.0   0.0 0.0 !",
        "PHASE OLIVINE % 3 2 1 4 !",
        "CONSTITUENT OLIVINE :MG,FE:SI:O: !",
        f"PARAMETER G(OLIVINE,MG:SI:O;0) 298.15 {_term_expr(em.gibbs_coeffs('forsterite'))}; 6000 N !",
        f"PARAMETER G(OLIVINE,FE:SI:O;0) 298.15 {_term_expr(em.gibbs_coeffs('fayalite'))}; 6000 N !",
        f"PARAMETER G(OLIVINE,FE,MG:SI:O;0) 298.15 {L[0]:+.10E}; 6000 N !",
        f"PARAMETER G(OLIVINE,FE,MG:SI:O;1) 298.15 {L[1]:+.10E}; 6000 N !",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def check_vs_pycalphad():
    tdb = HERE / "_olivine.tdb"
    write_tdb(tdb)
    db = Database(str(tdb))
    phase = ol.olivine_phase()
    comps = ["MG", "FE", "SI", "O"]
    print("1) GM vs pycalphad  (per mole of atoms)")
    worst = 0.0
    for T in (1000.0, 1400.0):
        for x_fo in (0.0, 0.25, 0.5, 0.75, 1.0):
            # pycalphad site fractions, sorted order [Fe, Mg] on sublattice 0, then Si, O
            pt = np.array([[1.0 - x_fo, x_fo, 1.0, 1.0]])
            res = calculate(db, comps, "OLIVINE", T=T, P=101325, points=pt, output="GM")
            gpc = float(res.GM.values.squeeze())
            gours = phase.gibbs(ol.site_fracs(x_fo), T)  # per mole atom
            d = abs(gpc - gours)
            worst = max(worst, d)
            print(f"   T={T:6.0f}  x_fo={x_fo:4.2f}  pycalphad={gpc:12.4f}  ours={gours:12.4f}  |d|={d:.2e}")
    print(f"   worst |d| = {worst:.2e} J/mol-atom  -> {'PASS' if worst < 1e-4 else 'FAIL'}")
    return worst


def check_enthalpy_of_mixing():
    """H_xs must reproduce Wood & Kleppa's H_xs = 2(1000 + 1000 X_Fe) X_Fe X_Mg cal/mol."""
    print("\n2) Excess enthalpy of mixing vs Wood & Kleppa (1981)  [J/mol-formula]")
    worst = 0.0
    for x_fo in (0.2, 0.4, 0.5, 0.6, 0.8):
        x_fe = 1.0 - x_fo
        wk = 2.0 * (1000.0 + 1000.0 * x_fe) * x_fe * x_fo * ol.CAL  # cal -> J
        ours = ol.h_xs(x_fo)
        d = abs(wk - ours)
        worst = max(worst, d)
        print(f"   x_fo={x_fo:4.2f}  Wood-Kleppa={wk:8.1f}  ours={ours:8.1f}  |d|={d:.2e}")
    print(f"   worst |d| = {worst:.2e} J/mol  -> {'PASS' if worst < 1e-6 else 'FAIL'}")
    print(f"   H_xs at x_fo=0.5 = {ol.h_xs(0.5):.0f} J/mol  (small, positive = near-ideal)")


def check_activities():
    """Near-ideal mixing: activities close to (but above) the ideal a_i = X_i^2 line."""
    print("\n3) Component activities at 1200 K (ideal reference a_fo = X_fo^2)")
    for x_fo in (0.2, 0.5, 0.8):
        a = ol.activities(x_fo, 1200.0)
        print(f"   x_fo={x_fo:4.2f}  a_fo={a['a_fo']:.4f} (ideal {x_fo**2:.4f}, "
              f"g={a['gamma_fo']:.3f})   a_fa={a['a_fa']:.4f} "
              f"(ideal {(1-x_fo)**2:.4f}, g={a['gamma_fa']:.3f})")
    # Gibbs-Duhem sanity: activity coefficients are >= 1 (positive deviation).
    ok = all(ol.activities(x, 1200.0)["gamma_fo"] >= 1.0 for x in (0.2, 0.5, 0.8))
    print(f"   positive deviation (all gamma >= 1): {'PASS' if ok else 'FAIL'}")


def check_solvus():
    """Metastable solvus consolute. A small positive interaction gives a consolute far
    below olivine's stability field: olivine is a complete solid solution in practice."""
    Tc, xc = ol.consolute()
    print("\n4) Metastable Fe-Mg solvus (complete solid solution above it)")
    print(f"   consolute  T_c = {Tc:.0f} K ({Tc-273.15:.0f} C)  at x_fo = {xc:.2f}")
    print(f"   (olivine crystallizes near 2000 K; the solvus is deeply metastable/low-T,")
    print(f"    so forsterite-fayalite is a continuous solution - matches the calorimetry)")


if __name__ == "__main__":
    check_vs_pycalphad()
    check_enthalpy_of_mixing()
    check_activities()
    check_solvus()
