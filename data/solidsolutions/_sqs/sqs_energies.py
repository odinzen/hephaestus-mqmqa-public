"""SevenNet-0 Fe-Mg mixing enthalpy on the icet SQS cells from build_sqs.py.

Same model and relaxation as ../_mlip/campaign.py (FIRE, cell + positions, fmax 0.03 eV/A, 0 GPa),
with the step cap raised to 800 for the larger cells. End members are relaxed in the COD cell and
must match campaign.log, which confirms the setup before any SQS number is trusted.

Run in mlip-screen: `conda run -n mlip-screen python sqs_energies.py [mineral ...]`.
"""
import json
import os
import sys
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
CIF = HERE.parent / "_mlip" / "cif"
OUT = HERE / "out"
EV = 96485.0
CALC = SevenNetCalculator(model="7net-0")

# cif, Mg sites per formula unit, campaign.log end members (eV/f.u.), prior H_mix at x=.25/.5/.75
MINERALS = {
    "spinel": ("spinel_MgAl2O4_1010129.cif", 1, (-49.7412, -50.9307), (-2965, -3739, -2485)),
    "clinopyroxene": ("diopside_CaMgSi2O6_1000007.cif", 1, (-73.4425, -74.6303), (-869, 327, 865)),
    "orthopyroxene": ("enstatite_Mg2Si2O6_1000047.cif", 2, (-71.8481, -74.4394), (2193, 1707, 3128)),
}
XS = (0.25, 0.5, 0.75)


def relax(a):
    a = a.copy()
    a.calc = CALC
    converged = FIRE(FrechetCellFilter(a), logfile=None).run(fmax=0.03, steps=800)
    return a.get_potential_energy(), bool(converged)


def n_fu(a, per_fu):
    return sum(s in ("Mg", "Fe") for s in a.get_chemical_symbols()) / per_fu


def rk_fit(h):
    xs = np.array(XS)
    A = np.column_stack([xs * (1 - xs), xs * (1 - xs) * (2 * xs - 1)])
    (L0, L1), *_ = np.linalg.lstsq(A, np.asarray(h, float), rcond=None)
    return float(L0), float(L1)


structures = json.loads((OUT / "structures.json").read_text())
only = set(sys.argv[1:]) or set(MINERALS)
results = json.loads((OUT / "energies.json").read_text()) if (OUT / "energies.json").exists() else {}
for name, (cif, per_fu, prior_ends, prior_h) in MINERALS.items():
    if name not in only:
        continue
    conv = read(str(CIF / cif))
    ends = []
    for fe in (False, True):
        a = conv.copy()
        if fe:
            a.set_chemical_symbols(["Fe" if s == "Mg" else s for s in a.get_chemical_symbols()])
        e, ok = relax(a)
        ends.append(e / n_fu(a, per_fu))
    print(f"\n=== {name}: end members {ends[0]:.4f} / {ends[1]:.4f} eV/f.u. "
          f"(campaign {prior_ends[0]:.4f} / {prior_ends[1]:.4f})", flush=True)
    rows = []
    for s in structures[name]:
        a = read(str(OUT / s["file"]))
        e, ok = relax(a)
        x = s["x"]
        h = (e / n_fu(a, per_fu) - ((1 - x) * ends[0] + x * ends[1])) * EV
        rows.append(dict(sites=s["sites"], atoms=s["atoms"], x=x, Hmix=float(h), converged=ok))
        print(f"  {s['atoms']:4d} atoms ({s['sites']} sites) x={x:.2f}: H_mix {h:7.0f} J/mol"
              f"  converged={ok}", flush=True)
    fits = {}
    for n in sorted({r["sites"] for r in rows}):
        h = [r["Hmix"] for r in rows if r["sites"] == n]
        fits[n] = dict(zip(("L0", "L1"), rk_fit(h)), h=h)
    fits["prior"] = dict(zip(("L0", "L1"), rk_fit(prior_h)), h=list(prior_h))
    print(f"  {'cell':>14s}  {'x=0.25':>7s} {'x=0.50':>7s} {'x=0.75':>7s}  {'L0':>7s} {'L1':>7s}")
    for k, f in fits.items():
        lab = f"{k} sites SQS" if k != "prior" else "prior average"
        print(f"  {lab:>14s}  " + " ".join(f"{v:7.0f}" for v in f["h"]) + f"  {f['L0']:7.0f} {f['L1']:7.0f}")
    results[name] = dict(endmembers=ends, rows=rows, fits={str(k): v for k, v in fits.items()})
    (OUT / "energies.json").write_text(json.dumps(results, indent=1))
