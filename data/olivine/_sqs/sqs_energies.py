"""SevenNet-0 H_mix of olivine on icet SQS cells, same relaxation as _mlip/olivine_control.py."""
import json
import os
import warnings
from pathlib import Path

os.environ["TORCHDYNAMO_DISABLE"] = "1"
warnings.filterwarnings("ignore")
import numpy as np
from ase.filters import FrechetCellFilter
from ase.io import read
from ase.optimize import FIRE
from sevenn.calculator import SevenNetCalculator

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
CIF = HERE.parent / "_mlip" / "cif" / "forsterite_1572966.cif"
CALC = SevenNetCalculator(model="7net-0")
EV = 96485.0
WK_L0, WK_L1 = 12552.0, 4184.0
wk = lambda x: x * (1 - x) * (WK_L0 + WK_L1 * (2 * x - 1))
PRIOR = {0.25: 1236, 0.5: 3168, 0.75: 1444}   # olv_sevennet.log, 6-ordering average, 28 atoms


def relax(a):
    a = a.copy()
    a.calc = CALC
    opt = FIRE(FrechetCellFilter(a), logfile=None)
    ok = opt.run(fmax=0.03, steps=800)
    fmax = float(np.abs(a.get_forces()).max())
    return a.get_potential_energy(), ok, fmax


def per_fu(a, e):
    return e / (sum(s in ("Mg", "Fe") for s in a.get_chemical_symbols()) / 2)


base = read(str(CIF))
ends = {}
for x, sym in ((0.0, "Mg"), (1.0, "Fe")):
    a = base.copy()
    a.set_chemical_symbols(["Fe" if (s == "Mg" and sym == "Fe") else s for s in a.get_chemical_symbols()])
    e, ok, fm = relax(a)
    ends[x] = per_fu(a, e)
    print(f"endmember x={x:.0f}: {ends[x]:.4f} eV/fu converged={ok}", flush=True)

results = []
for n in (28, 56, 112):
    for x in (0.25, 0.5, 0.75):
        a = read(str(OUT / f"icet_sqs_{n}_x{x:.2f}.xyz"))
        e, ok, fm = relax(a)
        h = (per_fu(a, e) - ((1 - x) * ends[0.0] + x * ends[1.0])) * EV
        results.append(dict(atoms=n, x=x, Hmix=h, converged=bool(ok), fmax=fm))
        print(f"{n:4d} atoms x={x:.2f}: H_mix {h:7.0f} J/mol  (WK {wk(x):5.0f}, 6-ord avg {PRIOR[x]:5.0f})"
              f"  converged={ok}", flush=True)

print("\ncell   L0      L1     RMS vs Wood-Kleppa (J/mol formula)")
xs = np.array([0.25, 0.5, 0.75])
A = np.column_stack([xs * (1 - xs), xs * (1 - xs) * (2 * xs - 1)])
wkv = np.array([wk(x) for x in xs])
fits = {}
for n in (28, 56, 112):
    h = np.array([r["Hmix"] for r in results if r["atoms"] == n])
    (L0, L1), *_ = np.linalg.lstsq(A, h, rcond=None)
    rms = float(np.sqrt(np.mean((h - wkv) ** 2)))
    fits[n] = dict(L0=float(L0), L1=float(L1), rms=rms)
    print(f"{n:4d}  {L0:6.0f}  {L1:6.0f}   {rms:5.0f}")
h = np.array([PRIOR[x] for x in xs])
(L0, L1), *_ = np.linalg.lstsq(A, h, rcond=None)
print(f"prior 6-ord avg (28 atoms): L0 {L0:.0f} L1 {L1:.0f} RMS {np.sqrt(np.mean((h - wkv) ** 2)):.0f}")
print(f"Wood-Kleppa: L0 {WK_L0:.0f} L1 {WK_L1:.0f}")
(OUT / "energies.json").write_text(json.dumps(dict(endmembers=ends, results=results, fits=fits), indent=1))
