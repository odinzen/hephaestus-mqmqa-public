"""Generate QE pw.x inputs for the olivine Fe-Mg mixing DFT control.
Same 28-atom forsterite framework as the MLIP runs (COD 1572966), same k-grid for all
structures so basis/k errors cancel in the mixing-enthalpy difference. pslibrary 1.0.0
PBE-PAW, spin-polarized (FM Fe), vc-relax. A quick 'scf' variant is written for sanity."""
import itertools, sys
from pathlib import Path
import numpy as np
from ase.io import read, write
HERE = Path(__file__).resolve().parent
PSDIR = "/mnt/c/Users/busta/Code/mqmqa/data/olivine/_dft/pseudo"   # WSL-visible
PSEUDO = {"Fe":"Fe.pbe-spn-kjpaw_psl.1.0.0.UPF","Mg":"Mg.pbe-spnl-kjpaw_psl.1.0.0.UPF",
          "Si":"Si.pbe-n-kjpaw_psl.1.0.0.UPF","O":"O.pbe-n-kjpaw_psl.1.0.0.UPF"}
KPTS = (2, 1, 2)                                   # same mesh for every structure

def base_input(calc):
    return {
      "control": {"calculation":calc,"restart_mode":"from_scratch","prefix":"oliv",
                  "pseudo_dir":PSDIR,"outdir":"./out","tprnfor":True,"tstress":True,
                  "forc_conv_thr":1e-4,"etot_conv_thr":1e-5,"nstep":250,"disk_io":"low","verbosity":"low"},
      "system": {"ecutwfc":60,"ecutrho":480,"occupations":"smearing","smearing":"gaussian",
                 "degauss":0.01,"nspin":2},
      "electrons": {"conv_thr":1e-7,"mixing_beta":0.3,"electron_maxstep":250},
      "ions": {"ion_dynamics":"bfgs"},
      "cell": {"cell_dynamics":"bfgs","press_conv_thr":0.5},
    }

def make(atoms, name, calc):
    d = base_input(calc)
    atoms = atoms.copy()
    # high-spin Fe2+ (~4 muB) FM initial guess; ASE maps per-atom moments -> starting_magnetization
    atoms.set_initial_magnetic_moments([0.5 if s == "Fe" else 0.0
                                        for s in atoms.get_chemical_symbols()])
    run = HERE/"runs"/name; run.mkdir(parents=True, exist_ok=True)
    write(str(run/"pw.in"), atoms, format="espresso-in", input_data=d,
          pseudopotentials=PSEUDO, kpts=KPTS)
    print("wrote", run/"pw.in", atoms.get_chemical_formula())

base = read(str(Path("data/olivine/_mlip/cif/forsterite_1572966.cif")))
mg = [i for i,s in enumerate(base.get_chemical_symbols()) if s=="Mg"]
def sub(idx):
    a=base.copy(); sy=a.get_chemical_symbols()
    for i in idx: sy[i]="Fe"
    a.set_chemical_symbols(sy); return a
# x=0 forsterite, x=1 fayalite, x=0.5 one ordering (first 4 M-sites)
make(base, "fo", "vc-relax")
make(sub(mg), "fa", "vc-relax")
make(sub(mg[:4]), "x50_a", "vc-relax")
# a fast SCF sanity input on forsterite (no relax)
make(base, "fo_scf", "scf")
