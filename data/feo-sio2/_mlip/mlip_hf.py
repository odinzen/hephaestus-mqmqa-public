"""MLIP spot-check: formation enthalpy of fayalite from the oxides (0 K static), vs the
open standard enthalpies. Validates MatterSim for the Fe-Si-O chemistry and measures its
under-binding bias, which is applied to the liquid dH_mix (mlip_mix.py). dHf_ox conserves
atoms, so the MLIP per-atom reference energies cancel exactly. Mirrors data/mgo-sio2.

Run in the mlip-screen conda env, from this directory (reads cif/).
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np
from pymatgen.core import Structure, Lattice
from pymatgen.io.ase import AseAtomsAdaptor
from ase.optimize import LBFGS
from ase.filters import FrechetCellFilter
from mattersim.forcefield import MatterSimCalculator

EV = 96485.0
calc = MatterSimCalculator()


def relax(struct):
    at = AseAtomsAdaptor.get_atoms(struct); at.calc = calc
    LBFGS(FrechetCellFilter(at), logfile=None).run(fmax=0.03, steps=400)
    return at.get_potential_energy(), len(at)


def load(cid):
    return Structure.from_file(f"cif/{cid}.cif")


def epf(struct, atoms_per_f):
    E, n = relax(struct)
    return E / (n / atoms_per_f)


# wustite FeO, rocksalt a = 4.326 A (COD 9009766)
FeO = Structure.from_spacegroup("Fm-3m", Lattice.cubic(4.326), ["Fe", "O"],
                                [[0, 0, 0], [0.5, 0.5, 0.5]])
eFeO = epf(FeO, 2)
eSiO2 = epf(load("9009666"), 3)      # quartz
print(f"  E/f FeO={eFeO:.4f}  SiO2(qz)={eSiO2:.4f} eV")

# compound: (cid, n_FeO, n_SiO2, atoms/f, measured dHf_ox J/mol vs FeO + quartz, label)
#   fayalite dHf_ox(vs quartz) = dHf(fay,elem) - 2 dHf(FeO) - dHf(SiO2,qz)
#                              = -1478.2 - 2(-272.044) - (-910.7) kJ = -23.41 kJ/mol.
comp = [("1000064", 2, 1, 7, -23412, "Fe2SiO4 (fayalite vs qz)")]
print("\n  compound                     MLIP dHf_ox   measured   diff (kJ/mol)   bias/oxide-unit")
for cid, nc, ns, apf, meas, lab in comp:
    e = epf(load(cid), apf)
    dhf = (e - nc * eFeO - ns * eSiO2) * EV
    n_ox = nc + ns
    # bias to ADD to the raw MD dH_mix (per oxide unit): (measured - MLIP)/n_oxide.
    bias = (meas - dhf) / n_ox
    print(f"  {lab:28s} {dhf/1000:+8.1f}   {meas/1000:+8.1f}   {(dhf-meas)/1000:+6.1f}"
          f"        {bias/1000:+.2f} kJ  (x=1/3)")
