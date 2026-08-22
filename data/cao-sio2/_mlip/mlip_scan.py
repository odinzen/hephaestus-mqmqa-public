"""MLIP scan of CaO-SiO2 liquid enthalpy of mixing across composition.

Maps dH_mix(x_SiO2) to separate two effects behind the phase-diagram error:
  - WHERE the ordering peaks (central shape) -> constrains the excess shape
    independent of the solid data;
  - whether dH_mix FLATTENS toward the silica-rich end -> a positive-deviation /
    demixing tendency (the real CaO-SiO2 liquid-liquid gap) that our cation-mixing
    excess cannot produce.

dH_mix(x) = u_mix(x) - x*u_SiO2 - (1-x)*u_CaO   (per mole oxide formula unit, eV),
element counts conserved so the MLIP per-atom references cancel. NVT at estimated
melt densities, common T = 3000 K (all liquid). A shape probe, not absolute values.
"""

import sys
import numpy as np
from ase import Atoms
from ase.md.langevin import Langevin
from ase.md.velocitydistribution import MaxwellBoltzmannDistribution
from ase import units

EV_PER_MOL = 96485.0
MW = {"Si": 28.085, "O": 15.999, "Ca": 40.078}

# (n_SiO2, n_CaO) formula units per cell; x_SiO2 = nSiO2/(nSiO2+nCaO)
CELLS = {
    "CaO":  (0, 45),
    "x020": (8, 32),
    "x033": (12, 24),
    "x050": (16, 16),
    "x060": (18, 12),
    "x070": (21, 9),
    "SiO2": (30, 0),
}


def rho_est(x):
    return 2.2 * x + 2.9 * (1.0 - x)   # rough linear melt density (g/cc)


def build(nsio2, ncao, rng):
    counts = {"Si": nsio2, "O": 2 * nsio2 + ncao, "Ca": ncao}
    syms = []
    for el, n in counts.items():
        syms += [el] * n
    nat = len(syms)
    x = nsio2 / (nsio2 + ncao) if (nsio2 + ncao) else 1.0
    mass = sum(MW[e] * n for e, n in counts.items()) / 6.02214076e23
    vol = mass / rho_est(x) * 1e24
    L = vol ** (1 / 3)
    m = int(np.ceil(nat ** (1 / 3))) + 1
    grid = [(i, j, k) for i in range(m) for j in range(m) for k in range(m)]
    rng.shuffle(grid)
    a = L / m
    pos = (np.array(grid[:nat], float) + 0.5) * a + rng.uniform(-0.15*a, 0.15*a, (nat, 3))
    rng.shuffle(syms)
    return Atoms(syms, positions=pos, cell=[L, L, L], pbc=True), nat, L


def sample(at, calc, T, melt, eq, samp, dt):
    at.calc = calc
    MaxwellBoltzmannDistribution(at, temperature_K=4000)

    def md(temp, ps, rec=None):
        dyn = Langevin(at, dt * units.fs, temperature_K=temp, friction=0.02)
        if rec is not None:
            dyn.attach(lambda: rec.append(at.get_potential_energy()), interval=20)
        dyn.run(int(ps * 1000 / dt))
    md(4000.0, melt); md(T, eq)
    e = []; md(T, samp, e)
    return np.mean(e), np.std(e) / np.sqrt(max(len(e), 1))


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "mattersim"
    T, dt = 3000.0, 2.0
    melt, eq, samp = 1.0, 1.5, 3.0
    if model == "mattersim":
        from mattersim.forcefield import MatterSimCalculator
        calc = MatterSimCalculator()
    elif model == "orb":
        from orb_models.forcefield import pretrained
        from orb_models.forcefield.calculator import ORBCalculator
        calc = ORBCalculator(pretrained.orb_v2(device="cpu"), device="cpu")
    else:
        raise SystemExit("unknown model")

    print(f"# model={model} T={T}K  melt/eq/samp={melt}/{eq}/{samp} ps")
    u = {}
    for name, (ns, nc) in CELLS.items():
        rng = np.random.default_rng(1234)
        at, nat, L = build(ns, nc, rng)
        um, sem = sample(at, calc, T, melt, eq, samp, dt)
        nunits = ns + nc
        u[name] = (um / nunits, sem / nunits, ns / nunits if nunits else 1.0)
        print(f"  {name:5s} x={u[name][2]:.3f} nat={nat:3d} L={L:5.2f} "
              f"u/unit={u[name][0]:8.4f} eV")

    uS, uC = u["SiO2"][0], u["CaO"][0]
    print("\n  x_SiO2   dH_mix (kJ/mol-oxide-unit)")
    for name, (uu, sem, x) in u.items():
        if name in ("SiO2", "CaO"):
            continue
        dH = (uu - x * uS - (1 - x) * uC) * EV_PER_MOL / 1000
        print(f"   {x:.3f}    {dH:+7.1f}")
    print("\n  shape: a minimum near x~0.33 (orthosilicate) = central ordering peak;")
    print("  flattening/rising toward x~0.7 = silica-rich demixing tendency.")


if __name__ == "__main__":
    main()
