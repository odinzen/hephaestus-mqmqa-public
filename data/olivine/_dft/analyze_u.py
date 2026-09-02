"""PBE+U olivine mixing enthalpy vs Wood-Kleppa, configurational average over x=0.5 orderings.

Forsterite (no Fe) reused from the PBE run; fayalite from runs_u/fa. H_mix averaged over the
five Fe4Mg4 orderings (x50_a original + ord2..ord5) to strip single-ordering ordering energy.
"""
import re
from pathlib import Path
HERE = Path(__file__).resolve().parent
RY_JMOL = 13.605693 * 96485.33
NF = 4
E_FO = -1988.20969169   # forsterite PBE (no Fe -> +U identical), reused
ORDERINGS = ["x50_a", "ord2", "ord3", "ord4", "ord5"]


def E(run, sub="runs_u"):
    f = HERE / sub / run / "pw.out"
    if not f.exists():
        return None, False, "?"
    out = f.read_text(errors="ignore")
    es = re.findall(r"^!\s+total energy\s+=\s+(-?\d+\.\d+)\s+Ry", out, re.M)
    m = re.findall(r"total magnetization\s+=\s+(-?\d+\.\d+)", out)
    return (float(es[-1]) if es else None), ("JOB DONE" in out), (m[-1] if m else "?")


def hmix(ex, efa):
    return (ex - 0.5 * efa - 0.5 * E_FO) * RY_JMOL / NF


efa, dfa, mfa = E("fa")
print(f"fo (PBE reused) E={E_FO}")
print(f"fa+U   E={efa} done={dfa} mag={mfa}\n")

if not efa:
    print("fayalite endmember missing; cannot compute H_mix.")
    raise SystemExit

hs = []
for name in ORDERINGS:
    ex, dx, mx = E(name)
    if ex is None:
        started = (HERE / "runs_u" / name / "pw.out").exists()
        print(f"  {name:6s}  ({'running, no energy line yet' if started else 'not started'})")
        continue
    h = hmix(ex, efa)
    flag = "" if dx else "  [NOT converged - preliminary]"
    print(f"  {name:6s}  E={ex:.6f}  mag={mx:>6}  H_mix={h:8.0f} J/mol{flag}")
    if dx:
        hs.append(h)

print()
if hs:
    avg = sum(hs) / len(hs)
    print(f"Converged orderings: {len(hs)}/{len(ORDERINGS)}")
    print(f"DFT+U <H_mix(0.5)> = {avg:8.0f} J/mol   (PBE was -4742,  Wood-Kleppa +3138)")
    print(f"  spread: min {min(hs):.0f}  max {max(hs):.0f}")
else:
    print("No converged orderings yet.")
print("MLIP ref: SevenNet +3168, ORB +2092")
