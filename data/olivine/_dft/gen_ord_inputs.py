"""DFT+U inputs for the SevenNet-relaxed x=0.5 orderings (ord2..ord5). U=4 on Fe, same numerics."""
import re
from pathlib import Path
from ase.io import read, write
HERE=Path(__file__).resolve().parent
PSDIR="/mnt/c/Users/busta/Code/mqmqa/data/olivine/_dft/pseudo"
PSEUDO={"Fe":"Fe.pbe-spn-kjpaw_psl.1.0.0.UPF","Mg":"Mg.pbe-spnl-kjpaw_psl.1.0.0.UPF",
        "Si":"Si.pbe-n-kjpaw_psl.1.0.0.UPF","O":"O.pbe-n-kjpaw_psl.1.0.0.UPF"}
KPTS=(2,1,2)
def base_input():
    return {"control":{"calculation":"vc-relax","restart_mode":"from_scratch","prefix":"oliv",
              "pseudo_dir":PSDIR,"outdir":"./out","tprnfor":True,"tstress":True,"forc_conv_thr":1e-4,
              "etot_conv_thr":1e-5,"nstep":250,"disk_io":"low","verbosity":"low"},
            "system":{"ecutwfc":60,"ecutrho":480,"occupations":"smearing","smearing":"gaussian",
              "degauss":0.01,"nspin":2},
            "electrons":{"conv_thr":1e-7,"mixing_beta":0.2,"mixing_mode":"local-TF","electron_maxstep":400},
            "ions":{"ion_dynamics":"bfgs"},"cell":{"cell_dynamics":"bfgs","press_conv_thr":0.5}}
for n in (2,3,4,5):
    a=read(str(HERE/"ordering_geoms"/f"ord{n}.xyz"))
    a.set_initial_magnetic_moments([0.5 if s=="Fe" else 0.0 for s in a.get_chemical_symbols()])
    run=HERE/"runs_u"/f"ord{n}"; run.mkdir(parents=True,exist_ok=True)
    write(str(run/"pw.in"),a,format="espresso-in",input_data=base_input(),pseudopotentials=PSEUDO,kpts=KPTS)
    txt=(run/"pw.in").read_text(); sp=re.search(r"ATOMIC_SPECIES\n((?:.*\n)+?)\n",txt).group(1)
    fe=next(i for i,l in enumerate([x for x in sp.splitlines() if x.strip()],1) if l.split()[0]=="Fe")
    (run/"pw.in").write_text(txt.replace("   nspin            = 2\n",f"   nspin            = 2\n   lda_plus_u       = .true.\n   Hubbard_U({fe}) = 4.0\n"))
    print(f"ord{n}: {a.get_chemical_formula()} Fe=sp{fe}")
