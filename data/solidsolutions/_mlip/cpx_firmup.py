"""Firm-up rerun of clinopyroxene (diopside-hedenbergite) Fe-Mg mixing. The conventional diopside
cell has only 4 Mg sites, too coarse for a reliable excess; this uses a 2x1x1 supercell (8 Mg
sites, matching the validated olivine cell) with more orderings per composition. SevenNet-0, same
relax protocol as the campaign (Fe->Mg on M1, cell+positions at 0 GPa, H_mix a difference vs ends).
"""
import itertools, os, warnings, json
os.environ['TORCHDYNAMO_DISABLE'] = '1'; warnings.filterwarnings('ignore')
from pathlib import Path
import numpy as np
from ase.io import read
from ase.optimize import FIRE
from ase.filters import FrechetCellFilter
from sevenn.calculator import SevenNetCalculator

HERE = Path(__file__).resolve().parent
EV = 96485.0; REP = (2, 1, 1); NORD = 10
CALC = SevenNetCalculator(model='7net-0')

def relax(a):
    a = a.copy(); a.calc = CALC
    FIRE(FrechetCellFilter(a), logfile=None).run(fmax=0.03, steps=400)
    return a.get_potential_energy()

base = read(str(HERE / 'cif' / 'diopside_CaMgSi2O6_1000007.cif')).repeat(REP)
mg = [i for i, s in enumerate(base.get_chemical_symbols()) if s == 'Mg']
n = len(mg); Z = n  # 1 Mg per Ca(Mg,Fe)Si2O6 formula
rng = np.random.default_rng(0); rows = []
print(f'cpx supercell {REP}: {base.get_chemical_formula()}, {n} Mg-sites, Z={Z}, up to {NORD} orderings/comp', flush=True)
for x in (0.0, 0.25, 0.5, 0.75, 1.0):
    k = round(x * n); combos = list(itertools.combinations(mg, k))
    if len(combos) > NORD:
        combos = [combos[i] for i in rng.choice(len(combos), NORD, replace=False)]
    es = []
    for combo in combos:
        a = base.copy(); sym = a.get_chemical_symbols()
        for i in combo:
            sym[i] = 'Fe'
        a.set_chemical_symbols(sym); es.append(relax(a) / Z)
    sd = np.std(es) if len(es) > 1 else 0.
    se = sd / np.sqrt(len(es)) if len(es) > 1 else 0.
    rows.append((k / n, float(np.mean(es)), float(sd)))
    print(f'  x={k/n:.3f} ({len(combos)} ord): <E>={np.mean(es):.4f} eV/f.u. spread {sd*1000:.1f} meV (SE {se*1000:.1f})', flush=True)

e0, e1 = rows[0][1], rows[-1][1]; xs = np.array([r[0] for r in rows])
hm = np.array([(r[1] - ((1 - r[0]) * e0 + r[0] * e1)) * EV for r in rows])
I = (xs > 0) & (xs < 1)
A = np.column_stack([xs[I] * (1 - xs[I]), xs[I] * (1 - xs[I]) * (2 * xs[I] - 1)])
(L0, L1), *_ = np.linalg.lstsq(A, hm[I], rcond=None)
h50 = float(hm[np.argmin(np.abs(xs - 0.5))])
print('\n  x      H_mix (J/mol formula)')
for x, h in zip(xs, hm):
    print(f'  {x:.3f}   {h:8.0f}')
print(f'\nclinopyroxene (8-site supercell)  RK L0={L0:.0f} L1={L1:.0f}  H_mix@0.5={h50:.0f}', flush=True)
print('prior 4-site cell:                RK L0=2012 L1=11811  H_mix@0.5=959', flush=True)
json.dump({'label': 'clinopyroxene_supercell', 'rep': list(REP), 'nsites': n,
           'x': list(map(float, xs)), 'H_mix': list(map(float, hm)),
           'L0': float(L0), 'L1': float(L1), 'h50': h50},
          open(HERE / 'cpx_firmup.json', 'w'), indent=1)
print('CPX FIRMUP DONE', flush=True)
