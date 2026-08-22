"""Classical demixing test: silica-rich CaO-SiO2 melt BELOW the consolute (~1970 K).
Start mixed at 1800 K, watch Ca-Ca clustering grow with time. Rising enrichment =
liquid-liquid phase separation (the miscibility gap); flat ~1 = Pedone lacks the gap.
"""
import numpy as np
from openmm import unit
from openmm_pedone import melt_cell, make_sim
from openmm_analyze import mic_dists

def demix_enrich(p, Ca, L, r=6.0):
    d = mic_dists(p[Ca], p[Ca], L); np.fill_diagonal(d, 1e9)
    exp = (len(Ca)-1)*(4/3*np.pi*r**3)/(L**3)
    return (d < r).sum(1).mean()/exp

rng = np.random.default_rng(3)
# x_SiO2 = 0.8, ~560 atoms, silica-rich (deep in the gap)
syms, pos, L = melt_cell(160, 40, 2.35, rng)
Ca = np.where(np.array(syms)=="Ca")[0]
sim = make_sim(syms, L, 1800.0)
sim.context.setPositions(pos*unit.nanometer)
sim.minimizeEnergy(maxIterations=3000)
sim.context.setVelocitiesToTemperature(3500*unit.kelvin); sim.step(2000)  # 4ps randomize hot
sim.integrator.setTemperature(1800*unit.kelvin)
print(f"# x_SiO2=0.8, {len(syms)} atoms, L={L*10:.1f} A, T=1800K (consolute ~1970K)")
print("# t_ps   Ca-Ca_enrichment (>1 = clustering/demixing)")
for i in range(30):
    sim.step(2500)  # 5 ps
    p = np.array(sim.context.getState(getPositions=True).getPositions().value_in_unit(unit.nanometer))*10
    print(f"  {5*(i+1):4d}   {demix_enrich(p, Ca, L*10):.3f}", flush=True)
