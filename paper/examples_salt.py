"""Paper worked example (salt): the LiCl-KCl phase diagram from the shipped open database.
The listing in the manuscript is the code between BEGIN/END; the figure code follows it."""
import sys; sys.path.insert(0, "python")
import numpy as np

# --- BEGIN paper listing -------------------------------------------------
from mqmqa import Database
from mqmqa.equilibrium import build_inputs, multiphase_binary

db  = Database.read("web/LiCl-KCl.dat")            # the file the browser app ships
liq = db.phase_index("LICL-KCL-LIQUID")
LiCl, KCl = {"LI": 1, "CL": 1}, {"K": 1, "CL": 1}  # endmember element compositions

diagram = []
for T in np.arange(500.0, 1101.0, 10.0):
    inp    = build_inputs(db, liq, T)              # liquid model at this temperature
    solids = [(0.0, db.stoich_gibbs(0, T), "LiCl(s)"),
              (1.0, db.stoich_gibbs(1, T), "KCl(s)")]
    for xi in np.arange(0.025, 1.0, 0.025):        # xi = mole fraction KCl
        state = multiphase_binary(inp, LiCl, KCl, solids, xi, ngrid=80)
        diagram.append((xi, T, "+".join(sorted(state["phases"]))))

liquid_only = [(T, xi) for xi, T, ph in diagram if ph == "LIQUID"]
Te, xe = min(liquid_only)                          # coldest all-liquid point = eutectic
print(f"eutectic near x_KCl = {xe:.3f}, T = {Te:.0f} K   (measured: 0.415, 626 K)")
# --- END paper listing ---------------------------------------------------

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np2

# category grid -> greyscale field plot (0 liquid, 1 two-phase, 2 subsolidus)
xis = sorted({d[0] for d in diagram}); Ts = sorted({d[1] for d in diagram})
xi_i = {v:k for k,v in enumerate(xis)}; T_i = {v:k for k,v in enumerate(Ts)}
grid = np.zeros((len(Ts), len(xis)))
cat = lambda ph: 0.0 if ph=="LIQUID" else (2.0 if ph=="KCl(s)+LiCl(s)" else 1.0)
for xi,T,ph in diagram: grid[T_i[T], xi_i[xi]] = cat(ph)
fig, ax = plt.subplots(figsize=(4.6,3.4), dpi=300)
ax.imshow(grid, origin="lower", aspect="auto", cmap="Greys", vmin=-0.6, vmax=2.6,
          extent=[min(xis), max(xis), min(Ts), max(Ts)], interpolation="nearest")
ax.plot(0.415, 626.0, marker="*", ms=12, mfc="white", mec="black", mew=0.9, ls="none")
ax.plot(xe, Te, marker="o", ms=5, mfc="black", mec="black", ls="none")
ax.set_xlabel(r"$x_\mathrm{KCl}$"); ax.set_ylabel("T (K)")
for sp in ("top","right"): ax.spines[sp].set_visible(False)
fig.tight_layout(); fig.savefig("paper/figures/fig4_salt_example.png")
print("phase sets seen:", sorted({ph for _,_,ph in diagram}))
