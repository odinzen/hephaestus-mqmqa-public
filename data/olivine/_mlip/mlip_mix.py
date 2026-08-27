"""MLIP validation: does MatterSim reproduce the MEASURED olivine Fe-Mg mixing?

Olivine forsterite-fayalite is the control: its enthalpy of mixing is known from Wood &
Kleppa 1981 solution calorimetry, the subregular Hxs = X_Fe*X_Mg*(2000 + 2000*X_Fe) cal/mol
formula = RK L0 = 12552, L1 = 4184 J/mol (positive - slightly UNFAVOURABLE mixing, the
opposite sign from spinel). If MatterSim, run with the exact same method used for
clinopyroxene and spinel, reproduces Wood & Kleppa, the MLIP-for-solids mixing energies are
validated against experiment and their systematic uncertainty is bounded.

Method identical to spinel: the forsterite cell (COD 1572966, 28 atoms, 8 M-sites) is the
framework; Mg->Fe orderings on the M-sites are relaxed (cell + positions, 0 GPa) and
averaged. H_mix(x) per (Mg,Fe)2SiO4 formula (2 M-sites), compared to Wood-Kleppa.
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
from mattersim.forcefield import MatterSimCalculator

HERE = Path(__file__).resolve().parent
CALC = MatterSimCalculator(load_path="MatterSim-v1.0.0-5M.pth", device="cpu")
EV = 96485.0
MAX_ORDER = 6
# Wood & Kleppa 1981 (measured), RK on (y_Fe - y_Mg), J/mol formula
WK_L0, WK_L1 = 12552.0, 4184.0


def wk(x):
    return x * (1 - x) * (WK_L0 + WK_L1 * (2 * x - 1))


def relax(atoms):
    atoms = atoms.copy(); atoms.calc = CALC
    FIRE(FrechetCellFilter(atoms), logfile=None).run(fmax=0.03, steps=400)
    return atoms.get_potential_energy()


def main():
    base = read(str(HERE / "cif" / "forsterite_1572966.cif"))    # Mg8Si4O16, 8 M-sites
    mg = [i for i, s in enumerate(base.get_chemical_symbols()) if s == "Mg"]
    n = len(mg); Z = n // 2                                       # 8 M-sites = 4 formulas
    rng = np.random.default_rng(0)
    print(f"cell {base.get_chemical_formula()}, {n} M-sites, {Z} formulas", flush=True)

    rows = []
    for k in (0, 2, 4, 6, 8):
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

    e0, e1 = rows[0]["E"], rows[-1]["E"]
    xs = np.array([r["x"] for r in rows])
    hm = np.array([(r["E"] - ((1 - r["x"]) * e0 + r["x"] * e1)) * EV for r in rows])
    for r, h in zip(rows, hm):
        r["Hmix_Jmol"] = float(h)
        r["Hmix_sig"] = r["spread"] * EV / max(1, r["ne"]) ** 0.5
    print("\n x      MLIP H_mix     Wood-Kleppa    diff (J/mol formula)")
    for r in rows:
        print(f" {r['x']:.2f}   {r['Hmix_Jmol']:8.0f} +/-{r['Hmix_sig']:4.0f}   "
              f"{wk(r['x']):8.0f}      {r['Hmix_Jmol']-wk(r['x']):+7.0f}")
    interior = (xs > 0) & (xs < 1)
    rms = float(np.sqrt(np.mean((hm[interior] - np.array([wk(x) for x in xs[interior]])) ** 2)))
    A = np.column_stack([xs[interior] * (1 - xs[interior]),
                         xs[interior] * (1 - xs[interior]) * (2 * xs[interior] - 1)])
    (L0, L1), *_ = np.linalg.lstsq(A, hm[interior], rcond=None)
    print(f"\nMLIP RK fit: L0 = {L0:.0f}, L1 = {L1:.0f}  vs Wood-Kleppa 12552, 4184 J/mol")
    print(f"RMS(MLIP - Wood-Kleppa) = {rms:.0f} J/mol formula")
    (HERE / "mlip_mix_result.json").write_text(
        json.dumps(dict(rows=rows, L0=float(L0), L1=float(L1), rms_vs_wk=rms), indent=1))


if __name__ == "__main__":
    main()
