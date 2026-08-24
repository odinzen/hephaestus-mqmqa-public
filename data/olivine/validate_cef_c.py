"""Validate the C CEF kernel + the C ChemSage SUBL reader against pycalphad.

Both sides read the SAME olivine SUBL .dat (data/olivine/Olivine-CEF.dat, written by
build_subl_dat.py). The C reader parses the SUBL block and the C kernel (mqmqa_cef_gibbs,
a clean-room port of cef/cef.py) computes GM; pycalphad's Model.GM is the oracle. Agreement
to machine precision closes the loop: the C reader parsed the sublattice model correctly and
the C energy kernel matches the reference formalism.

Run from the repo root:
  C:/Users/busta/miniforge3/envs/calphad/python.exe data/olivine/validate_cef_c.py
"""
import sys
from pathlib import Path

import numpy as np
from pycalphad import Database as PycDatabase, calculate

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "python"))
sys.path.insert(0, str(HERE.parents[1] / "cef"))

import mqmqa
import olivine as ol

DAT = HERE / "Olivine-CEF.dat"


def _build_dat():
    import build_subl_dat
    DAT.write_text(build_subl_dat.build(), encoding="ascii")


def main():
    _build_dat()

    # C reader + C kernel
    cdb = mqmqa.Database.read(str(DAT))
    p = cdb.phase_index("OLIVINE")
    print("phase kind (1 = CEF):", cdb.phase_kind(p))
    subl = cdb.cef_sublattices(p)
    for s, sl in enumerate(subl):
        print(f"  sublattice {s}: a_s={sl['site_ratio']:.3f}  constituents={sl['constituents']}")

    # constituent order the reader expects for the flattened site-fraction vector
    order = [(s, c) for s, sl in enumerate(subl) for c in sl["constituents"]]

    def Y_for(x_fo):
        # map (y_Fe, y_Mg) onto the reader's constituent order; Si, O are 1.0
        ymap = {("FE"): 1.0 - x_fo, ("MG"): x_fo, ("SI"): 1.0, ("O"): 1.0}
        return [ymap[c] for _, c in order]

    # pycalphad oracle on the same file
    pdb = PycDatabase(str(DAT))

    print("\nGM: C reader+kernel vs pycalphad (same .dat)")
    worst = 0.0
    for T in (1000.0, 1400.0, 1800.0):
        for x_fo in (0.0, 0.2, 0.5, 0.8, 1.0):
            gc = cdb.cef_gibbs(p, Y_for(x_fo), T)
            pt = np.array([[1.0 - x_fo, x_fo, 1.0, 1.0]])  # pycalphad sorted [Fe,Mg],Si,O
            gpc = float(calculate(pdb, ["FE", "MG", "SI", "O"], "OLIVINE",
                                  T=T, P=101325, points=pt, output="GM").GM.values.squeeze())
            d = abs(gc - gpc)
            worst = max(worst, d)
            print(f"  T={T:6.0f}  x_fo={x_fo:4.2f}  C={gc:12.4f}  pycalphad={gpc:12.4f}  |d|={d:.2e}")
    print(f"  worst |d| = {worst:.2e} J/mol-atom  -> {'PASS' if worst < 1e-4 else 'FAIL'}")

    # cross-check the C kernel against the pure-Python CEF prototype too (relative
    # tolerance: absolute J/mol on ~3e5-magnitude energies floors at float64 round-off)
    print("\nGM: C kernel vs Python cef prototype (relative)")
    phase = ol.olivine_phase()
    worst2 = 0.0
    for T in (1000.0, 1400.0):
        for x_fo in (0.25, 0.5, 0.75):
            gc = cdb.cef_gibbs(p, Y_for(x_fo), T)
            gpy = phase.gibbs(ol.site_fracs(x_fo), T)
            worst2 = max(worst2, abs(gc - gpy) / abs(gpy))
    print(f"  worst relative |d| = {worst2:.2e}  -> {'PASS' if worst2 < 1e-9 else 'FAIL'}")


if __name__ == "__main__":
    main()
