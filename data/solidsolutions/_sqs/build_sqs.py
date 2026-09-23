"""icet SQS cells for the Fe-Mg joins in spinel, clinopyroxene and orthopyroxene.

Replaces the "average a handful of random orderings in one unit cell" step of
../_mlip/campaign.py. The olivine control (../../olivine/_sqs) showed an 8-site cell cannot hold a
random arrangement at x=0.5 (it forces a 3:1 M1:M2 split and lands 2.7 kJ/mol low), while 16- and
32-site SQS agree to ~100 J/mol. So each mineral gets SQS at 16 and 32 mixing sites.

Supercells are the most compact shape of the requested size (ase find_optimal_cell_shape), so the
pair cutoff does not alias along a short axis. Pair/triplet cutoffs are the smallest giving each
mineral a usable number of correlations (spinel has few Mg-Mg shells inside 7 A).

Where the mixing sites fall into more than one symmetry class (orthopyroxene M1/M2), icet's
annealer is free to trade the M1:M2 balance for better pair terms, and at 32 sites it did, giving a
partly ordered cell. Those minerals use a constrained annealer instead: Fe is split evenly across
the classes and swaps stay within a class, scored with icet's own objective.

Run in the `icet` env: `conda run -n icet python build_sqs.py [mineral ...]`. Energies:
sqs_energies.py.
"""
import json
import sys
from pathlib import Path

import numpy as np
from ase.build import find_optimal_cell_shape, make_supercell
from ase.io import read, write
from icet import ClusterSpace
from icet.tools.structure_generation import (_get_sqs_cluster_vector, compare_cluster_vectors,
                                             generate_sqs_from_supercells)

HERE = Path(__file__).resolve().parent
CIF = HERE.parent / "_mlip" / "cif"
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

# cif, cutoffs, cell sizes in mixing sites. The 16-site opx cell is the COD cell itself (5.2 A
# along c), so it aliases; 64 sites is added to check convergence.
MINERALS = {
    "spinel": ("spinel_MgAl2O4_1010129.cif", [10.0, 6.0], (16, 32)),
    "clinopyroxene": ("diopside_CaMgSi2O6_1000007.cif", [9.0, 5.5], (16, 32)),
    "orthopyroxene": ("enstatite_Mg2Si2O6_1000047.cif", [7.0, 4.5], (16, 32, 64)),
}
XS = (0.25, 0.5, 0.75)
SEEDS = 3
N_STEPS = 40000


def min_image(atoms):
    """Shortest lattice translation of the supercell, a check against aliasing."""
    c = atoms.cell
    shifts = [np.array([i, j, k]) for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1)
              if (i, j, k) != (0, 0, 0)]
    return min(np.linalg.norm(s @ c) for s in shifts)


def site_classes(cs, sc, as_list):
    """Mixing-site indices of supercell sc grouped by point orbit (M1, M2, ...)."""
    points = [i for i, o in enumerate(as_list) if o["order"] == 1]
    mg = sc.copy()
    mg.set_chemical_symbols(["Mg" if s in ("Mg", "Fe") else s for s in sc.get_chemical_symbols()])
    cv0 = cs.get_cluster_vector(mg)
    classes = {p: [] for p in points}
    for i, s in enumerate(mg.get_chemical_symbols()):
        if s != "Mg":
            continue
        a = mg.copy()
        a[i].symbol = "Fe"
        d = np.abs(cs.get_cluster_vector(a) - cv0)
        classes[max(points, key=lambda p: d[p])].append(i)
    return list(classes.values())


