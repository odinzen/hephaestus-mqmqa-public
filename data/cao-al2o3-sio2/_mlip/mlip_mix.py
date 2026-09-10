"""MLIP melt-mixing enthalpy feasibility test for the aluminate liquids.

Same melt-quench-sample method as data/cao-sio2/_mlip/mlip_mix.py: NVT MD of the two pure
oxides and the 50/50 oxide-fraction mix at a common temperature where all are molten; dH_mix
per oxide unit from the energy difference, so per-atom reference energies cancel. The question
is whether foundation MLIPs AGREE (can anchor the excess) or spread like the spinel case.

Binaries: cas = CaO-Al2O3, as = Al2O3-SiO2, control = CaO-SiO2 (already known to cluster deep,
bounds the systematic error). Oxide units: CaO, AlO1.5 (half of Al2O3), SiO2.
"""
import os, sys, time
import numpy as np
from ase import Atoms
from ase.md.langevin import Langevin
from ase.md.velocitydistribution import MaxwellBoltzmannDistribution
from ase import units

EV_PER_MOL = 96485.0
MW = {"Si": 28.085, "O": 15.999, "Ca": 40.078, "Al": 26.982}

# atoms per formula, n formula units, melt density g/cc, oxide units per formula
SYSTEMS = {
    "SiO2":     dict(atoms={"Si": 1, "O": 2}, nf=32, rho=2.2, upf=1),
    "CaO":      dict(atoms={"Ca": 1, "O": 1}, nf=48, rho=2.8, upf=1),
    "Al2O3":    dict(atoms={"Al": 2, "O": 3}, nf=20, rho=3.0, upf=2),
    "Ca2Al2O5": dict(atoms={"Ca": 2, "Al": 2, "O": 5}, nf=12, rho=2.9, upf=4),  # CaO-AlO1.5 50/50
    "Al2Si2O7": dict(atoms={"Al": 2, "Si": 2, "O": 7}, nf=10, rho=2.5, upf=4),  # AlO1.5-SiO2 50/50
    "CaSiO3":   dict(atoms={"Ca": 1, "Si": 1, "O": 3}, nf=20, rho=2.6, upf=2),  # CaO-SiO2 50/50
}
BINARY = {
    "cas":     ("Ca2Al2O5", "CaO",   "Al2O3"),
    "as":      ("Al2Si2O7", "Al2O3", "SiO2"),
    "control": ("CaSiO3",   "CaO",   "SiO2"),
}


def build(spec, rng):
    counts = {el: n * spec["nf"] for el, n in spec["atoms"].items()}
    symbols = []
    for el, n in counts.items():
        symbols += [el] * n
    natoms = len(symbols)
    mass_g = sum(MW[el] * n for el, n in counts.items()) / 6.02214076e23
    L = (mass_g / spec["rho"] * 1e24) ** (1.0 / 3.0)
    m = int(np.ceil(natoms ** (1.0 / 3.0))) + 1
    grid = [(i, j, k) for i in range(m) for j in range(m) for k in range(m)]
    rng.shuffle(grid)
    a = L / m
    pos = (np.array(grid[:natoms], float) + 0.5) * a
    pos += rng.uniform(-0.15 * a, 0.15 * a, pos.shape)
    rng.shuffle(symbols)
    return Atoms(symbols, positions=pos, cell=[L, L, L], pbc=True), natoms, L


def run(spec, calc, T, melt_ps, eq_ps, samp_ps, dt_fs, seed):
    rng = np.random.default_rng(seed)
    at, natoms, L = build(spec, rng)
    at.calc = calc
    MaxwellBoltzmannDistribution(at, temperature_K=4000)

    def md(temp, ps):
        dyn = Langevin(at, dt_fs * units.fs, temperature_K=temp, friction=0.02)
        e = []
        dyn.attach(lambda: e.append(at.get_potential_energy()), interval=20)
        dyn.run(int(ps * 1000 / dt_fs))
        return np.array(e)

    md(4000.0, melt_ps)
    md(T, eq_ps)
    e = md(T, samp_ps)
    denom = spec["nf"] * spec["upf"]
    return e.mean() / denom, e.std() / np.sqrt(max(len(e), 1)) / denom, natoms, L


def make_calc(model):
    if model == "sevennet":
        from sevenn.calculator import SevenNetCalculator
        return SevenNetCalculator(model="7net-0", device="cpu")
    if model == "mattersim":
        from mattersim.forcefield import MatterSimCalculator
        return MatterSimCalculator(device="cpu")
    if model == "orb":
        from orb_models.forcefield import pretrained
        from orb_models.forcefield.calculator import ORBCalculator
        return ORBCalculator(pretrained.orb_v2(device="cpu"), device="cpu")
    raise SystemExit(f"unknown model {model}")


def main():
    model = sys.argv[1]
    binary = sys.argv[2] if len(sys.argv) > 2 else "cas"
    T = float(sys.argv[3]) if len(sys.argv) > 3 else 3000.0
    melt_ps = float(sys.argv[4]) if len(sys.argv) > 4 else 1.5
    eq_ps = float(sys.argv[5]) if len(sys.argv) > 5 else 3.0
    samp_ps = float(sys.argv[6]) if len(sys.argv) > 6 else 6.0
    seed = int(sys.argv[7]) if len(sys.argv) > 7 else 1234
    dt_fs = 2.0

    calc = make_calc(model)
    binaries = list(BINARY) if binary == "all" else [binary]
    needed = []
    for b in binaries:
        for n in BINARY[b]:
            if n not in needed:
                needed.append(n)
    print(f"# model={model} binary={binary} T={T}K melt/eq/samp={melt_ps}/{eq_ps}/{samp_ps}ps", flush=True)
    u = {}
    for name in needed:
        t0 = time.time()
        uu, sem, nat, L = run(SYSTEMS[name], calc, T, melt_ps, eq_ps, samp_ps, dt_fs, seed)
        u[name] = (uu, sem)
        print(f"  {name:9s} natoms={nat:3d} box={L:5.2f}A U/oxide={uu:9.4f}+-{sem:.4f}eV  ({time.time()-t0:.0f}s)", flush=True)
    for b in binaries:
        mixn, an, bn = BINARY[b]
        dU = u[mixn][0] - 0.5 * u[an][0] - 0.5 * u[bn][0]
        err = np.sqrt(u[mixn][1] ** 2 + 0.25 * u[an][1] ** 2 + 0.25 * u[bn][1] ** 2)
        print(f"  RESULT {model} {b}: dH_mix(x=0.5) = {dU*EV_PER_MOL/1000:+.1f} +- {err*EV_PER_MOL/1000:.1f} kJ/mol-oxide", flush=True)


if __name__ == "__main__":
    main()
