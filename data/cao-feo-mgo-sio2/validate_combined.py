"""Validate the combined CaO-FeO-MgO-SiO2 multiphase file.

What is validated is the MACHINERY: the combined file assembles the shipped liquid and
CEF-solid databases verbatim, pycalphad reads all eight phases, and a full multi-phase
equilibrium runs and crystallizes a silicate from the slag melt. What is NOT claimed is a
quantitative liquidus: the R&H solid minerals and the MQMQA liquid oxide endmembers are
assessed on independent absolute scales, so absolute melting temperatures and primary-phase
fields are uncalibrated (documented in PROVENANCE.md; the reference-consistency calibration
is the v0.2 step).
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))


def _load(rel, nm):
    s = importlib.util.spec_from_file_location(nm, HERE.parents[1] / "data" / rel)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m


def main():
    import mqmqa
    from pycalphad import Database, calculate, equilibrium, variables as v

    bc = _load("cao-feo-mgo-sio2/build_combined_dat.py", "bc")
    path = bc.build()
    db = mqmqa.Database.read(str(path))
    pdb = Database(str(path))
    phases = sorted(pdb.phases.keys())
    print("1) phases read:", phases)
    assert len(phases) == 8

    # 2) splice is verbatim: the liquid SUBQ block is byte-identical to the standalone file,
    # and the CEF phase Gibbs equals the standalone solids database.
    liq_src = (HERE / "CaO-FeO-MgO-SiO2-liquid.dat").read_text().splitlines()[6:]
    combined = Path(path).read_text().splitlines()
    i0 = combined.index(" CaO-FeO-MgO-SiO2-liquid")
    spliced = combined[i0:i0 + len(liq_src)]
    print(f"2) liquid block byte-identical to standalone: {spliced == liq_src}")
    s = mqmqa.Database.read(str(HERE.parents[0] / "olivine-opx-cpx" / "Olivine-Opx-Cpx-CEF.dat"))
    gc = db.cef_gibbs(db.phase_index("CLINOPYROXENE"), [1, 0.3, 0.7, 1, 1], 1800.0, per_mole_atoms=True)
    gcs = s.cef_gibbs(s.phase_index("CLINOPYROXENE"), [1, 0.3, 0.7, 1, 1], 1800.0, per_mole_atoms=True)
    print(f"   combined cpx vs standalone solids db: {abs(gc - gcs):.2e} J/mol-atom")

    # 3) multi-phase equilibrium runs and crystallizes a silicate from the melt
    xo = {"CaO": 0.25, "FeO": 0.1, "MgO": 0.2, "SiO2": 0.45}
    el = {"CA": xo["CaO"], "FE": xo["FeO"], "MG": xo["MgO"], "SI": xo["SiO2"],
          "O": xo["CaO"] + xo["FeO"] + xo["MgO"] + 2 * xo["SiO2"]}
    tot = sum(el.values())
    print("3) crystallization of a CaO25/FeO10/MgO20/SiO2-45 slag (qualitative):")
    for Tt in (2000.0, 1850.0, 1700.0):
        r = equilibrium(pdb, ["CA", "FE", "MG", "SI", "O"], list(pdb.phases.keys()),
                        {v.T: Tt, v.P: 101325, v.N: 1, v.X("CA"): el["CA"] / tot,
                         v.X("FE"): el["FE"] / tot, v.X("MG"): el["MG"] / tot,
                         v.X("SI"): el["SI"] / tot})
        ph = sorted(set(str(x) for x in r.Phase.values.ravel() if x))
        print(f"   {Tt:.0f} K: {ph}")
    print("   (primary-phase fields are not calibrated; see PROVENANCE.md)")


if __name__ == "__main__":
    main()
