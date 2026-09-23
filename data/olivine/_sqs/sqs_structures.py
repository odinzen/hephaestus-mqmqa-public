"""icet SQS for olivine (Mg,Fe)2SiO4, checked against the brute-force pick in _dft/build_sqs.py.

Run in the `icet` conda env via `conda run -n icet python sqs_structures.py` (calling that env's
python.exe directly fails a DLL load on this machine). Energies: sqs_energies.py in mlip-screen.
"""
import itertools
import json
from pathlib import Path

import numpy as np
from ase.io import read, write
from icet import ClusterSpace
from icet.tools.structure_generation import (_get_sqs_cluster_vector, compare_cluster_vectors,
                                             generate_sqs, generate_sqs_by_enumeration)

OLV = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)

prim = read(str(OLV / "_mlip" / "cif" / "forsterite_1572966.cif"))
M = [i for i, s in enumerate(prim.get_chemical_symbols()) if s == "Mg"]
chem = [["Mg", "Fe"] if s == "Mg" else [s] for s in prim.get_chemical_symbols()]
cs = ClusterSpace(prim, cutoffs=[7.0, 4.5], chemical_symbols=chem)
AS_LIST = cs.as_list


def with_fe(fe_idx, base=prim):
    a = base.copy()
    sym = a.get_chemical_symbols()
    for i in fe_idx:
        sym[i] = "Fe"
    a.set_chemical_symbols(sym)
    return a


def score(atoms, x):
    """icet's own SQS objective with optimality_weight=None, sum |cv - random target|."""
    target = _get_sqs_cluster_vector(cs, {"A": {"Fe": x, "Mg": 1 - x}})
    cv = cs.get_cluster_vector(atoms)
    return float(compare_cluster_vectors(cv, target, AS_LIST, optimality_weight=None)), cv, target


# label M1/M2 by which point function a single Fe on that site moves
ref = cs.get_cluster_vector(prim)
label = {}
for i in M:
    d = cs.get_cluster_vector(with_fe([i])) - ref
    label[i] = "M1" if abs(d[1]) > abs(d[2]) else "M2"
m1 = [i for i in M if label[i] == "M1"]
print("M1 sites:", m1, " M2 sites:", [i for i in M if label[i] == "M2"])

rows = []
for combo in itertools.combinations(M, 4):
    s, cv, tgt = score(with_fe(combo), 0.5)
    rows.append((s, combo, sum(i in m1 for i in combo), cv))
rows.sort(key=lambda r: r[0])
scores = np.array([r[0] for r in rows])

brute = read(str(OLV / "_dft" / "ordering_geoms" / "sqs_unrelaxed.xyz"))
bfe = tuple(i for i, s in enumerate(brute.get_chemical_symbols()) if s == "Fe")
bs, bcv, tgt = score(brute, 0.5)
brank = int(np.sum(scores < bs - 1e-9)) + 1
print(f"\n70 arrangements at x=0.5 (28-atom cell): icet score {scores.min():.3f} .. {scores.max():.3f}, "
      f"{len(np.unique(scores.round(6)))} distinct values")
print(f"brute-force pick Fe={bfe}: score {bs:.3f}, rank {brank}/70 "
      f"(ties at best: {int(np.sum(np.isclose(scores, scores[0])))}), Fe on M1 = {sum(i in m1 for i in bfe)}/4")
print(f"  its point correlations M1,M2 = {bcv[1]:+.2f},{bcv[2]:+.2f} (random: 0,0)")
for s, c, n1, cv in rows[:3]:
    print(f"icet top: Fe={c} score {s:.3f}, Fe on M1 {n1}/4, point corr {cv[1]:+.2f},{cv[2]:+.2f}")

enum = generate_sqs_by_enumeration(cs, max_size=1, target_concentrations={"A": {"Fe": 0.5, "Mg": 0.5}},
                                   optimality_weight=None)
es = score(enum, 0.5)[0]
print(f"generate_sqs_by_enumeration(max_size=1) score {es:.3f} (should equal the best, {scores[0]:.3f})")
write(str(OUT / "icet_sqs_28_x0.50.xyz"), enum)

summary = dict(brute_rank=brank, brute_score=bs, best28=float(scores[0]), worst28=float(scores[-1]),
               brute_fe_on_m1=sum(i in m1 for i in bfe), cells=[])
# 28-atom SQS at x=0.25/0.75 by enumeration too, so the energy test has a full 28-atom series
for x in (0.25, 0.75):
    a = generate_sqs_by_enumeration(cs, max_size=1, target_concentrations={"A": {"Fe": x, "Mg": 1 - x}},
                                    optimality_weight=None)
    print(f"28-atom enumeration x={x:.2f}: score {score(a, x)[0]:.3f}")
    write(str(OUT / f"icet_sqs_28_x{x:.2f}.xyz"), a)
    summary["cells"].append(dict(atoms=28, x=x, score=score(a, x)[0]))
summary["cells"].append(dict(atoms=28, x=0.5, score=es))

# larger cells by simulated annealing, where brute force is no longer possible
for reps in ([2, 1, 1], [2, 1, 2]):
    n = int(np.prod(reps))
    for x in (0.25, 0.5, 0.75):
        tc = {"A": {"Fe": x, "Mg": 1 - x}}
        best = None
        for seed in range(3):
            a = generate_sqs(cs, max_size=n, target_concentrations=tc, include_smaller_cells=False,
                             n_steps=30000, optimality_weight=None, random_seed=seed)
            s = score(a, x)[0]
            if best is None or s < best[0]:
                best = (s, a)
        s, a = best
        print(f"{len(a)}-atom cell ({8 * n} M-sites) x={x:.2f}: best-of-3 annealing score {s:.3f}")
        write(str(OUT / f"icet_sqs_{len(a)}_x{x:.2f}.xyz"), a)
        summary["cells"].append(dict(atoms=len(a), x=x, score=s))
(OUT / "structures.json").write_text(json.dumps(summary, indent=1))
