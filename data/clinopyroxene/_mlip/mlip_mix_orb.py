"""Refined MLIP di-hed mixing enthalpy on a larger cell (8 M1 sites).

The 40-atom cell's per-ordering spread (~1 kJ) swamped the sub-kJ mixing signal. Here the
diopside cell is doubled (2x1x1, 80 atoms, 8 M1 sites); at each composition several
distinct Fe/Mg orderings are relaxed and averaged, giving H_mix with a spread-based
uncertainty. The finer site count also samples x = 0.125..0.875.
"""
import itertools
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import numpy as np
from ase.io import read
from ase.optimize import FIRE
from ase.filters import FrechetCellFilter
import os; os.environ["TORCHDYNAMO_DISABLE"]="1"
from orb_models.forcefield import pretrained
from orb_models.forcefield.calculator import ORBCalculator

HERE = Path(__file__).resolve().parent
CALC = ORBCalculator(pretrained.orb_v2(device="cpu"), device="cpu")
MAX_ORDER = 8            # cap orderings per composition
EV = 96485.0


def relax(atoms):
    atoms = atoms.copy(); atoms.calc = CALC
    FIRE(FrechetCellFilter(atoms), logfile=None).run(fmax=0.02, steps=500)
    return atoms.get_potential_energy()


def orderings(sites, k, rng):
    all_c = list(itertools.combinations(sites, k))
    if len(all_c) <= MAX_ORDER:
        return all_c
    idx = rng.choice(len(all_c), MAX_ORDER, replace=False)
    return [all_c[i] for i in idx]


def main():
    base = read(str(HERE / "cif" / "diopside_1000007.cif")) * (2, 1, 1)   # 80 atoms
    mg = [i for i, s in enumerate(base.get_chemical_symbols()) if s == "Mg"]
    n = len(mg)                                    # 8 M1 sites
    Z = n                                          # formulas per cell (1 M1 = 1 formula)
    rng = np.random.default_rng(0)
    print(f"cell {base.get_chemical_formula()}, {n} M1 sites", flush=True)

    rows = []
    for k in range(n + 1):
        es = []
        for combo in orderings(mg, k, rng):
            a = base.copy(); sym = a.get_chemical_symbols()
            for i in combo:
                sym[i] = "Fe"
            a.set_chemical_symbols(sym)
            es.append(relax(a) / Z)
        rows.append(dict(x=k / n, n=len(es), E=float(np.mean(es)),
                         spread=float(np.std(es)) if len(es) > 1 else 0.0))
        print(f"x={k/n:.3f}: {len(es)} ord, <E>={np.mean(es):.4f} +/- "
              f"{np.std(es)*1000 if len(es)>1 else 0:.1f} meV/fu", flush=True)

    e_di, e_hed = rows[0]["E"], rows[-1]["E"]
    for r in rows:
        r["Hmix_Jmol"] = (r["E"] - ((1 - r["x"]) * e_di + r["x"] * e_hed)) * EV
        r["Hmix_sig"] = r["spread"] * EV / max(1, r["n"]) ** 0.5
    xs = np.array([r["x"] for r in rows]); hm = np.array([r["Hmix_Jmol"] for r in rows])
    interior = (xs > 0) & (xs < 1)
    xi, hi = xs[interior], hm[interior]
    L0_sym = float(np.sum(hi * xi * (1 - xi)) / np.sum((xi * (1 - xi)) ** 2))   # symmetric LSQ
    A = np.column_stack([xi * (1 - xi), xi * (1 - xi) * (1 - 2 * xi)])
    (L0, L1), *_ = np.linalg.lstsq(A, hi, rcond=None)

    print("\nH_mix (J/mol formula), with per-mean sigma:")
    for r in rows:
        print(f"  x={r['x']:.3f}  {r['Hmix_Jmol']:8.1f}  +/- {r['Hmix_sig']:5.1f}")
    print(f"\nsymmetric L0 = {L0_sym:.1f} J/mol")
    print(f"subregular   L0 = {L0:.1f}  L1 = {L1:.1f} J/mol")
    (HERE / "mlip_mix2_orb_result.json").write_text(
        json.dumps(dict(rows=rows, L0_sym=L0_sym, L0=float(L0), L1=float(L1)), indent=1))


if __name__ == "__main__":
    main()
