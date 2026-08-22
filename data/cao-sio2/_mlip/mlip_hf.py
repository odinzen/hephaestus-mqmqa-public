"""MLIP spot-check: formation enthalpy of Ca-silicates from the oxides (0 K static),
vs measured calorimetry. Validates the MLIP for this chemistry before we trust its
liquid dH_mix. dHf_ox conserves atoms, so MLIP per-atom references cancel exactly.
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np
from pymatgen.core import Structure, Lattice
from pymatgen.io.ase import AseAtomsAdaptor
from ase.optimize import LBFGS
from ase.filters import FrechetCellFilter
from mattersim.forcefield import MatterSimCalculator
EV=96485.0
calc=MatterSimCalculator()
def relax(struct):
    at=AseAtomsAdaptor.get_atoms(struct); at.calc=calc
    LBFGS(FrechetCellFilter(at),logfile=None).run(fmax=0.03,steps=300)
    n=len(at); return at.get_potential_energy(), n
def load(cid): return Structure.from_file(f"cif/{cid}.cif")
CaO=Structure.from_spacegroup("Fm-3m",Lattice.cubic(4.811),["Ca","O"],[[0,0,0],[.5,.5,.5]])
# energy per formula unit (eV)
def epf(struct, atoms_per_f):
    E,n=relax(struct); return E/(n/atoms_per_f)
eCaO=epf(CaO,2); eSiO2=epf(load("9009666"),3)
print(f"  E/f CaO={eCaO:.4f}  SiO2(qz)={eSiO2:.4f} eV")
# compound: (cid, n_CaO, n_SiO2, atoms/f, measured dHf_ox J/mol, label)
comp=[("9017535",1,1,5,-81922,"CaSiO3 (pseudowoll vs qz)"),
      ("9012789",2,1,7,-126315,"Ca2SiO4 (beta vs qz)"),
      ("1540704",3,1,9,-112884,"Ca3SiO5 (vs qz)")]
print("\n  compound                     MLIP dHf_ox   measured   diff (kJ/mol)")
for cid,nc,ns,apf,meas,lab in comp:
    e=epf(load(cid),apf)
    dhf=(e-nc*eCaO-ns*eSiO2)*EV
    print(f"  {lab:28s} {dhf/1000:+8.1f}   {meas/1000:+8.1f}   {(dhf-meas)/1000:+6.1f}")
