"""Uncertainty-weighted Redlich-Kister fit to the MLIP di-hed H_mix, and a figure.

RK convention matching the CEF file: G_xs = y_Fe*y_Mg*[L0 + L1*(y_Fe - y_Mg)], per mole
of formula (one mixing cation). y_Fe = x here. A sigma floor of 50 J/mol represents the
MLIP's own systematic uncertainty so the symmetry-locked endpoints do not get infinite
weight. Prints L0, L1 for build_dat.py.
"""
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
d = json.loads((HERE / "mlip_mix2_result.json").read_text())
rows = d["rows"]

x = np.array([r["x"] for r in rows])
hm = np.array([r["Hmix_Jmol"] for r in rows])
sig = np.array([max(50.0, r["Hmix_sig"]) for r in rows])
interior = (x > 0) & (x < 1)
xi, hi, si = x[interior], hm[interior], sig[interior]

# G_xs = x(1-x)[L0 + L1(2x-1)]  (2x-1 = y_Fe - y_Mg)
A = np.column_stack([xi * (1 - xi), xi * (1 - xi) * (2 * xi - 1)])
W = np.diag(1.0 / si ** 2)
cov = np.linalg.inv(A.T @ W @ A)
L = cov @ A.T @ W @ hi
L0, L1 = L
dL0, dL1 = np.sqrt(np.diag(cov))
print(f"weighted RK fit:  L0 = {L0:.1f} +/- {dL0:.1f}   L1 = {L1:.1f} +/- {dL1:.1f} J/mol")
print(f"H_mix(0.5) fit = {0.25*L0:.1f} J/mol (MLIP {hm[x==0.5][0]:.1f})")

xf = np.linspace(0, 1, 200)
fit = xf * (1 - xf) * (L0 + L1 * (2 * xf - 1))
fig, ax = plt.subplots(figsize=(5.6, 4.2))
ax.axhline(0, color="#999", lw=0.8)
ax.errorbar(x, hm, yerr=sig, fmt="o", color="#1a1a1a", ms=5, capsize=3, label="MatterSim")
ax.plot(xf, fit, color="#b00000", lw=1.8, label=f"RK: L0={L0:.0f}, L1={L1:.0f} J/mol")
ax.set_xlabel("x(hedenbergite) = Fe / (Fe+Mg) on M1")
ax.set_ylabel("Enthalpy of mixing (J/mol formula)")
ax.set_title("Diopside-Hedenbergite Mixing (MLIP Triangulation)", fontsize=11)
ax.legend(fontsize=9, loc="lower right"); ax.grid(alpha=0.15)
fig.tight_layout()
fig.savefig(HERE / "dihed_hmix.png", dpi=160)
print("wrote", HERE / "dihed_hmix.png")
print(f"\nfor build_dat.py:  L0 = {L0:.1f}   L1 = {L1:.1f}")
