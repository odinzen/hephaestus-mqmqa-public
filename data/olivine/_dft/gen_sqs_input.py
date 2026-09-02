"""SevenNet-relax the x=0.5 SQS, then write its DFT+U vc-relax input (same recipe as ord2..ord5).

Keeps U=4 on Fe and the identical cutoffs / k-mesh / robust mixing so the SQS energy is
directly comparable to E_fa and E_fo in the 28-atom framework.
"""
import os, re, warnings
os.environ["TORCHDYNAMO_DISABLE"] = "1"; warnings.filterwarnings("ignore")
from pathlib import Path
from ase.io import read, write
from ase.optimize import FIRE
from ase.filters import FrechetCellFilter
from sevenn.calculator import SevenNetCalculator

HERE = Path(__file__).resolve().parent
PSDIR = "/mnt/c/Users/busta/Code/mqmqa/data/olivine/_dft/pseudo"
PSEUDO = {"Fe": "Fe.pbe-spn-kjpaw_psl.1.0.0.UPF", "Mg": "Mg.pbe-spnl-kjpaw_psl.1.0.0.UPF",
          "Si": "Si.pbe-n-kjpaw_psl.1.0.0.UPF", "O": "O.pbe-n-kjpaw_psl.1.0.0.UPF"}
KPTS = (2, 1, 2)

def base_input():
    return {"control": {"calculation": "vc-relax", "restart_mode": "from_scratch", "prefix": "oliv",
              "pseudo_dir": PSDIR, "outdir": "./out", "tprnfor": True, "tstress": True,
              "forc_conv_thr": 1e-4, "etot_conv_thr": 1e-5, "nstep": 250, "disk_io": "low",
              "verbosity": "low"},
            "system": {"ecutwfc": 60, "ecutrho": 480, "occupations": "smearing",
              "smearing": "gaussian", "degauss": 0.01, "nspin": 2},
            "electrons": {"conv_thr": 1e-7, "mixing_beta": 0.2, "mixing_mode": "local-TF",
              "electron_maxstep": 400},
            "ions": {"ion_dynamics": "bfgs"}, "cell": {"cell_dynamics": "bfgs", "press_conv_thr": 0.5}}

a = read(str(HERE / "ordering_geoms" / "sqs_unrelaxed.xyz"))
a.calc = SevenNetCalculator(model="7net-0")
a.set_initial_magnetic_moments([0.5 if s == "Fe" else 0.0 for s in a.get_chemical_symbols()])
FIRE(FrechetCellFilter(a), logfile=None).run(fmax=0.03, steps=400)
write(str(HERE / "ordering_geoms" / "sqs_relaxed.xyz"), a)

a.set_initial_magnetic_moments([0.5 if s == "Fe" else 0.0 for s in a.get_chemical_symbols()])
run = HERE / "runs_u" / "sqs"; run.mkdir(parents=True, exist_ok=True)
write(str(run / "pw.in"), a, format="espresso-in", input_data=base_input(),
      pseudopotentials=PSEUDO, kpts=KPTS)
txt = (run / "pw.in").read_text()
sp = re.search(r"ATOMIC_SPECIES\n((?:.*\n)+?)\n", txt).group(1)
fe = next(i for i, l in enumerate([x for x in sp.splitlines() if x.strip()], 1) if l.split()[0] == "Fe")
(run / "pw.in").write_text(txt.replace("   nspin            = 2\n",
    f"   nspin            = 2\n   lda_plus_u       = .true.\n   Hubbard_U({fe}) = 4.0\n"))
print(f"SQS SevenNet-relaxed and DFT+U input written: {a.get_chemical_formula()} Fe=species{fe}")
print(f"  -> runs_u/sqs/pw.in")
