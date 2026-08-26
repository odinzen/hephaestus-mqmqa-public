"""Validate clinopyroxene (diopside-hedenbergite) against pycalphad.

The correctness gate: the C engine's CEF Gibbs energy equals pycalphad's Model.GM to
machine precision across the join and temperature, on the written .dat. Also reports the
Robie-Hemingway endmember reproduction (dHf, S298, Cp298) and the ideal-mixing activities.
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))
_bd = importlib.util.spec_from_file_location("cpx_build", HERE / "build_dat.py")
bd = importlib.util.module_from_spec(_bd); _bd.loader.exec_module(bd)
em = bd.em


def main():
    from pycalphad import Database as PDB, calculate
    import mqmqa
    dat = bd.build()
    db = mqmqa.Database.read(str(dat))
    p = db.phase_index("CLINOPYROXENE")
    pdb = PDB(str(dat))

    print("Robie-Hemingway endmembers (Bull. 2131):")
    for n, ref in (("diopside", 166.78), ("hedenbergite", 175.3)):
        d = em.ENDMEMBERS[n]
        print(f"  {n:13s} dHf {d['dHf']/1000:9.1f} kJ  S298 {d['S298']:6.1f}  "
              f"Cp298 {em.cp(n, 298.15):7.2f} (R&H {ref})")

    worst = 0.0
    for T in (1000.0, 1400.0, 1600.0):
        for xdi in np.linspace(0.0, 1.0, 11):
            Y = [1.0, 1.0 - xdi, xdi, 1.0, 1.0]     # CA, FE, MG, SI, O in file order
            ge = db.cef_gibbs(p, Y, T, per_mole_atoms=True)
            res = calculate(pdb, ["CA", "FE", "MG", "SI", "O"], "CLINOPYROXENE",
                            T=T, P=101325, points=np.array([[1.0, 1.0 - xdi, xdi, 1.0, 1.0]]))
            worst = max(worst, abs(ge - float(res.GM.values.ravel()[0])))
    print(f"\nengine CEF Gibbs vs pycalphad Model.GM: worst |diff| = {worst:.2e} J/mol-atom "
          f"-> {'PASS' if worst < 1e-6 else 'FAIL'}")

    # ideal mixing: activity of each endmember equals its site fraction (gamma = 1).
    print("Mixing: ideal on the M1 (Fe,Mg) sublattice (L0 = 0); a(di) = x_di by "
          "construction. A measured excess and the di-hed solvus are the v0.2 refinement.")


if __name__ == "__main__":
    main()
