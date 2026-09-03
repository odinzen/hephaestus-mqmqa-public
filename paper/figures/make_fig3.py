"""Regenerate fig3_ternary.png: (a) liquidus projection, (b) 1600 degC isothermal section.

Readability rules: large in-field labels with white halos (dark fills cannot eat them),
contour labels at 9 pt with halos, greyscale house fills, no baked caption.
Panel (a) reads the cached projection (data/feo-mgo-sio2/_liquidus_projection.npz);
panel (b) recomputes the section through the same assemblage machinery the web export uses.
"""
import importlib.util
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import matplotlib.tri as mtri
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "python"))
DATA = ROOT / "data" / "feo-mgo-sio2"

plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"]})

ABBR = {"LIQUID": "L", "OLIVINE": "Ol", "ORTHOPYROXENE": "Opx", "PERICLASE": "Per",
        "WUSTITE": "Wus", "CRISTOBALITE": "Crs"}
HALO = [pe.withStroke(linewidth=2.8, foreground="white")]
S3 = np.sqrt(3) / 2


def tri_xy(x_fe, x_si):
    """MgO left (0,0), FeO right (1,0), SiO2 top."""
    return x_fe + 0.5 * x_si, S3 * x_si


def frame(ax):
    ax.plot([0, 1, 0.5, 0], [0, 0, S3, 0], color="black", linewidth=1.2)
    ax.text(-0.02, -0.045, "MgO", ha="right", fontsize=12)
    ax.text(1.02, -0.045, "FeO", ha="left", fontsize=12)
    ax.text(0.5, S3 + 0.035, "SiO$_2$", ha="center", fontsize=12)
    ax.set_xlim(-0.14, 1.14)
    ax.set_ylim(-0.10, S3 + 0.10)
    ax.set_aspect("equal")
    ax.axis("off")


def label_regions(ax, X, Y, names, min_pts=25, size=12, skip=()):
    for nm in sorted(set(names)):
        if not nm or nm in skip:
            continue
        m = np.array([n == nm for n in names])
        if m.sum() < min_pts:
            continue
        # densest-point placement: the region point closest to the region's centroid
        cx, cy = X[m].mean(), Y[m].mean()
        i = np.argmin((X[m] - cx) ** 2 + (Y[m] - cy) ** 2)
        ax.text(X[m][i], Y[m][i], nm, ha="center", va="center",
                fontsize=size, path_effects=HALO)


# ---------- panel (a): liquidus projection ----------
d = np.load(DATA / "_liquidus_projection.npz", allow_pickle=True)
fe, si = d["comps"][:, 0], d["comps"][:, 1]
Xa, Ya = tri_xy(fe, si)
prim = [str(p) for p in d["prim"]]
liqC = d["liqT"] - 273.15

GREY = {"OLIVINE": "0.78", "ORTHOPYROXENE": "0.88", "PERICLASE": "0.55",
        "WUSTITE": "0.42", "CRISTOBALITE": "0.68", "": "1.0"}
cats = sorted(set(prim))
code = np.array([cats.index(p) for p in prim], float)

fig, (axa, axb) = plt.subplots(1, 2, figsize=(12.6, 5.6), dpi=300)
ok = np.array([p != "" for p in prim]) & ~np.isnan(liqC)
axa.scatter(Xa[ok], Ya[ok], c=[GREY[p] for p in np.array(prim)[ok]], s=4.5,
            marker="s", linewidths=0)
# the cache is a regular barycentric grid: contour it as a 2-D field so no
# triangulation bridges across gaps (that produced jagged phantom contours)
fu = np.unique(np.round(fe, 9)); step = fu[1] - fu[0]
n = len(fu)
T2 = np.full((n, n), np.nan)
I = np.rint(fe / step).astype(int); J = np.rint(si / step).astype(int)
T2[J, I] = np.where(ok, liqC, np.nan)
# NaN-aware Gaussian smoothing: the cached scan quantizes the liquidus in 10 K
# steps, which staircases raw contours; smooth the field, not the physics
from scipy.ndimage import gaussian_filter
w = np.isfinite(T2).astype(float)
T0 = np.where(w > 0, T2, 0.0)
num = gaussian_filter(T0, 1.8); den = gaussian_filter(w, 1.8)
T2s = np.where(w > 0, num / np.maximum(den, 1e-9), np.nan)
FE2, SI2 = np.meshgrid(fu, fu)
X2 = FE2 + 0.5 * SI2; Y2 = S3 * SI2
cs = axa.contour(X2, Y2, T2s, levels=[1300, 1400, 1500, 1600, 1700, 1800],
                 colors="black", linewidths=1.0)
cl = axa.clabel(cs, fmt="%.0f", fontsize=9)
for t in cl:
    t.set_path_effects(HALO)
label_regions(axa, Xa[ok], Ya[ok], [ABBR[p] for p in np.array(prim)[ok]],
              min_pts=220, size=13, skip={"Crs"})
frame(axa)
axa.set_title("(a)", fontsize=13)

# ---------- panel (b): isothermal section at 1600 degC ----------
_spec = importlib.util.spec_from_file_location("td", DATA / "ternary_diagram.py")
td = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(td)
from mqmqa import ternary as tern

TK = 1600 + 273.15
pts, facets = td.build(TK, nsamp=9000)
N = 95
gx, gy, nsol, names = [], [], [], []
for i in range(N + 1):
    for j in range(N + 1 - i):
        x_fe, x_si = i / N, j / N
        a = tern.assemblage(pts, facets, x_fe, x_si)
        if a is None:
            continue
        key = sorted({("LIQUID" if ph.startswith("FEO") else ph)
                      for ph, amt, xf, xs in a if amt > 1e-3})
        x, y = tri_xy(x_fe, x_si)
        gx.append(x); gy.append(y)
        nsol.append(sum(1 for k in key if k != "LIQUID"))
        names.append("+".join(ABBR[k] for k in key))
gx, gy = np.array(gx), np.array(gy)
shade = {0: "1.0", 1: "0.82", 2: "0.60", 3: "0.42"}
axb.scatter(gx, gy, c=[shade[min(n, 3)] for n in nsol], s=5.5, marker="s", linewidths=0)
label_regions(axb, gx, gy, names, min_pts=30, size=11.5)
frame(axb)
axb.set_title("(b)", fontsize=13)

fig.savefig(HERE / "fig3_ternary.png", bbox_inches="tight", facecolor="white")
print("fig3_ternary.png written")