def constrained_sqs(cs, as_list, sc, x, target, seed, T_start=5.0, T_stop=0.001):
    """Anneal toward the random target with Fe fixed at fraction x within every site class."""
    FE, MG = 26, 12
    rng = np.random.default_rng(seed)
    a = sc.copy()
    # per class: [Fe indices, Mg indices], kept in step with a.numbers so swaps are O(1)
    pools = []
    for idx in site_classes(cs, sc, as_list):
        idx = np.array(idx)
        fe = rng.choice(idx, round(x * len(idx)), replace=False)
        mg = np.setdiff1d(idx, fe)
        a.numbers[mg], a.numbers[fe] = MG, FE
        if len(fe) and len(mg):
            pools.append([fe, mg])

    def score():
        return float(compare_cluster_vectors(cs.get_cluster_vector(a), target, as_list,
                                             optimality_weight=None))

    s = score()
    best = (s, a.numbers.copy())
    for step in range(N_STEPS):
        T = T_start * (T_stop / T_start) ** (step / N_STEPS)
        fe, mg = pools[rng.integers(len(pools))]
        p, q = rng.integers(len(fe)), rng.integers(len(mg))
        i, j = fe[p], mg[q]
        a.numbers[i], a.numbers[j] = MG, FE
        s_new = score()
        if s_new <= s or rng.random() < np.exp(-(s_new - s) / T):
            s = s_new
            fe[p], mg[q] = j, i
            if s < best[0]:
                best = (s, a.numbers.copy())
        else:
            a.numbers[i], a.numbers[j] = FE, MG
    a.numbers[:] = best[1]
    return a


def main():
    only = set(sys.argv[1:]) or set(MINERALS)
    summary = json.loads((OUT / "structures.json").read_text()) if (OUT / "structures.json").exists() else {}
    for name, (cif, cutoffs, sites) in MINERALS.items():
        if name not in only:
            continue
        conv = read(str(CIF / cif))
        chem = [["Mg", "Fe"] if s == "Mg" else [s] for s in conv.get_chemical_symbols()]
        cs = ClusterSpace(conv, cutoffs=cutoffs, chemical_symbols=chem)
        prim = cs.primitive_structure
        n_prim = next(len(s.indices) for s in cs.get_sublattices(prim) if "Fe" in s.chemical_symbols)
        print(f"\n=== {name}: {len(prim)}-atom primitive, {n_prim} mixing sites, {len(cs)} cluster functions,"
              f" cutoffs {cutoffs}", flush=True)
        as_list = cs.as_list  # a property that icet rebuilds on every access (~5 ms)
        n_points = sum(o["order"] == 1 for o in as_list)
        summary[name] = []
        for n_sites in sites:
            size = n_sites // n_prim
            P = find_optimal_cell_shape(prim.cell, size, "sc")
            sc = make_supercell(prim, P)
            for x in XS:
                tc = {"A": {"Fe": x, "Mg": 1 - x}}
                target = _get_sqs_cluster_vector(cs, tc)
                best = None
                for seed in range(SEEDS):
                    if n_points > 1:
                        a = constrained_sqs(cs, as_list, sc, x, target, seed)
                    else:
                        a = generate_sqs_from_supercells(cs, [sc], target_concentrations=tc, n_steps=N_STEPS,
                                                         optimality_weight=None, random_seed=seed)
                    s = float(compare_cluster_vectors(cs.get_cluster_vector(a), target, as_list,
                                                      optimality_weight=None))
                    if best is None or s < best[0]:
                        best = (s, a)
                s, a = best
                n_fe = sum(t == "Fe" for t in a.get_chemical_symbols())
                cv = cs.get_cluster_vector(a)
                points = [round(float(cv[i]), 3) for i, o in enumerate(as_list) if o["order"] == 1]
                print(f"  {len(a):4d} atoms ({n_sites} sites, min image {min_image(a):.1f} A) x={x:.2f}: "
                      f"score {s:.3f}, n_Fe {n_fe}, point corr {points} (target {target[1]:+.2f})", flush=True)
                fname = f"{name}_{n_sites}sites_x{x:.2f}.xyz"
                write(str(OUT / fname), a)
                summary[name].append(dict(sites=n_sites, atoms=len(a), x=x, score=s, n_fe=n_fe,
                                          points=points, min_image=min_image(a), file=fname))
        (OUT / "structures.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
