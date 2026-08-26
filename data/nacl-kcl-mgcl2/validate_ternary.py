"""Validate the assembled NaCl-KCl-MgCl2 ternary (nothing ternary was fitted).

Three checks, all against the WRITTEN database file:
 1. engine liquid GM == pycalphad at the Mohan eutectic composition (the Muggianu
    assembly of the three binaries is emitted and evaluated correctly);
 2. the ternary-eutectic MELTING temperature vs Mohan et al. 2018's measured 387 degC
    (660.15 K) at 24.5/20.5/55 wt% NaCl/KCl/MgCl2 (a pure prediction; the composition is
    FactSage-located, the melting point is DSC-measured);
 3. the eutectic-liquid heat capacity vs Mohan's measured 1.18 J/g/K.
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))
_spec = importlib.util.spec_from_file_location("nkm_build", HERE / "build_dat.py")
bd = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(bd)

from mqmqa import Database
from mqmqa import equilibrium as eq
from mqmqa import _abi

MASS = {"NaCl": 58.442, "KCl": 74.551, "MgCl2": 95.211}   # g/mol
WT = {"NaCl": 24.5, "KCl": 20.5, "MgCl2": 55.0}           # Mohan 2018 eutectic
T_EUT_MEAS = 660.15                                        # 387 degC
CP_MEAS = 1.18                                             # J/g/K


def mohan_salt_fractions():
    moles = {k: WT[k] / MASS[k] for k in WT}
    tot = sum(moles.values())
    return {k: moles[k] / tot for k in moles}


def element_moles(xf):
    na, k, mg = xf["NaCl"], xf["KCl"], xf["MgCl2"]
    return {"NA": na, "K": k, "MG": mg, "CL": na + k + 2 * mg}


def g_per_atom_mass(el):
    tot = sum(el.values())
    g = el["NA"] * 22.990 + el["K"] * 39.098 + el["MG"] * 24.305 + el["CL"] * 35.453
    return g / tot                                         # g per mole of atoms


def main():
    from pycalphad import Database as PDB, calculate, equilibrium, variables as v
    dat = HERE / "NaCl-KCl-MgCl2.dat"
    if not dat.exists():
        bd.build()
    db = Database.read(str(dat))
    pdb = PDB(str(dat))
    p = db.phase_index("NACL-KCL-MGCL2-LIQUID")

    xf = mohan_salt_fractions()
    el = element_moles(xf)
    print(f"Mohan eutectic: salt fractions {{Na {xf['NaCl']:.3f}, K {xf['KCl']:.3f}, "
          f"Mg {xf['MgCl2']:.3f}}}")

    # 1. C engine vs pycalphad liquid GM at the eutectic composition (liquid-only
    # equilibrium in pycalphad is the true minimum at the exact composition).
    tot = sum(el.values())
    for T in (700.0, 900.0):
        inp = eq.build_inputs(db, p, T, components=["NA", "K", "MG", "CL"])
        gm_eng = _abi.c_equilibrate(inp, el)["GM"]
        rr = equilibrium(pdb, ["NA", "K", "MG", "CL"], ["NACL-KCL-MGCL2-LIQUID"],
                         {v.T: T, v.P: 101325, v.N: 1, v.X("NA"): el["NA"] / tot,
                          v.X("K"): el["K"] / tot, v.X("MG"): el["MG"] / tot})
        gm_pyc = float(rr.GM.values.ravel()[0])
        print(f"1. liquid GM @{T:.0f}K: engine {gm_eng:.2f}  pycalphad {gm_pyc:.2f}  "
              f"diff {gm_eng - gm_pyc:+.3f} J/mol-atom")

    # 2. melting temperature at the eutectic composition (pycalphad full-phase sweep)
    conds = {v.T: None, v.P: 101325, v.N: 1,
             v.X("NA"): el["NA"] / tot, v.X("K"): el["K"] / tot, v.X("MG"): el["MG"] / tot}
    T_melt, last_solid = None, None
    for Tt in np.arange(600.0, 740.0, 2.0):
        conds[v.T] = float(Tt)
        rr = equilibrium(pdb, ["NA", "K", "MG", "CL"], list(pdb.phases.keys()), conds)
        phases = sorted(set(str(x) for x in rr.Phase.values.ravel() if x))
        if phases == ["NACL-KCL-MGCL2-LIQUID"]:
            T_melt = float(Tt)
            break
        last_solid = (float(Tt), phases)
    print(f"2. model liquidus (fully liquid) at {T_melt} K vs Mohan measured {T_EUT_MEAS} K "
          f"(387 degC); just below: {last_solid}")

    # 3. eutectic-liquid Cp near the melting point (C solver, smooth in T)
    Tc, h = 700.0, 5.0
    def gm(TT):
        i = eq.build_inputs(db, p, TT, components=["NA", "K", "MG", "CL"])
        return _abi.c_equilibrate(i, el)["GM"]
    cp_atom = -Tc * (gm(Tc + h) - 2 * gm(Tc) + gm(Tc - h)) / (h * h)
    cp_gram = cp_atom / g_per_atom_mass(el)
    print(f"3. eutectic-liquid Cp: model {cp_gram:.2f} J/g/K vs Mohan measured {CP_MEAS} "
          f"(not fitted)")


if __name__ == "__main__":
    main()
