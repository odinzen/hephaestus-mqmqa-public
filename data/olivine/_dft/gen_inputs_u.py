"""PBE+U inputs restarted from the PBE-relaxed geometries. Same numerics + ordering as the PBE
run; add Hubbard U on Fe 3d only (forsterite has no Fe, so its energy is unchanged and reused).
Isolates the +U effect on the olivine Fe-Mg mixing enthalpy."""
import re
from pathlib import Path
from ase.io import read, write
HERE = Path(__file__).resolve().parent
PSDIR = "/mnt/c/Users/busta/Code/mqmqa/data/olivine/_dft/pseudo"
PSEUDO = {"Fe":"Fe.pbe-spn-kjpaw_psl.1.0.0.UPF","Mg":"Mg.pbe-spnl-kjpaw_psl.1.0.0.UPF",
          "Si":"Si.pbe-n-kjpaw_psl.1.0.0.UPF","O":"O.pbe-n-kjpaw_psl.1.0.0.UPF"}
KPTS = (2,1,2); U_FE = 4.0
def base_input():
    return {"control":{"calculation":"vc-relax","restart_mode":"from_scratch","prefix":"oliv",
              "pseudo_dir":PSDIR,"outdir":"./out","tprnfor":True,"tstress":True,"forc_conv_thr":1e-4,
              "etot_conv_thr":1e-5,"nstep":250,"disk_io":"low","verbosity":"low"},
            "system":{"ecutwfc":60,"ecutrho":480,"occupations":"smearing","smearing":"gaussian",
              "degauss":0.01,"nspin":2},
            "electrons":{"conv_thr":1e-7,"mixing_beta":0.3,"electron_maxstep":250},
            "ions":{"ion_dynamics":"bfgs"},"cell":{"cell_dynamics":"bfgs","press_conv_thr":0.5}}
def make(src, name):
    atoms = read(str(HERE/"runs"/src/"pw.out"), format="espresso-out", index=-1)
    atoms.set_initial_magnetic_moments([0.5 if s=="Fe" else 0.0 for s in atoms.get_chemical_symbols()])
    run = HERE/"runs_u"/name; run.mkdir(parents=True, exist_ok=True)
    write(str(run/"pw.in"), atoms, format="espresso-in", input_data=base_input(),
          pseudopotentials=PSEUDO, kpts=KPTS)
    txt = (run/"pw.in").read_text()
    spec = re.search(r"ATOMIC_SPECIES\n((?:.*\n)+?)\n", txt).group(1)
    feidx = next(i for i,l in enumerate([x for x in spec.splitlines() if x.strip()],1) if l.split()[0]=="Fe")
    txt = txt.replace("   nspin            = 2\n",
                      f"   nspin            = 2\n   lda_plus_u       = .true.\n   Hubbard_U({feidx}) = {U_FE}\n")
    (run/"pw.in").write_text(txt)
    print(f"wrote {run/'pw.in'}  Fe=species{feidx}  {atoms.get_chemical_formula()}  {len(atoms)} atoms")
make("fa","fa"); make("x50_a","x50_a")
