"""Classical (Pedone/OpenMM) structure + demixing of CaO-SiO2 melts.
Structure: Si-O and Ca-O coordination, Qn speciation (network polymerization).
Demixing: Ca-Ca enrichment at silica-rich composition (clustering -> phase separation).
"""
import sys, numpy as np
from openmm import unit
from openmm_pedone import melt_cell, make_sim

def run(nSiO2, nCaO, rho, T, frames, melt_ps=3.0, eq_ps=5.0, gap_ps=0.4):
    rng = np.random.default_rng(1)
    syms, pos, L = melt_cell(nSiO2, nCaO, rho, rng)
    sim = make_sim(syms, L, T)
    sim.context.setPositions(pos * unit.nanometer)
    sim.minimizeEnergy(maxIterations=2000)
    sim.context.setVelocitiesToTemperature(4000 * unit.kelvin)
    sim.step(int(melt_ps * 500))
    sim.integrator.setTemperature(T * unit.kelvin)
    sim.step(int(eq_ps * 500))
    traj = []
    for _ in range(frames):
        sim.step(int(gap_ps * 500))
        p = np.array(sim.context.getState(getPositions=True).getPositions()
                     .value_in_unit(unit.nanometer)) * 10.0
        traj.append(p)
    return np.array(syms), np.array(traj), L * 10.0

def mic_dists(a, b, L):  # all pairwise min-image distances between sets a,b (Nx3)
    d = a[:, None, :] - b[None, :, :]
    d -= L * np.round(d / L)
    return np.sqrt((d**2).sum(-1))

def structure(syms, traj, L, si_o=2.4, ca_o=3.0):
    Si = np.where(syms == "Si")[0]; O = np.where(syms == "O")[0]; Ca = np.where(syms == "Ca")[0]
    sio, cao, qn_hist, nbo = [], [], np.zeros(5), []
    for p in traj:
        dSiO = mic_dists(p[Si], p[O], L)      # (nSi, nO)
        dCaO = mic_dists(p[Ca], p[O], L)
        sio.append((dSiO < si_o).sum(1).mean())
        cao.append((dCaO < ca_o).sum(1).mean())
        bond = dSiO < si_o                      # Si-O bonds
        si_per_O = bond.sum(0)                   # # Si bonded to each O
        bridging = si_per_O >= 2                 # bridging O
        qn = (bond & bridging[None, :]).sum(1)   # # bridging O per Si = Qn
        for q in qn:
            qn_hist[min(q, 4)] += 1
        nbo.append((si_per_O == 1).sum() / len(O))
    qn_hist /= qn_hist.sum()
    return np.mean(sio), np.mean(cao), np.mean(nbo), qn_hist

def demix(syms, traj, L, r=6.0):
    """Ca-Ca enrichment: mean #Ca within r of a Ca / expected if random."""
    Ca = np.where(syms == "Ca")[0]; nCa = len(Ca); n = len(syms)
    shell_expect = (nCa - 1) * (4/3*np.pi*r**3) / (L**3)  # random expectation in shell
    enr = []
    for p in traj:
        d = mic_dists(p[Ca], p[Ca], L)
        np.fill_diagonal(d, 1e9)
        obs = (d < r).sum(1).mean()
        enr.append(obs / shell_expect)
    return np.mean(enr), np.std(enr)

if __name__ == "__main__":
    print("=== CLASSICAL (Pedone/OpenMM) structure at x_SiO2=0.5 (CaSiO3) ===")
    syms, traj, L = run(64, 64, 2.6, 2000.0, frames=20)
    sio, cao, nbo, qn = structure(syms, traj, L)
    print(f"  Si-O CN={sio:.2f}  Ca-O CN={cao:.2f}  NBO/O={nbo:.2f}")
    print(f"  Qn (Q0..Q4) = {np.round(qn,2)}   (Q2 dominant = chain silicate expected at CS)")
    print("\n=== CLASSICAL demixing probe at x_SiO2=0.7 (silica-rich) ===")
    syms2, traj2, L2 = run(84, 36, 2.4, 3000.0, frames=25, eq_ps=8.0)
    enr, sd = demix(syms2, traj2, L2)
    print(f"  Ca-Ca enrichment (obs/random within 6A) = {enr:.2f} +- {sd:.2f}")
    print("  >1 = Ca clustering (demixing tendency); ~1 = well mixed")
