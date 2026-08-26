"""MLIP enthalpy of mixing for the diopside-hedenbergite (Fe,Mg) M1 join.

No open di-hed mixing calorimetry exists, so the excess is computed from a foundation
MLIP (MatterSim), the same triangulation used for the CaO-SiO2 / MgO-SiO2 liquids. The
mixing enthalpy is a difference between the alloy and its endmembers, so the MLIP's
systematic per-atom error largely cancels.

Method: the diopside C2/c cell (COD 1000007, Ca4Mg4Si8O24, 4 M1 sites) is the common
framework. For k = 0..4 Mg->Fe substitutions on M1, every distinct ordering is relaxed
(cell + positions, 0 GPa) with MatterSim; the configurational average energy per formula
gives H_mix(x = k/4) = <E(k)> - (1-x) E(di) - x E(hed). A Redlich-Kister excess is fit.
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
from mattersim.forcefield import MatterSimCalculator

HERE = Path(__file__).resolve().parent
CIF = HERE / "cif" / "diopside_1000007.cif"
CALC = MatterSimCalculator(load_path="MatterSim-v1.0.0-5M.pth", device="cpu")


def relax(atoms):
    atoms = atoms.copy()
    atoms.calc = CALC
    dyn = FIRE(FrechetCellFilter(atoms), logfile=None)
    dyn.run(fmax=0.03, steps=400)
    return atoms.get_potential_energy(), atoms.get_volume()


def main():
    base = read(str(CIF))                       # Ca4Mg4Si8O24, 40 atoms, Z=4
    mg_sites = [i for i, s in enumerate(base.get_chemical_symbols()) if s == "Mg"]
    assert len(mg_sites) == 4, mg_sites
    Z = 4                                        # formulas per cell

    rows = []
    for k in range(5):                           # k Fe of 4 M1 sites -> x = k/4
        energies, vols = [], []
        for combo in itertools.combinations(mg_sites, k):
            a = base.copy()
            sym = a.get_chemical_symbols()
            for i in combo:
                sym[i] = "Fe"
            a.set_chemical_symbols(sym)
            e, v = relax(a)
            energies.append(e / Z)               # per formula
            vols.append(v / Z)
        rows.append(dict(x=k / 4.0, n_orderings=len(energies),
                         E_mean=float(np.mean(energies)),
                         E_min=float(np.min(energies)),
                         V_mean=float(np.mean(vols))))
        print(f"x={k/4:.2f}: {len(energies)} orderings, <E>={np.mean(energies):.4f} "
              f"E_min={np.min(energies):.4f} eV/fu, V={np.mean(vols):.2f} A^3", flush=True)

    e_di, e_hed = rows[0]["E_mean"], rows[-1]["E_mean"]
    EV = 96485.0                                 # eV -> J/mol
    for r in rows:
        ideal = (1 - r["x"]) * e_di + r["x"] * e_hed
        r["Hmix_eV"] = r["E_mean"] - ideal
        r["Hmix_Jmol"] = r["Hmix_eV"] * EV
    xs = np.array([r["x"] for r in rows])
    hm = np.array([r["Hmix_Jmol"] for r in rows])
    # subregular RK: Hmix = x(1-x)[L0 + L1 (1-2x)]
    interior = (xs > 0) & (xs < 1)
    A = np.column_stack([xs[interior] * (1 - xs[interior]),
                         xs[interior] * (1 - xs[interior]) * (1 - 2 * xs[interior])])
    (L0, L1), *_ = np.linalg.lstsq(A, hm[interior], rcond=None)
    print("\nH_mix (J/mol formula):")
    for r in rows:
        print(f"  x={r['x']:.2f}  {r['Hmix_Jmol']:8.1f}")
    print(f"\nRedlich-Kister fit: L0 = {L0:.1f}  L1 = {L1:.1f} J/mol "
          f"(per formula, i.e. per mole of mixing cation)")
    print(f"H_mix(0.5) = {hm[xs == 0.5][0]:.1f} J/mol; endmember cell V "
          f"di {rows[0]['V_mean']:.2f} hed {rows[-1]['V_mean']:.2f} A^3 (expt ~109.7/112.6)")
    (HERE / "mlip_mix_result.json").write_text(
        json.dumps(dict(rows=rows, L0=float(L0), L1=float(L1)), indent=1))


if __name__ == "__main__":
    main()
