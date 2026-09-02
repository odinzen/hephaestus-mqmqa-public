"""Pick the x=0.5 Fe/Mg SQS on the 8 forsterite M-sites by exhaustive enumeration.

For 8 octahedral M-sites at 4 Fe / 4 Mg there are only C(8,4)=70 arrangements, so the global
best special quasirandom structure is found by brute force, not Monte Carlo. Spin variable
sigma = +1 (Fe) / -1 (Mg); random mixing at x=0.5 has every pair correlation = 0. We pick the
arrangement whose shell-resolved pair correlations sit closest to zero (nearer shells weighted
more), which is the standard SQS objective.
"""
import itertools
from pathlib import Path
import numpy as np
from ase.io import read, write

HERE = Path(__file__).resolve().parent
base = read(str(HERE.parent / "_mlip" / "cif" / "forsterite_1572966.cif"))
sym = base.get_chemical_symbols()
M = [i for i, s in enumerate(sym) if s == "Mg"]            # 8 octahedral M-sites
assert len(M) == 8, f"expected 8 M-sites, got {len(M)}"

cell = np.array(base.get_cell())
pos = base.get_positions()[M]                              # 8 M-site cartesian positions

# Build periodic images of the M-sublattice (+/-1 in each direction) and remember each
# image's parent site, so a site's neighbor shells include its periodic partners.
shifts = np.array([[i, j, k] for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1)])
img_pos, img_parent = [], []
for s in shifts:
    t = s @ cell
    for p in range(8):
        img_pos.append(pos[p] + t)
        img_parent.append(p)
img_pos = np.array(img_pos)
img_parent = np.array(img_parent)

# distances from each original site to every image; collect shell radii
D = np.linalg.norm(pos[:, None, :] - img_pos[None, :, :], axis=2)     # (8, 216)
d_round = np.round(D, 2)
shell_r = sorted({d for d in d_round.flatten() if d > 0.01})[:4]      # first 4 M-M shells

# directed neighbor pairs (i -> parent_j) for each shell
shell_pairs = []
for r in shell_r:
    pairs = []
    for i in range(8):
        for jimg in np.where(np.isclose(d_round[i], r))[0]:
            pairs.append((i, img_parent[jimg]))
    shell_pairs.append(pairs)
    print(f"shell d={r:.2f} A : {len(pairs)} directed pairs ({len(pairs)//8} neighbors/site)")

W = [1.0, 0.5, 0.25, 0.12]                     # weight nearer shells more

def correlations(fe_local):
    sig = np.full(8, -1.0)
    sig[list(fe_local)] = 1.0
    return [float(np.mean([sig[i] * sig[j] for i, j in ps])) for ps in shell_pairs]

best = None
for combo in itertools.combinations(range(8), 4):
    c = correlations(combo)
    obj = sum(w * abs(v) for w, v in zip(W, c))
    key = (round(obj, 6), round(max(abs(v) for v in c), 6))
    if best is None or key < best[0]:
        best = (key, combo, c)

_, fe_local, corr = best
fe_sites = [M[i] for i in fe_local]
print("\nrandom target per shell: 0")
print("SQS correlations       :", [f"{v:+.3f}" for v in corr])
print("objective              :", best[0][0], " max|corr|:", best[0][1])
print("Fe on M-site indices   :", fe_sites)

out = base.copy()
s2 = out.get_chemical_symbols()
for i in fe_sites:
    s2[i] = "Fe"
out.set_chemical_symbols(s2)
(HERE / "ordering_geoms").mkdir(exist_ok=True)
write(str(HERE / "ordering_geoms" / "sqs_unrelaxed.xyz"), out)
print("\nwrote ordering_geoms/sqs_unrelaxed.xyz  formula", out.get_chemical_formula())
