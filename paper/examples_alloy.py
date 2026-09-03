"""Paper worked example (alloy TDB): the Al-Zn phase diagram from the shipped open TDB.
The manuscript listing is the code between BEGIN/END; the figure code follows it."""
import sys; sys.path.insert(0, "python")
import numpy as np

# --- BEGIN paper listing -------------------------------------------------
from mqmqa import Database

db = Database.read("web/AlZn.tdb")            # Thermo-Calc dialect, same reader
phases = [(db.phase_index(n), n) for n in db.phase_names]

def lower_hull(pts):                               # 2-D lower convex hull of (x, G)
    pts = sorted(pts); hull = []
    for p in pts:
        while len(hull) >= 2 and (hull[-1][0]-hull[-2][0])*(p[1]-hull[-2][1]) \
                <= (hull[-1][1]-hull[-2][1])*(p[0]-hull[-2][0]):
            hull.pop()
        hull.append(p)
    return hull

diagram = []
for T in np.arange(300.0, 1001.0, 5.0):
    pts = []
    for p, name in phases:                      # every CEF phase along the join
        for y in np.linspace(1e-4, 1-1e-4, 60):    # y = site fraction of Zn
            g = db.cef_gibbs(p, [1.0-y, y], T, per_mole_atoms=True)
            pts.append((y, g, name))
    hull = lower_hull(pts)                     # 2-D lower convex hull of (x, G)
    for edge_a, edge_b in zip(hull, hull[1:]):
        xa, _ga, name_a = edge_a
        xb, _gb, name_b = edge_b
        diagram.append((0.5*(xa+xb), T, tuple(sorted({name_a, name_b}))))

liq = [(T, x) for x, T, ph in diagram if ph == ("LIQUID",)]
Te, xe = min(liq)                                  # coldest all-liquid point = eutectic
print(f"eutectic near x_Zn = {xe:.3f}, T = {Te:.0f} K   (assessed: 0.885, 654 K)")
# --- END paper listing ---------------------------------------------------

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# rasterize hull states onto a grid for the greyscale field plot
xis = np.linspace(0.0125, 0.9875, 40)
Ts = np.arange(300.0, 1001.0, 5.0)
grid = np.full((len(Ts), len(xis)), np.nan)
cat = {("LIQUID",): 0.0}
def catval(ph):
    if ph == ("LIQUID",): return 0.0
    if "LIQUID" in ph: return 1.0
    return 2.0
# nearest-edge assignment per (T, xi): use the recorded edges per T
from collections import defaultdict
byT = defaultdict(list)
for x, T, ph in diagram: byT[T].append((x, ph))
# rebuild per T from hull edges directly for exact interval painting
for ti, T in enumerate(Ts):
    pts = []
    for p, name in phases:
        for y in np.linspace(1e-4, 1-1e-4, 60):
            pts.append((y, db.cef_gibbs(p, [1.0-y, y], float(T), per_mole_atoms=True), name))
    hull = lower_hull(pts)
    for k in range(len(hull)-1):
        a, b = hull[k], hull[k+1]
        v = catval(tuple(sorted({a[2], b[2]})))
        sel = (xis >= a[0]-1e-9) & (xis <= b[0]+1e-9)
        grid[ti, sel] = v
fig, ax = plt.subplots(figsize=(4.6, 3.4), dpi=300)
ax.imshow(grid, origin="lower", aspect="auto", cmap="Greys", vmin=-0.6, vmax=2.6,
          extent=[xis[0], xis[-1], Ts[0], Ts[-1]], interpolation="nearest")
ax.plot(0.885, 654.0, marker="*", ms=12, mfc="white", mec="black", mew=0.9, ls="none")
ax.plot(xe, Te, marker="o", ms=5, mfc="black", mec="black", ls="none")
ax.set_xlabel(r"$x_\mathrm{Zn}$"); ax.set_ylabel("T (K)")
for sp in ("top", "right"): ax.spines[sp].set_visible(False)
fig.tight_layout(); fig.savefig("paper/figures/fig5_alloy_example.png")
print("phase sets seen:", sorted({str(ph) for _, _, ph in diagram})[:8])
