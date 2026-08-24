"""Olivine metastable solvus by multiphase equilibrium - a CEF phase in the solver.

The forsterite-fayalite olivine is a single CEF solid solution. Below its consolute
temperature the calorimetric excess makes G(x) non-convex, so the phase unmixes into
two coexisting olivines (a metastable Fe-rich + Mg-rich pair). Computing that is exactly
the multiphase equilibrium of a CEF phase with itself: sample the phase's G(x) curve and
take the lower convex hull; the tie-line endpoints are the conjugate compositions.

This wires the C CEF kernel (via the ChemSage SUBL reader) into the engine's binary
multiphase hull solver: the olivine curve is evaluated by mqmqa.Database.cef_gibbs -> the
C mqmqa_cef_gibbs, then handed to equilibrium.miscibility_conjugates. The result is
validated against pycalphad's own equilibrium() on the same .dat.

Run from the repo root:
  C:/Users/busta/miniforge3/envs/calphad/python.exe data/olivine/solvus.py
"""
import sys
from pathlib import Path

import numpy as np
from pycalphad import Database as PycDatabase, equilibrium, variables as v

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "python"))
sys.path.insert(0, str(HERE.parents[1] / "cef"))

import mqmqa
from mqmqa import equilibrium as eq
import olivine as ol

DAT = HERE / "Olivine-CEF.dat"
X_SI, X_O = 1.0 / 7.0, 4.0 / 7.0  # olivine atom fractions of Si and O (fixed by stoichiometry)


def olivine_curve(cdb, p, T, n=401):
    """Sampled G(x_fo) curve of the olivine CEF phase, per formula unit, from the C
    kernel. x_fo = y_Mg is the metal-sublattice forsterite fraction."""
    pts = []
    for x_fo in np.linspace(1e-4, 1 - 1e-4, n):
        Y = [1.0 - x_fo, x_fo, 1.0, 1.0]  # reader order [Fe, Mg], Si, O
        g = cdb.cef_gibbs(p, Y, T, per_mole_atoms=False)  # per Mg2SiO4/Fe2SiO4 formula
        pts.append((float(x_fo), g, "OLIVINE", float(x_fo)))
    return pts


def my_conjugates(cdb, p, T):
    """The two coexisting olivine compositions (x_fo) from the engine's hull solver,
    or None above the consolute (convex curve, single stable phase)."""
    conj = eq.miscibility_conjugates(olivine_curve(cdb, p, T), min_span=2e-3)
    if not conj:
        return None
    # the widest tie-line is the solvus (a fine grid can leave tiny near-flat edges)
    xL, _, xR, _ = max(conj, key=lambda c: c[2] - c[0])
    return xL, xR


def pyc_conjugates(pdb, T):
    """pycalphad's coexisting olivine compositions at T: sweep overall X(MG) and read
    the metal fraction x_fo of every stable phase instance; the binodal edges are the
    min and max x_fo seen in two-phase gridpoints. None if no two-phase region."""
    res = equilibrium(pdb, ["FE", "MG", "SI", "O"], "OLIVINE",
                      {v.T: T, v.P: 101325, v.X("SI"): X_SI, v.X("O"): X_O,
                       v.X("MG"): (0.005, 0.281, 0.0025)})
    phase = res.Phase.values
    XMG = res.X.sel(component="MG").values
    XFE = res.X.sel(component="FE").values
    xfos = []
    npts = phase.shape[-1]
    flatP = phase.reshape(-1, npts)
    flatMG = XMG.reshape(-1, npts)
    flatFE = XFE.reshape(-1, npts)
    for i in range(flatP.shape[0]):
        stable = [k for k in range(npts) if flatP[i, k] == "OLIVINE"]
        if len(stable) >= 2:  # two-phase gridpoint
            for k in stable:
                m, f = flatMG[i, k], flatFE[i, k]
                if m + f > 0:
                    xfos.append(m / (m + f))
    if not xfos:
        return None
    return min(xfos), max(xfos)


def main():
    import build_subl_dat
    DAT.write_text(build_subl_dat.build(), encoding="ascii")

    cdb = mqmqa.Database.read(str(DAT))
    p = cdb.phase_index("OLIVINE")
    pdb = PycDatabase(str(DAT))

    Tc, xc = ol.consolute()
    print(f"model consolute: T_c = {Tc:.0f} K ({Tc - 273.15:.0f} C) at x_fo = {xc:.3f}\n")
    print("Olivine metastable solvus: conjugate x_fo (forsterite fraction)")
    print(f"{'T (K)':>7} | {'engine (C CEF) L/R':>22} | {'pycalphad L/R':>22} | max |d|")
    print("-" * 72)
    worst = 0.0
    for T in (300.0, 350.0, 400.0, 430.0):
        mine = my_conjugates(cdb, p, T)
        pyc = pyc_conjugates(pdb, T)
        if mine and pyc:
            d = max(abs(mine[0] - pyc[0]), abs(mine[1] - pyc[1]))
            worst = max(worst, d)
            print(f"{T:7.0f} | {mine[0]:9.4f} {mine[1]:9.4f}   | "
                  f"{pyc[0]:9.4f} {pyc[1]:9.4f}   | {d:.4f}")
        else:
            print(f"{T:7.0f} | {'single phase' if not mine else mine!s:>22} | "
                  f"{'single phase' if not pyc else pyc!s:>22} |")
    print("-" * 72)
    ok = worst < 0.02  # 2 mol% agreement on the binodal (grid-limited on both sides)
    print(f"worst binodal disagreement = {worst:.4f} mole fraction  -> "
          f"{'PASS' if ok else 'FAIL'}")


if __name__ == "__main__":
    main()
