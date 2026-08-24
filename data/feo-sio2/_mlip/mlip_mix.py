"""Independent MLIP estimate of the FeO-SiO2 liquid enthalpy of mixing.

FeO-SiO2 (iron-saturated, Fe2+) has no digitized liquid activities in the trove, so the
phase-diagram invariant (fayalite congruent melting, Bowen & Schairer 1932) is the primary
constraint on the liquid depth. This gives an INDEPENDENT second number: a foundation
MLIP's melt-mixing enthalpy, to cross-check and (bias-corrected) anchor that depth. Mirrors
data/mgo-sio2/_mlip/mlip_mix.py.

Method: melt-quench-sample MD of the endmember and mixed liquids at a common temperature
where all are molten (SiO2 melts ~1996 K; sample hot enough for silica mobility):
  pure SiO2, pure FeO, FeSiO3 (x_SiO2 = 0.5), Fe2SiO4 (x_SiO2 = 1/3).
Enthalpy of mixing per mole of OXIDE FORMULA UNIT (~1 bar, PV negligible):
  dU_mix = u_mixed - (1-x)*u_FeO - x*u_SiO2
with u_i the average potential energy per oxide formula unit. Element counts are conserved
in this combination, so the MLIP per-atom reference energies cancel. NVT at estimated melt
densities (a difference quantity, so density error largely cancels). Reported as a CLUE with
its model spread, not a verdict.
"""

import sys
import numpy as np
from ase import Atoms
from ase.md.langevin import Langevin
from ase.md.velocitydistribution import MaxwellBoltzmannDistribution
from ase import units

EV_PER_MOL = 96485.0  # eV -> J/mol

# composition -> (atoms per formula, n_formula_units, melt density g/cc, oxide units/f, x_SiO2)
SYSTEMS = {
    "SiO2":    dict(atoms={"Si": 1, "O": 2}, nf=18, rho=2.2, units_per_f=1, x=1.0),
    "FeO":     dict(atoms={"Fe": 1, "O": 1}, nf=27, rho=4.6, units_per_f=1, x=0.0),
    "FeSiO3":  dict(atoms={"Fe": 1, "Si": 1, "O": 3}, nf=11, rho=3.4, units_per_f=2, x=0.5),
    "Fe2SiO4": dict(atoms={"Fe": 2, "Si": 1, "O": 4}, nf=8, rho=3.75, units_per_f=3, x=1.0/3.0),
}
MW = {"Si": 28.085, "O": 15.999, "Fe": 55.845}


def build_liquid_seed(spec, rng):
    counts = {el: n * spec["nf"] for el, n in spec["atoms"].items()}
    symbols = []
    for el, n in counts.items():
        symbols += [el] * n
    natoms = len(symbols)
    mass_g = sum(MW[el] * n for el, n in counts.items()) / 6.02214076e23
    vol_A3 = mass_g / spec["rho"] * 1e24
    L = vol_A3 ** (1.0 / 3.0)
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
    at, natoms, L = build_liquid_seed(spec, rng)
    at.calc = calc
    MaxwellBoltzmannDistribution(at, temperature_K=4200)

    def md(temp, ps):
        dyn = Langevin(at, dt_fs * units.fs, temperature_K=temp, friction=0.02)
        energies = []
        dyn.attach(lambda: energies.append(at.get_potential_energy()), interval=20)
        dyn.run(int(ps * 1000 / dt_fs))
        return np.array(energies)

    md(min(4200.0, T + 500.0), melt_ps)  # melt just above the sample T (dense FeO is
    md(T, eq_ps)                          # unstable if melted too hot -> slow/pathological)
    e = md(T, samp_ps)
    denom = spec["nf"] * spec["units_per_f"]
    return e.mean() / denom, e.std() / np.sqrt(max(len(e), 1)) / denom, natoms, L


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "mattersim"
    T = float(sys.argv[2]) if len(sys.argv) > 2 else 2800.0
    melt_ps = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
    eq_ps = float(sys.argv[4]) if len(sys.argv) > 4 else 4.0
    samp_ps = float(sys.argv[5]) if len(sys.argv) > 5 else 8.0
    seed = int(sys.argv[6]) if len(sys.argv) > 6 else 1234
    dt_fs = 2.0

    if model == "mattersim":
        from mattersim.forcefield import MatterSimCalculator
        calc = MatterSimCalculator()
    elif model == "orb":
        from orb_models.forcefield import pretrained
        from orb_models.forcefield.calculator import ORBCalculator
        calc = ORBCalculator(pretrained.orb_v2(device="cpu"), device="cpu")
    else:
        raise SystemExit(f"unknown model {model}")

    print(f"# model={model} T={T}K melt/eq/samp={melt_ps}/{eq_ps}/{samp_ps} ps seed={seed}", flush=True)
    u = {}
    for name, spec in SYSTEMS.items():
        uu, sem, nat, L = run(spec, calc, T, melt_ps, eq_ps, samp_ps, dt_fs, seed)
        u[name] = (uu, sem)
        print(f"  {name:8s} natoms={nat:3d} box={L:5.2f}A  U/oxide-unit={uu:9.4f} +-{sem:.4f} eV", flush=True)

    for name in ("FeSiO3", "Fe2SiO4"):
        x = SYSTEMS[name]["x"]
        dU = u[name][0] - (1 - x) * u["FeO"][0] - x * u["SiO2"][0]
        err = np.sqrt(u[name][1]**2 + (1 - x)**2 * u["FeO"][1]**2 + x**2 * u["SiO2"][1]**2)
        print(f"\n  dH_mix(x_SiO2={x:.3f}, {name}) = {dU*EV_PER_MOL/1000:+.1f} "
              f"+- {err*EV_PER_MOL/1000:.1f} kJ/mol-oxide-unit  ({dU:+.4f} eV)", flush=True)


if __name__ == "__main__":
    main()
