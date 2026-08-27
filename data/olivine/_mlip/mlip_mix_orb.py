import itertools, json, os, warnings
os.environ['TORCHDYNAMO_DISABLE']='1'
warnings.filterwarnings('ignore')
from pathlib import Path
import numpy as np
from ase.io import read
from ase.optimize import FIRE
from ase.filters import FrechetCellFilter
from orb_models.forcefield import pretrained
from orb_models.forcefield.calculator import ORBCalculator
HERE=Path(__file__).resolve().parent
orbff=pretrained.orb_v2(device='cpu')
CALC=ORBCalculator(orbff, device='cpu')
EV=96485.0; WK_L0,WK_L1=12552.,4184.
wk=lambda x: x*(1-x)*(WK_L0+WK_L1*(2*x-1))
def relax(a):
    a=a.copy(); a.calc=CALC; FIRE(FrechetCellFilter(a),logfile=None).run(fmax=0.03,steps=400); return a.get_potential_energy()
base=read(str(HERE/'cif'/'forsterite_1572966.cif')); mg=[i for i,s in enumerate(base.get_chemical_symbols()) if s=='Mg']; n=len(mg); Z=n//2
rng=np.random.default_rng(0); rows=[]
print(f'ORB: {base.get_chemical_formula()}, {n} M-sites',flush=True)
for k in (0,2,4,6,8):
    combos=list(itertools.combinations(mg,k))
    if len(combos)>6: combos=[combos[i] for i in rng.choice(len(combos),6,replace=False)]
    es=[]
    for combo in combos:
        a=base.copy(); sym=a.get_chemical_symbols()
        for i in combo: sym[i]='Fe'
        a.set_chemical_symbols(sym); es.append(relax(a)/Z)
    rows.append((k/n,float(np.mean(es)),float(np.std(es)) if len(es)>1 else 0.))
    print(f'x={k/n:.2f}: <E>={np.mean(es):.4f} +/-{np.std(es)*1000 if len(es)>1 else 0:.1f} meV',flush=True)
e0,e1=rows[0][1],rows[-1][1]
xs=np.array([r[0] for r in rows]); hm=np.array([(r[1]-((1-r[0])*e0+r[0]*e1))*EV for r in rows])
print('\n x     ORB H_mix   Wood-Kleppa   diff')
for x,h in zip(xs,hm): print(f' {x:.2f}   {h:8.0f}    {wk(x):8.0f}   {h-wk(x):+7.0f}')
I=(xs>0)&(xs<1); rms=float(np.sqrt(np.mean((hm[I]-np.array([wk(x) for x in xs[I]]))**2)))
A=np.column_stack([xs[I]*(1-xs[I]), xs[I]*(1-xs[I])*(2*xs[I]-1)]); (L0,L1),*_=np.linalg.lstsq(A,hm[I],rcond=None)
print(f'\nORB RK: L0={L0:.0f} L1={L1:.0f} vs WK 12552,4184; RMS(ORB-WK)={rms:.0f} J/mol')
