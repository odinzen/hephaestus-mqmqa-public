"""Parse QE vc-relax total energies and compute the olivine Fe-Mg mixing enthalpy,
compared to Wood & Kleppa 1981. Cell = Mg8Si4O16 = 4 formula units (Mg,Fe)2SiO4."""
import re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
RY_JMOL = 13.605693 * 96485.33      # 1 Ry -> J/mol
NF = 4                              # formula units in the 28-atom cell
WK = lambda x: x*(1-x)*(12552.0 + 4184.0*(2*x-1))

def final_energy(run):
    out = (HERE/"runs"/run/"pw.out").read_text(errors="ignore")
    es = re.findall(r"^!\s+total energy\s+=\s+(-?\d+\.\d+)\s+Ry", out, re.M)
    done = "JOB DONE" in out
    return (float(es[-1]) if es else None), done, len(es)

def moment(run):
    out = (HERE/"runs"/run/"pw.out").read_text(errors="ignore")
    m = re.findall(r"total magnetization\s+=\s+(-?\d+\.\d+)", out)
    return float(m[-1]) if m else None

E = {}
for r in ("fo", "fa", "x50_a"):
    e, done, n = final_energy(r)
    E[r] = e
    print(f"{r:7s} E={e} Ry  done={done}  scf_pts={n}  mag={moment(r)}")

if all(E[r] is not None for r in E):
    hmix = (E["x50_a"] - 0.5*E["fa"] - 0.5*E["fo"]) * RY_JMOL / NF
    print(f"\nDFT H_mix(x=0.5) = {hmix:8.0f} J/mol formula")
    print(f"Wood-Kleppa      = {WK(0.5):8.0f} J/mol formula")
    print(f"diff             = {hmix-WK(0.5):+8.0f} J/mol")
    print(f"\nFor reference, MLIP H_mix(0.5): SevenNet +3168, ORB +2092, MatterSim +71, CHGNet -2888")
else:
    print("\n(incomplete - some runs not finished)")
