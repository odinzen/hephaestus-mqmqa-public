"""MLIP phonon entropy/heat-capacity of the Ca-silicates (finite displacement,
MatterSim forces via phonopy). Replaces the estimated S298 / Neumann-Kopp Cp used
in the phase-diagram solids. Phonon frequencies (curvature) are more robust to the
MLIP's CaO-rich binding bias than formation energies, so S/Cp should be reliable.
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np
from pymatgen.core import Structure
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from pymatgen.io.ase import AseAtomsAdaptor
from ase import Atoms
from ase.optimize import LBFGS
from ase.filters import FrechetCellFilter
from phonopy import Phonopy
from phonopy.structure.atoms import PhonopyAtoms
from mattersim.forcefield import MatterSimCalculator

calc = MatterSimCalculator()

def relax(struct):
    at = AseAtomsAdaptor.get_atoms(struct); at.calc = calc
    LBFGS(FrechetCellFilter(at), logfile=None).run(fmax=0.01, steps=400)
    return at

def phonons(cid, apf, label, haas, sc=(2, 2, 2)):
    prim = SpacegroupAnalyzer(Structure.from_file(f"cif/{cid}.cif")).get_primitive_standard_structure()
    at = relax(prim)
    cell = PhonopyAtoms(symbols=at.get_chemical_symbols(),
                        scaled_positions=at.get_scaled_positions(), cell=at.cell[:])
    ph = Phonopy(cell, supercell_matrix=np.diag(sc))
    ph.generate_displacements(distance=0.03)
    forces = []
    for s in ph.supercells_with_displacements:
        a = Atoms(s.symbols, positions=s.positions, cell=s.cell, pbc=True); a.calc = calc
        forces.append(a.get_forces())
    ph.forces = forces
    ph.produce_force_constants()
    ph.run_mesh([12, 12, 12])
    natoms_prim = len(at)
    zf = natoms_prim / apf                      # formula units in the primitive cell
    ph.run_thermal_properties(t_min=298, t_max=298, t_step=1)
    tp = ph.get_thermal_properties_dict()
    S = tp["entropy"][0] / zf                    # J/K per formula unit
    Cv = tp["heat_capacity"][0] / zf
    fmin = ph.get_mesh_dict()["frequencies"].min()
    print(f"  {label:24s} S298={S:6.1f}  Cv298={Cv:6.1f} J/mol/K   Haas={haas}   "
          f"min_freq={fmin:+.2f} THz {'(IMAG!)' if fmin < -0.1 else ''}")

if __name__ == "__main__":
    print("MLIP phonon S298 / Cv vs Haas evaluated values (J/mol/K):")
    phonons("9017535", 5, "CaSiO3 (pseudowoll)", "woll 81.0 / est 85.2")
    phonons("9012789", 7, "Ca2SiO4 (beta)", "126.7")
