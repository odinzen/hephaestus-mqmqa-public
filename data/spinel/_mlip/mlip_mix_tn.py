"""MLIP enthalpy of mixing for the spinel-hercynite (Mg,Fe)Al2O4 A-site join.

No open Fe-Mg spinel-hercynite mixing calorimetry exists (the workspace has endmember
formation enthalpies only), so the excess is computed from MatterSim, the MLIP-for-solids
method proven on clinopyroxene, now on a new (cubic Fd-3m) structure. Normal-spinel
approximation: Fe and Mg mix on the tetrahedral A-site, Al is fixed on the octahedral
B-site (a static relaxation does not swap cation identities, so it gives the normal-spinel
mixing energy directly; the normal/inverse cation inversion is a separate v0.2 study).

The MgAl2O4 conventional cell (COD 9010342, 56 atoms, 8 A-sites) is the framework;
hercynite is the all-Fe A-site substitution, fully relaxed. H_mix(x) = <E(x)> - (1-x)
E(spinel) - x E(hercynite), per formula.
"""
import itertools
import json
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import numpy as np
from ase.io import read
from ase.optimize import FIRE
from ase.filters import FrechetCellFilter
import os; os.environ["TORCHDYNAMO_DISABLE"]="1"

HERE = Path(__file__).resolve().parent
import matgl
from matgl.ext.ase import PESCalculator
CALC = PESCalculator(matgl.load_model("TensorNet-PES-MatPES-PBE-2025.2"))
EV = 96485.0
MAX_ORDER = 6


def relax(atoms):
    atoms = atoms.copy(); atoms.calc = CALC
    FIRE(FrechetCellFilter(atoms), logfile=None).run(fmax=0.03, steps=400)
    return atoms.get_potential_energy()


def main():
    base = read(str(HERE / "cif" / "spinel_9010342.cif"))     # Mg8Al16O32
    mg = [i for i, s in enumerate(base.get_chemical_symbols()) if s == "Mg"]
    n = len(mg); Z = n                                         # 8 A-sites = 8 formulas
    rng = np.random.default_rng(0)
    print(f"cell {base.get_chemical_formula()}, {n} A-sites", flush=True)

    rows = []
    for k in (0, 2, 4, 6, 8):                                  # x = k/8 = 0,.25,.5,.75,1
        combos = list(itertools.combinations(mg, k))
        if len(combos) > MAX_ORDER:
            combos = [combos[i] for i in rng.choice(len(combos), MAX_ORDER, replace=False)]
        es = []
        for combo in combos:
            a = base.copy(); sym = a.get_chemical_symbols()
            for i in combo:
                sym[i] = "Fe"
            a.set_chemical_symbols(sym)
            es.append(relax(a) / Z)
        rows.append(dict(x=k / n, ne=len(es), E=float(np.mean(es)),
                         spread=float(np.std(es)) if len(es) > 1 else 0.0))
        print(f"x={k/n:.3f}: {len(es)} ord, <E>={np.mean(es):.4f} +/- "
              f"{np.std(es)*1000 if len(es)>1 else 0:.1f} meV/fu", flush=True)

    e_sp, e_hc = rows[0]["E"], rows[-1]["E"]
    xs = np.array([r["x"] for r in rows])
    hm = np.array([(r["E"] - ((1 - r["x"]) * e_sp + r["x"] * e_hc)) * EV for r in rows])
    for r, h in zip(rows, hm):
        r["Hmix_Jmol"] = float(h)
        r["Hmix_sig"] = r["spread"] * EV / max(1, r["ne"]) ** 0.5
    interior = (xs > 0) & (xs < 1)
    xi, hi = xs[interior], hm[interior]
    A = np.column_stack([xi * (1 - xi), xi * (1 - xi) * (2 * xi - 1)])
    (L0, L1), *_ = np.linalg.lstsq(A, hi, rcond=None)
    print("\nH_mix (J/mol formula):")
    for r in rows:
        print(f"  x={r['x']:.3f}  {r['Hmix_Jmol']:8.1f}  +/- {r['Hmix_sig']:5.1f}")
    print(f"\nRedlich-Kister fit: L0 = {L0:.1f}  L1 = {L1:.1f} J/mol (per MAl2O4 formula)")
    (HERE / "mlip_tn_result.json").write_text(
        json.dumps(dict(rows=rows, L0=float(L0), L1=float(L1)), indent=1))


if __name__ == "__main__":
    main()