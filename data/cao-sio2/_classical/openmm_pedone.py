"""Classical MD of CaO-SiO2 melts with the Pedone et al. 2006 rigid-ion potential,
in OpenMM. Independent cross-check of the MLIP structure + demixing.

Pedone form (per pair): Coulomb(partial charges) + Morse + C/r^12
  U = qi qj/(4 pi e0 r) + D[(1-exp(-a(r-r0)))^2 - 1] + C/r^12
Partial charges: O -1.2, Si +2.4, Ca +1.2. Morse/C only on O-cation and O-O pairs;
cation-cation is Coulomb only. Params below are the standard Pedone 2006 set (eV, A)
- flagged for verification against the paper; used here for a qualitative cross-check.
"""
import sys
import numpy as np
import openmm as mm
from openmm import unit, System, Platform, LangevinMiddleIntegrator
from openmm.app import Topology, Element, Simulation, PDBFile

EV = 96.485  # eV -> kJ/mol
CHARGE = {"Ca": 1.2, "Si": 2.4, "O": -1.2}
MASS = {"Ca": 40.078, "Si": 28.085, "O": 15.999}
TYPE = {"Ca": 0, "Si": 1, "O": 2}
# pair -> (D eV, a A^-1, r0 A, C eV A^12); symmetric, O-involving only
PED = {(2, 2): (0.042395, 1.379316, 3.618701, 22.0),   # O-O
       (1, 2): (0.340554, 2.006700, 2.100000, 1.0),    # Si-O
       (0, 2): (0.030211, 2.241334, 2.923245, 5.0)}    # Ca-O

def _tables():
    D = np.zeros((3, 3)); A = np.ones((3, 3)); R0 = np.zeros((3, 3)); C = np.zeros((3, 3))
    for (i, j), (d, a, r0, c) in PED.items():
        for (x, y) in ((i, j), (j, i)):
            D[x, y] = d * EV; A[x, y] = a * 10.0; R0[x, y] = r0 * 0.1
            C[x, y] = c * EV * 1e-12
    return D, A, R0, C

def build_system(symbols, cutoff):
    sysm = System()
    for s in symbols:
        sysm.addParticle(MASS[s] * unit.amu)
    nb = mm.NonbondedForce(); nb.setNonbondedMethod(mm.NonbondedForce.PME)
    nb.setCutoffDistance(cutoff * unit.nanometer)
    for s in symbols:
        nb.addParticle(CHARGE[s] * unit.elementary_charge, 0.0, 0.0)
    sysm.addForce(nb)
    D, A, R0, C = _tables()
    flat = lambda M: [float(v) for v in M.flatten()]
    cnb = mm.CustomNonbondedForce(
        "D*((1-exp(-a*(r-r0)))^2 - 1) + Cc/r^12;"
        "D=Dt(t1,t2); a=at(t1,t2); r0=r0t(t1,t2); Cc=Ct(t1,t2)")
    cnb.addPerParticleParameter("t")
    cnb.addTabulatedFunction("Dt", mm.Discrete2DFunction(3, 3, flat(D)))
    cnb.addTabulatedFunction("at", mm.Discrete2DFunction(3, 3, flat(A)))
    cnb.addTabulatedFunction("r0t", mm.Discrete2DFunction(3, 3, flat(R0)))
    cnb.addTabulatedFunction("Ct", mm.Discrete2DFunction(3, 3, flat(C)))
    cnb.setNonbondedMethod(mm.CustomNonbondedForce.CutoffPeriodic)
    cnb.setCutoffDistance(cutoff * unit.nanometer)
    for s in symbols:
        cnb.addParticle([float(TYPE[s])])
    sysm.addForce(cnb)
    return sysm

def melt_cell(nSiO2, nCaO, rho, rng):
    counts = {"Si": nSiO2, "O": 2 * nSiO2 + nCaO, "Ca": nCaO}
    syms = sum(([s] * n for s, n in counts.items()), [])
    nat = len(syms)
    mass = sum(MASS[s] * n for s, n in counts.items()) / 6.02214076e23
    L = (mass / rho * 1e21) ** (1 / 3)  # nm (rho g/cc -> nm^3)
    m = int(np.ceil(nat ** (1 / 3))) + 1
    grid = [(i, j, k) for i in range(m) for j in range(m) for k in range(m)]
    rng.shuffle(grid); a = L / m
    pos = (np.array(grid[:nat], float) + 0.5) * a + rng.uniform(-0.1*a, 0.1*a, (nat, 3))
    rng.shuffle(syms)
    return syms, pos, L

def make_sim(symbols, L, T, platform="OpenCL"):
    cutoff = min(0.75, 0.45 * L)
    sysm = build_system(symbols, cutoff)
    box = np.eye(3) * L
    sysm.setDefaultPeriodicBoxVectors(*(box * unit.nanometer))
    integ = LangevinMiddleIntegrator(T * unit.kelvin, 1.0/unit.picosecond, 2.0*unit.femtosecond)
    top = Topology()
    ch = top.addChain(); res = top.addResidue("MLT", ch)
    for s in symbols:
        top.addAtom(s, Element.getBySymbol(s), res)
    top.setPeriodicBoxVectors(box * unit.nanometer)
    try:
        plat = Platform.getPlatformByName(platform)
    except Exception:
        plat = Platform.getPlatformByName("CPU")
    sim = Simulation(top, sysm, integ, plat)
    return sim

if __name__ == "__main__":
    rng = np.random.default_rng(1)
    syms, pos, L = melt_cell(64, 64, 2.6, rng)  # CaSiO3 x=0.5, ~320 atoms
    sim = make_sim(syms, L, 3000.0)
    sim.context.setPositions(pos * unit.nanometer)  # melt_cell returns nm
    print("platform:", sim.context.getPlatform().getName(), "natoms:", len(syms))
    e0 = sim.context.getState(getEnergy=True).getPotentialEnergy()
    print("initial PE/atom:", e0/len(syms))
    sim.minimizeEnergy(maxIterations=2000)
    em = sim.context.getState(getEnergy=True).getPotentialEnergy()
    print("PE/atom after minimize:", em/len(syms))
    sim.context.setVelocitiesToTemperature(4000 * unit.kelvin)
    sim.step(1000)   # 2 ps melt at 4000K
    integ = sim.integrator; integ.setTemperature(3000*unit.kelvin)
    sim.step(1500)   # 3 ps equilibrate at 3000K
    e1 = sim.context.getState(getEnergy=True).getPotentialEnergy()
    print("PE/atom after melt+eq:", e1/len(syms), "kJ/mol/atom")
