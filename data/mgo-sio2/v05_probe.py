"""Measure the Fix-A effect: swap Neumann-Kopp compound solids for the measured R&H
compound Cp(T), holding the v0.4 liquid fixed, and report every invariant both ways.

This isolates how much the compound heat-capacity model alone moves the invariant
temperatures - the question the brief poses (is Neumann-Kopp the ~115 K lever?).
"""
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "python"))

import phase_diagram as pdg
import phase_hull as ph

MEAS = {
    "forsterite congruent": 2163.0,
    "enstatite peritectic": 1830.0,
    "periclase-forsterite eutectic": 2123.0,
    "enstatite-cristobalite eutectic": 1816.0,
}


def cp298_check():
    print("Cp(298.15) reproduction (R&H measured in parens):")
    for name, meas in (("M2S(forsterite)", 118.61), ("MS(enstatite)", 83.09)):
        cp = pdg._cp5(pdg.RH_COMPOUND_CP[name], pdg.T0)
        print(f"  {name:18s} Cp298 = {cp:7.2f}   (R&H {meas})")


def invariants(dat):
    db, p = ph.load(dat)
    out = {}
    out["forsterite congruent"] = pdg.congruent_melting(db, p, "M2S(forsterite)")
    _, _, Tp, kind, _ = ph.classify_compound(db, p, "MS(enstatite)")
    out["enstatite peritectic"] = Tp
    out["enstatite kind"] = kind
    out["periclase-forsterite eutectic"] = ph.eutectic(
        db, p, "MgO(periclase)", "M2S(forsterite)")
    out["enstatite-cristobalite eutectic"] = ph.eutectic(
        db, p, "MS(enstatite)", "SiO2(cristobalite)")
    return out


def report(tag):
    dat = HERE / "MgO-SiO2-liquid.dat"
    r = invariants(dat)
    print(f"\n[{tag}]  (USE_COMPOUND_CP = {pdg.USE_COMPOUND_CP})")
    for k in MEAS:
        v = r[k]
        vs = f"{v:6.0f} K" if v else "  none "
        d = f"{v - MEAS[k]:+5.0f}" if v else "   -"
        print(f"  {k:34s} {vs}   meas {MEAS[k]:5.0f}   dT = {d} K")
    print(f"  enstatite classified: {r['enstatite kind']}")


if __name__ == "__main__":
    cp298_check()

    # sanity: with Cp_comp forced to the oxide sum, the compound-Cp path must reproduce
    # Neumann-Kopp exactly (algebraic identity). Check forsterite Gibbs at 1800 K.
    pdg.USE_COMPOUND_CP = False
    g_nk, _ = pdg.solid_gibbs_per_formula_unit("M2S(forsterite)", 1800.0)
    # temporarily point forsterite Cp at the oxide sum by a large T_fit_max and matched coef?
    # simplest identity check: dCp_ox at 298 is tiny, so g should differ only slightly.
    pdg.USE_COMPOUND_CP = True
    g_cp, _ = pdg.solid_gibbs_per_formula_unit("M2S(forsterite)", 1800.0)
    print(f"\nForsterite G(1800) per oxide unit: NK {g_nk:.1f}  vs  real-Cp {g_cp:.1f}  "
          f"(diff {g_cp - g_nk:+.1f} J/mol)")

    pdg.USE_COMPOUND_CP = False
    report("Neumann-Kopp (v0.4 baseline)")
    pdg.USE_COMPOUND_CP = True
    report("measured compound Cp (Fix A)")
