"""Independent MLIP estimate of the CaO-SiO2 liquid enthalpy of mixing.

Arbitrates the shallow (Stolyarova activities, ~ -30 kJ/mol-oxide) vs deep
(silicate calorimetry + melting, ~ -45 to -57 kJ/mol-oxide) disagreement at the
CaSiO3 composition, with a foundation MLIP as an independent third number.

Method: melt-quench-sample MD of three liquids at a common temperature where all
three are molten (CaO melts ~2845 K, so we sample at 3000 K):
  pure SiO2, pure CaO, and CaSiO3 (x_SiO2 = 0.5).
Enthalpy of mixing per mole of OXIDE FORMULA UNIT (at ~1 bar, PV negligible):
  dU_mix = u_CaSiO3 - 0.5*u_SiO2 - 0.5*u_CaO
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

# composition -> (elements per formula, n_formula_units, density g/cc, n_oxide_units)
SYSTEMS = {
    "SiO2":    dict(atoms={"Si": 1, "O": 2}, nf=32, rho=2.2, units_per_f=1),
    "CaO":     dict(atoms={"Ca": 1, "O": 1}, nf=48, rho=2.8, units_per_f=1),
    "CaSiO3":  dict(atoms={"Ca": 1, "Si": 1, "O": 3}, nf=20, rho=2.6, units_per_f=2),
}
MW = {"Si": 28.085, "O": 15.999, "Ca": 40.078}


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
    # simple-cubic grid with enough sites, take natoms of them, jitter
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
    MaxwellBoltzmannDistribution(at, temperature_K=4000)

    def md(temp, ps):
        dyn = Langevin(at, dt_fs * units.fs, temperature_K=temp, friction=0.02)
        steps = int(ps * 1000 / dt_fs)
        energies = []
        def rec():
            energies.append(at.get_potential_energy())
        dyn.attach(rec, interval=20)
        dyn.run(steps)
        return np.array(energies)

    md(4000.0, melt_ps)          # melt / randomize
    md(T, eq_ps)                 # equilibrate at target T
    e = md(T, samp_ps)           # sample
    u_per_unit = e.mean() / (spec["nf"] * spec["units_per_f"])
    sem = e.std() / np.sqrt(max(len(e), 1)) / (spec["nf"] * spec["units_per_f"])
    return u_per_unit, sem, natoms, L


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "mattersim"
    T = float(sys.argv[2]) if len(sys.argv) > 2 else 3000.0
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
    elif model.startswith("mace"):
        from mace.calculators import mace_mp
        tag = {"mace": "medium", "mace-mpa": "medium-mpa-0",
               "mace-omat": "medium-omat-0"}.get(model, "medium")
        calc = mace_mp(model=tag, dispersion=False, default_dtype="float32", device="cpu")
    else:
        raise SystemExit(f"unknown model {model}")

    print(f"# model={model} T={T}K melt/eq/samp={melt_ps}/{eq_ps}/{samp_ps} ps")
    u = {}
    for name, spec in SYSTEMS.items():
        uu, sem, nat, L = run(spec, calc, T, melt_ps, eq_ps, samp_ps, dt_fs, seed)
        u[name] = (uu, sem)
        print(f"  {name:8s} natoms={nat:3d} box={L:5.2f}A  U/oxide-unit={uu:9.4f} +-{sem:.4f} eV")

    dU = u["CaSiO3"][0] - 0.5 * u["SiO2"][0] - 0.5 * u["CaO"][0]
    err = np.sqrt(u["CaSiO3"][1]**2 + 0.25*u["SiO2"][1]**2 + 0.25*u["CaO"][1]**2)
    print(f"\n  dH_mix(x=0.5) = {dU*EV_PER_MOL/1000:+.1f} +- {err*EV_PER_MOL/1000:.1f} "
          f"kJ/mol-oxide-unit  ({dU:+.4f} eV)")
    print("  compare: activities imply ~ -30 ; calorimetry+melting imply ~ -45 to -57")


if __name__ == "__main__":
    main()
