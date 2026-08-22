"""MLIP (MatterSim) structure of CaSiO3 melt: Si-O/Ca-O coordination + Qn, to
cross-check the classical Pedone result. Self-contained numpy analysis."""
import numpy as np
from ase import Atoms
from ase.md.langevin import Langevin
from ase.md.velocitydistribution import MaxwellBoltzmannDistribution
from ase import units
from mattersim.forcefield import MatterSimCalculator

def build(nSiO2, nCaO, rho, rng):
    counts={"Si":nSiO2,"O":2*nSiO2+nCaO,"Ca":nCaO}; syms=sum(([s]*n for s,n in counts.items()),[])
    MW={"Si":28.085,"O":15.999,"Ca":40.078}; nat=len(syms)
    mass=sum(MW[s]*n for s,n in counts.items())/6.022e23; L=(mass/rho*1e24)**(1/3)
    m=int(np.ceil(nat**(1/3)))+1; g=[(i,j,k) for i in range(m) for j in range(m) for k in range(m)]
    rng.shuffle(g); a=L/m; pos=(np.array(g[:nat],float)+.5)*a+rng.uniform(-.1*a,.1*a,(nat,3))
    rng.shuffle(syms); return Atoms(syms,positions=pos,cell=[L,L,L],pbc=True)

def mic(a,b,L): d=a[:,None,:]-b[None,:,:]; d-=L*np.round(d/L); return np.sqrt((d**2).sum(-1))

def structure(syms,traj,L,si_o=2.4,ca_o=3.0):
    syms=np.array(syms); Si=np.where(syms=="Si")[0]; O=np.where(syms=="O")[0]; Ca=np.where(syms=="Ca")[0]
    sio,cao,nbo,qn=[],[],[],np.zeros(5)
    for p in traj:
        dSiO=mic(p[Si],p[O],L); dCaO=mic(p[Ca],p[O],L)
        sio.append((dSiO<si_o).sum(1).mean()); cao.append((dCaO<ca_o).sum(1).mean())
        bond=dSiO<si_o; siO=bond.sum(0); brg=siO>=2
        for q in (bond&brg[None,:]).sum(1): qn[min(q,4)]+=1
        nbo.append((siO==1).sum()/len(O))
    qn/=qn.sum(); return np.mean(sio),np.mean(cao),np.mean(nbo),qn

rng=np.random.default_rng(1); at=build(16,16,2.6,rng); L=at.cell[0,0]
at.calc=MatterSimCalculator(); MaxwellBoltzmannDistribution(at,temperature_K=4000)
def md(T,ps,rec=None):
    dyn=Langevin(at,2*units.fs,temperature_K=T,friction=0.02)
    if rec is not None: dyn.attach(lambda:rec.append(at.get_positions()),interval=100)
    dyn.run(int(ps*500))
md(4000,2); md(2000,3); traj=[]; md(2000,4,traj)
sio,cao,nbo,qn=structure(at.get_chemical_symbols(),np.array(traj),L)
print(f"MLIP x=0.5 @2000K: Si-O CN={sio:.2f} Ca-O CN={cao:.2f} NBO/O={nbo:.2f}")
print(f"  Qn(Q0..Q4)={np.round(qn,2)}")
