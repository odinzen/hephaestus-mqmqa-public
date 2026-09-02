"""Generate distinct x=0.5 Fe/Mg orderings on the 8 forsterite M-sites, SevenNet-relax each
(cell+ions) to give DFT+U a near-converged start. Random 4-of-8 subsets approximate the
configurational average that the measured random-mixing enthalpy corresponds to."""
import itertools, os, warnings
os.environ['TORCHDYNAMO_DISABLE']='1'; warnings.filterwarnings('ignore')
from pathlib import Path
import numpy as np
from ase.io import read, write
from ase.optimize import FIRE
from ase.filters import FrechetCellFilter
from sevenn.calculator import SevenNetCalculator
HERE=Path(__file__).resolve().parent
CALC=SevenNetCalculator(model='7net-0')
base=read(str(HERE.parent/'_mlip'/'cif'/'forsterite_1572966.cif'))
mg=[i for i,s in enumerate(base.get_chemical_symbols()) if s=='Mg']   # 8 M-sites
# ordering 1 = mg[:4] (the one already run in DFT). add 4 distinct random 4-subsets.
rng=np.random.default_rng(7); seen={tuple(sorted(mg[:4]))}; orders=[]
while len(orders)<4:
    pick=tuple(sorted(rng.choice(mg,4,replace=False)))
    if pick in seen: continue
    seen.add(pick); orders.append(list(pick))
for n,combo in enumerate(orders, start=2):        # ord2..ord5 (ord1 already done as x50_a)
    a=base.copy(); sym=a.get_chemical_symbols()
    for i in combo: sym[i]='Fe'
    a.set_chemical_symbols(sym); a.calc=CALC
    FIRE(FrechetCellFilter(a),logfile=None).run(fmax=0.03,steps=400)
    write(str(HERE/'ordering_geoms'/f'ord{n}.xyz'), a)
    print(f"ord{n}: Fe@{combo}  {a.get_chemical_formula()}  relaxed (SevenNet)", flush=True)
