"""Fe-Mg mixing enthalpy of a solid solution via SevenNet-0 - the identical protocol validated
against measured olivine calorimetry (see ../../olivine/_mlip/VALIDATION.md, RMS 861 J/mol).

Fe substitutes Mg on the mineral's Mg sites (Ca, Al, Si, O fixed); orderings are relaxed
(cell + positions, 0 GPa) and averaged; H_mix(x) is a difference against the two end members,
so any constant MLIP offset cancels. Reported as Redlich-Kister L0, L1 per formula unit.

Usage: ss_mix.py <cif> <mg_per_formula> <label>
"""
import itertools, os, sys, warnings, json
os.environ['TORCHDYNAMO_DISABLE'] = '1'; warnings.filterwarnings('ignore')
from pathlib import Path
import numpy as np
from ase.io import read
from ase.optimize import FIRE
from ase.filters import FrechetCellFilter
from sevenn.calculator import SevenNetCalculator

HERE = Path(__file__).resolve().parent
CIF, MGPF, LABEL = sys.argv[1], int(sys.argv[2]), sys.argv[3]
EV = 96485.0
CALC = SevenNetCalculator(model='7net-0')

def relax(a):
    a = a.copy(); a.calc = CALC
    FIRE(FrechetCellFilter(a), logfile=None).run(fmax=0.03, steps=400)
    return a.get_potential_energy()

base = read(CIF)
mg = [i for i, s in enumerate(base.get_chemical_symbols()) if s == 'Mg']
n = len(mg); Z = n // MGPF
rng = np.random.default_rng(0); rows = []
print(f'{LABEL}: {base.get_chemical_formula()}, {n} Mg-sites, Z={Z} formula units', flush=True)
for x in (0.0, 0.25, 0.5, 0.75, 1.0):
    k = round(x * n)
    combos = list(itertools.combinations(mg, k))
    if len(combos) > 6:
        combos = [combos[i] for i in rng.choice(len(combos), 6, replace=False)]
    es = []
    for combo in combos:
        a = base.copy(); sym = a.get_chemical_symbols()
        for i in combo:
            sym[i] = 'Fe'
        a.set_chemical_symbols(sym); es.append(relax(a) / Z)
    rows.append((k / n, float(np.mean(es)), float(np.std(es)) if len(es) > 1 else 0.))
    print(f'  x={k/n:.3f} (k={k}, {len(combos)} orderings): <E>={np.mean(es):.4f} eV/f.u.'
          f'  spread {(np.std(es)*1000 if len(es)>1 else 0):.1f} meV', flush=True)

e0, e1 = rows[0][1], rows[-1][1]
xs = np.array([r[0] for r in rows])
hm = np.array([(r[1] - ((1 - r[0]) * e0 + r[0] * e1)) * EV for r in rows])
print('\n  x      H_mix (J/mol formula)')
for x, h in zip(xs, hm):
    print(f'  {x:.3f}   {h:8.0f}')
I = (xs > 0) & (xs < 1)
A = np.column_stack([xs[I] * (1 - xs[I]), xs[I] * (1 - xs[I]) * (2 * xs[I] - 1)])
(L0, L1), *_ = np.linalg.lstsq(A, hm[I], rcond=None)
h50 = float(hm[np.argmin(np.abs(xs - 0.5))])
print(f'\n{LABEL} Redlich-Kister:  L0={L0:.0f}  L1={L1:.0f} J/mol   (H_mix@0.5 = {h50:.0f})', flush=True)
json.dump({'label': LABEL, 'x': list(xs), 'H_mix': list(hm), 'L0': float(L0), 'L1': float(L1)},
          open(HERE / f'ss_mix_{LABEL}.json', 'w'), indent=1)
