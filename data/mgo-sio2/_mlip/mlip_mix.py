"""Independent MLIP estimate of the MgO-SiO2 liquid enthalpy of mixing.

MgO-SiO2 has no measured liquid activities (unlike CaO-SiO2), so the phase-diagram
invariants are the primary constraint on the liquid depth. This gives an INDEPENDENT
third number: a foundation MLIP's melt-mixing enthalpy, to cross-check (and, if it
agrees after bias correction, anchor) the depth the invariants imply.

Method: melt-quench-sample MD of the endmember and mixed liquids at a common
temperature where all are molten (MgO melts ~3098 K, so sample at 3200 K):
  pure SiO2, pure MgO, MgSiO3 (x_SiO2 = 0.5), Mg2SiO4 (x_SiO2 = 1/3).
Enthalpy of mixing per mole of OXIDE FORMULA UNIT (at ~1 bar, PV negligible):
  dU_mix = u_mixed - (1-x)*u_MgO - x*u_SiO2
with u_i the average potential energy per oxide formula unit. Element counts are
conserved in this combination, so the MLIP's per-atom reference energies cancel.

NVT at estimated melt densities (a difference quantity, so density error largely
cancels). Reported as a CLUE with its model spread, not a verdict.
"""

import sys
import numpy as np
from ase import Atoms
from ase.md.langevin import Langevin
from ase.md.velocitydistribution import MaxwellBoltzmannDistribution
from ase import units

EV_PER_MOL = 96485.0  # eV -> J/mol

# composition -> (atoms per formula, n_formula_units, density g/cc, n_oxide_units, x_SiO2)
SYSTEMS = {
    "SiO2":    dict(atoms={"Si": 1, "O": 2}, nf=32, rho=2.2, units_per_f=1, x=1.0),
    "MgO":     dict(atoms={"Mg": 1, "O": 1}, nf=48, rho=2.8, units_per_f=1, x=0.0),
    "MgSiO3":  dict(atoms={"Mg": 1, "Si": 1, "O": 3}, nf=20, rho=2.6, units_per_f=2, x=0.5),
    "Mg2SiO4": dict(atoms={"Mg": 2, "Si": 1, "O": 4}, nf=14, rho=2.7, units_per_f=3, x=1.0/3.0),
}
MW = {"Si": 28.085, "O": 15.999, "Mg": 24.305}


def build_liquid_seed(spec, rng):
    """Random placement of the stoichiometric atoms on a jittered simple-cubic grid
    at the target melt density; high-T MD then melts away the lattice memory."""
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
    at = Atoms(symbols, positions=pos, cell=[L, L, L], pbc=True)
    return at, natoms, L


def run(spec, calc, T, melt_ps, eq_ps, samp_ps, dt_fs, seed):
    rng = np.random.default_rng(seed)
    at, natoms, L = build_liquid_seed(spec, rng)
    at.calc = calc
    MaxwellBoltzmannDistribution(at, temperature_K=4200)

    def md(temp, ps):
        dyn = Langevin(at, dt_fs * units.fs, temperature_K=temp, friction=0.02)
        steps = int(ps * 1000 / dt_fs)
        energies = []
        def rec():
            energies.append(at.get_potential_energy())
        dyn.attach(rec, interval=20)
        dyn.run(steps)
        return np.array(energies)

    md(4200.0, melt_ps)          # melt / randomize
    md(T, eq_ps)                 # equilibrate at target T
    e = md(T, samp_ps)           # sample
    u_per_unit = e.mean() / (spec["nf"] * spec["units_per_f"])
    sem = e.std() / np.sqrt(max(len(e), 1)) / (spec["nf"] * spec["units_per_f"])
    return u_per_unit, sem, natoms, L


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "mattersim"
    T = float(sys.argv[2]) if len(sys.argv) > 2 else 3200.0
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
        orbff = pretrained.orb_v2(device="cpu")
        calc = ORBCalculator(orbff, device="cpu")
    else:
        raise SystemExit(f"unknown model {model}")

    print(f"# model={model} T={T}K melt/eq/samp={melt_ps}/{eq_ps}/{samp_ps} ps", flush=True)
    u = {}
    for name, spec in SYSTEMS.items():
        uu, sem, nat, L = run(spec, calc, T, melt_ps, eq_ps, samp_ps, dt_fs, seed)
        u[name] = (uu, sem)
        print(f"  {name:8s} natoms={nat:3d} box={L:5.2f}A  U/oxide-unit={uu:9.4f} +-{sem:.4f} eV",
              flush=True)

    for name in ("MgSiO3", "Mg2SiO4"):
        x = SYSTEMS[name]["x"]
        dU = u[name][0] - (1 - x) * u["MgO"][0] - x * u["SiO2"][0]
        err = np.sqrt(u[name][1]**2 + (1 - x)**2 * u["MgO"][1]**2 + x**2 * u["SiO2"][1]**2)
        print(f"\n  dH_mix(x_SiO2={x:.3f}, {name}) = {dU*EV_PER_MOL/1000:+.1f} "
              f"+- {err*EV_PER_MOL/1000:.1f} kJ/mol-oxide-unit  ({dU:+.4f} eV)", flush=True)


if __name__ == "__main__":
    main()
