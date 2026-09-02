"""Fe-Mg mixing campaign, SevenNet-0: the excess for the CEF solid solutions that ship without
measured data (orthopyroxene, clinopyroxene, spinel). Olivine runs first as the validated control
(measured L0=12552, L1=4184, H_mix@0.5=+3138; SevenNet olivine ~9746 / +3168). Identical protocol
to ../../olivine/_mlip (VALIDATION.md): Fe substitutes Mg, orderings relaxed cell+positions at
0 GPa and averaged, H_mix a difference vs the two end members so a constant MLIP offset cancels.
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
EV = 96485.0
CALC = SevenNetCalculator(model='7net-0')

def relax(a):
    a = a.copy(); a.calc = CALC
    FIRE(FrechetCellFilter(a), logfile=None).run(fmax=0.03, steps=400)
    return a.get_potential_energy()

def mix(cif, mgpf, label):
    base = read(cif); mg = [i for i, s in enumerate(base.get_chemical_symbols()) if s == 'Mg']
    n = len(mg); Z = n // mgpf; rng = np.random.default_rng(0); rows = []
    print(f'\n=== {label}: {base.get_chemical_formula()}, {n} Mg-sites, Z={Z} ===', flush=True)
    for x in (0.0, 0.25, 0.5, 0.75, 1.0):
        k = round(x * n); combos = list(itertools.combinations(mg, k))
        if len(combos) > 6:
            combos = [combos[i] for i in rng.choice(len(combos), 6, replace=False)]
        es = []
        for combo in combos:
            a = base.copy(); sym = a.get_chemical_symbols()
            for i in combo:
                sym[i] = 'Fe'
            a.set_chemical_symbols(sym); es.append(relax(a) / Z)
        rows.append((k / n, float(np.mean(es)), float(np.std(es)) if len(es) > 1 else 0.))
        print(f'  x={k/n:.3f}: <E>={np.mean(es):.4f} eV/f.u. spread '
              f'{(np.std(es)*1000 if len(es)>1 else 0):.1f} meV', flush=True)
    e0, e1 = rows[0][1], rows[-1][1]; xs = np.array([r[0] for r in rows])
    hm = np.array([(r[1] - ((1 - r[0]) * e0 + r[0] * e1)) * EV for r in rows])
    I = (xs > 0) & (xs < 1)
    A = np.column_stack([xs[I] * (1 - xs[I]), xs[I] * (1 - xs[I]) * (2 * xs[I] - 1)])
    (L0, L1), *_ = np.linalg.lstsq(A, hm[I], rcond=None)
    h50 = float(hm[np.argmin(np.abs(xs - 0.5))])
    print(f'  -> RK L0={L0:.0f} L1={L1:.0f} J/mol   H_mix@0.5={h50:.0f}', flush=True)
    return {'label': label, 'endmembers': base.get_chemical_formula(),
            'x': list(map(float, xs)), 'H_mix': list(map(float, hm)),
            'L0': float(L0), 'L1': float(L1), 'h50': h50}

JOBS = [
    ('cif/forsterite_Mg2SiO4_1572966.cif', 2, 'olivine(control)'),
    ('cif/spinel_MgAl2O4_1010129.cif',     1, 'spinel'),
    ('cif/diopside_CaMgSi2O6_1000007.cif', 1, 'clinopyroxene'),
    ('cif/enstatite_Mg2Si2O6_1000047.cif', 2, 'orthopyroxene'),
]
res = []
for c, m, l in JOBS:
    res.append(mix(str(HERE / c), m, l))
    json.dump(res, open(HERE / 'campaign_results.json', 'w'), indent=1)  # checkpoint after each

print('\n===== CAMPAIGN SUMMARY (Fe-Mg mixing, SevenNet-0, J/mol formula) =====', flush=True)
print(f'{"solution":18s} {"L0":>8s} {"L1":>8s} {"H_mix@0.5":>10s}')
for r in res:
    print(f'{r["label"]:18s} {r["L0"]:8.0f} {r["L1"]:8.0f} {r["h50"]:10.0f}')
print('\ncontrol: olivine measured L0=12552 L1=4184 (H_mix@0.5=+3138); prior SevenNet ~9746/+3168')
print('unknowns below olivine have no calorimetry - MLIP-predicted, olivine-validated (~861 J/mol RMS)')
