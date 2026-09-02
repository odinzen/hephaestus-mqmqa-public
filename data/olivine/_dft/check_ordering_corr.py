"""Shell pair-correlations for the arrangements we actually ran, to find a convergeable one
that is also near-random (correlations near 0 in the near-neighbor shells)."""
from pathlib import Path
import numpy as np
from ase.io import read

HERE = Path(__file__).resolve().parent
base = read(str(HERE.parent / "_mlip" / "cif" / "forsterite_1572966.cif"))
M = [i for i, s in enumerate(base.get_chemical_symbols()) if s == "Mg"]
cell = np.array(base.get_cell()); pos = base.get_positions()[M]
shifts = np.array([[i, j, k] for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1)])
img_pos, img_parent = [], []
for s in shifts:
    t = s @ cell
    for p in range(8): img_pos.append(pos[p] + t); img_parent.append(p)
img_pos = np.array(img_pos); img_parent = np.array(img_parent)
D = np.round(np.linalg.norm(pos[:, None, :] - img_pos[None, :, :], axis=2), 2)
shell_r = sorted({d for d in D.flatten() if d > 0.01})[:4]
shell_pairs = [[(i, img_parent[j]) for i in range(8) for j in np.where(np.isclose(D[i], r))[0]] for r in shell_r]

def corr(fe_local):
    sig = np.full(8, -1.0); sig[list(fe_local)] = 1.0
    return [round(float(np.mean([sig[i] * sig[j] for i, j in ps])), 3) for ps in shell_pairs]

# reproduce the exact ordering selection from gen_orderings.py (rng seed 7)
rng = np.random.default_rng(7); seen = {tuple(sorted(M[:4]))}; orders = []
while len(orders) < 4:
    pick = tuple(sorted(rng.choice(M, 4, replace=False)))
    if pick in seen: continue
    seen.add(pick); orders.append(list(pick))

arr = {"x50_a": M[:4], "ord2": orders[0], "ord3": orders[1], "ord4": orders[2], "ord5": orders[3]}
status = {"x50_a": "DONE +16100", "ord2": "converged, ~+767 (8 steps)", "ord3": "converged, ~+1045",
          "ord4": "PATHOLOGICAL (never converged)", "ord5": "converged, partial"}
print(f"shells (A): {[float(r) for r in shell_r]}   random target: [0, 0, 0, 0]\n")
for k, fe in arr.items():
    fe_local = [M.index(i) for i in fe]
    c = corr(fe_local)
    near = abs(c[0]) + abs(c[1])   # shells 1-2 deviation from random
    print(f"{k:6} Fe@{sorted(fe)}  corr={c}  |shell1|+|shell2|={near:.2f}   [{status[k]}]")
