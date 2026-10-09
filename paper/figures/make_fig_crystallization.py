"""Colour figure of the CaO-MgO-SiO2 crystallization diagram at 5 mol% FeO (cation basis): the
primary crystallizing phase across the section, with liquidus isotherms in K. The FeO level and
the cation-fraction basis go in the caption, not on the image.

Draws web/crystallization_cao_mgo_sio2.json, the browser's precomputed export of the shipped
quaternary (data/cao-feo-mgo-sio2/export_chunked.py), so it shows what the application shows.
Colours are the dataviz reference categorical set; hatrurite, the ninth phase and a field of a few
cells, reuses the clinopyroxene blue with hatching (the two fields never touch). No baked caption.
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import to_rgba
from matplotlib.patches import Polygon, Rectangle
from scipy.ndimage import (binary_dilation, distance_transform_edt, gaussian_filter,
                           map_coordinates)

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "web" / "crystallization_cao_mgo_sio2.json"
H = np.sqrt(3) / 2
INK = "#1a1a1a"
R = 1500
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"]})

COLOUR = {"CLINOPYROXENE": "#2a78d6", "MAGNESIOWUSTITE": "#eb6834", "OLIVINE": "#1baf7a",
          "LARNITE": "#eda100", "WOLLASTONITE": "#e87ba4", "RANKINITE": "#008300",
          "CRISTOBALITE": "#4a3aa7", "LIME": "#e34948", "HATRURITE": "#2a78d6",
          "ORTHOPYROXENE": "#86b6ef"}
HATCHED = {"HATRURITE"}
NAME = {"CLINOPYROXENE": "Clinopyroxene", "MAGNESIOWUSTITE": "Magnesiowüstite",
        "OLIVINE": "Olivine", "LARNITE": "Larnite (Ca$_2$SiO$_4$)",
        "WOLLASTONITE": "Wollastonite", "RANKINITE": "Rankinite (Ca$_3$Si$_2$O$_7$)",
        "CRISTOBALITE": "Cristobalite", "LIME": "Lime", "HATRURITE": "Hatrurite (Ca$_3$SiO$_5$)",
        "ORTHOPYROXENE": "Orthopyroxene"}
ABBR = {"CLINOPYROXENE": "Cpx", "MAGNESIOWUSTITE": "Mw", "OLIVINE": "Ol", "LARNITE": "Lrn",
        "WOLLASTONITE": "Wo", "RANKINITE": "Rnk", "CRISTOBALITE": "Crs", "LIME": "Lime",
        "HATRURITE": "Htr", "ORTHOPYROXENE": "Opx"}

d = json.load(open(SRC, encoding="utf-8"))
n, phases = d["ngrid"], d["phases"]
assert not set(phases) - set(COLOUR), set(phases) - set(COLOUR)
grid = np.full((n + 1, n + 1), -1, int)          # [i = Ca share, j = Si share]
tgrid = np.full((n + 1, n + 1), np.nan)
for i, (row, trow) in enumerate(zip(d["field_rows"], d["liquidus_C"])):
    for j, (ch, t) in enumerate(zip(row, trow)):
        if ch != ".":
            grid[i, j] = int(ch)
        if t is not None:
            tgrid[i, j] = t + 273.15

# CaO left, MgO right, SiO2 top: x = x_Mg + x_Si / 2, y = H x_Si
X, Y = np.meshgrid(np.linspace(0, 1, R), np.linspace(0, H, int(R * H)))
b = Y / H
a = 1.0 - X - 0.5 * b
inside = (a >= -1e-9) & (b >= -1e-9) & (a + b <= 1 + 1e-9)
coords = [np.clip(a * n, 0, n), np.clip(b * n, 0, n)]
_, (ii, jj) = distance_transform_edt(grid < 0, return_indices=True)
full = grid[ii, jj]
present = sorted(set(full[grid >= 0].ravel()))
stack = np.stack([map_coordinates(gaussian_filter((full == k).astype(float), 1.0), coords,
                                  order=1, mode="nearest") for k in present])
idx = np.array(present)[np.argmax(stack, axis=0)]
idx[~inside] = -1

rgba = np.zeros(idx.shape + (4,))
stripes = ((np.arange(idx.shape[1])[None, :] + np.arange(idx.shape[0])[:, None]) % 18) < 6
for k in present:
    ph = phases[k]
    m = idx == k
    rgba[m] = to_rgba(COLOUR[ph])
    if ph in HATCHED:
        rgba[m & stripes] = (1, 1, 1, 1)

fig = plt.figure(figsize=(9.6, 6.2), dpi=500)
ax = fig.add_axes([0.02, 0.04, 0.66, 0.92])
ax.imshow(rgba, origin="lower", extent=(0, 1, 0, H), interpolation="nearest")
ax.add_patch(Polygon([(0, 0), (1, 0), (0.5, H)], closed=True, fill=False, ec=INK, lw=1.2, zorder=6))

# liquidus isotherms from the grid (contoured on the stored nodes, lightly smoothed)
A, B = np.meshgrid(np.arange(n + 1) / n, np.arange(n + 1) / n, indexing="ij")
ok = np.isfinite(tgrid)
w = ok.astype(float)
Ts = gaussian_filter(np.where(ok, tgrid, 0.0), 0.8) / np.maximum(gaussian_filter(w, 0.8), 1e-9)
Ts[~ok] = np.nan
cs = ax.contour((1 - A - B) + 0.5 * B, H * B, Ts, levels=[1673, 1873, 2073, 2273, 2473, 2673],
                colors=INK, linewidths=0.9, zorder=3)
halo = [pe.withStroke(linewidth=2.6, foreground="white")]
for t in ax.clabel(cs, fmt="%.0f", fontsize=8.5, inline_spacing=2):
    t.set_path_effects(halo)

lines = np.zeros(idx.shape, bool)
ny, nx = idx.shape
for seg in [s for c in cs.allsegs for s in c]:
    if len(seg) < 2:
        continue
    t = np.linspace(0, 1, 40 * len(seg))
    px = np.interp(t, np.linspace(0, 1, len(seg)), seg[:, 0])
    py = np.interp(t, np.linspace(0, 1, len(seg)), seg[:, 1])
    lines[np.clip((py / H * (ny - 1)).astype(int), 0, ny - 1),
          np.clip((px * (nx - 1)).astype(int), 0, nx - 1)] = True
blocked = binary_dilation(lines, iterations=int(0.012 * R))
for k in present:
    ph = phases[k]
    dist = distance_transform_edt(np.pad((idx == k) & ~blocked, 1), sampling=(1.0, 0.35))[1:-1, 1:-1]
    if dist.max() >= 0.02 * R:
        r, c = np.unravel_index(np.argmax(dist), dist.shape)
        ax.text(X[r, c], Y[r, c], ABBR[ph], color=INK, fontsize=11, ha="center", va="center",
                zorder=5, path_effects=[pe.withStroke(linewidth=3, foreground="white")])
    else:                                   # thin field: label outside with a leader
        band = distance_transform_edt(np.pad(idx == k, 1))[1:-1, 1:-1]
        r, c = np.unravel_index(np.argmax(band), band.shape)
        x0, y0 = X[r, c], Y[r, c]
        left = x0 < 0.5
        ax.annotate(ABBR[ph], xy=(x0, y0), xytext=(x0 + (-0.16 if left else 0.16), y0 - 0.05),
                    fontsize=11, color=INK, ha="right" if left else "left", va="center", zorder=7,
                    arrowprops=dict(arrowstyle="-", color=INK, lw=0.8))

for x, y, s, ha, va in ((-0.012, -0.025, "CaO", "right", "top"), (1.012, -0.025, "MgO", "left", "top"),
                        (0.5, H + 0.02, "SiO$_2$", "center", "bottom")):
    ax.text(x, y, s, color=INK, fontsize=13, ha=ha, va=va)
ax.set_xlim(-0.12, 1.1)
ax.set_ylim(-0.08, H + 0.07)
ax.set_aspect("equal")
ax.axis("off")

lx = fig.add_axes([0.69, 0.14, 0.3, 0.76])
lx.axis("off"); lx.set_xlim(0, 1); lx.set_ylim(0, 1)
lx.text(0, 0.97, "Primary phase", color=INK, fontsize=12, fontweight="bold", va="center")
order = [p for p in ["CRISTOBALITE", "WOLLASTONITE", "RANKINITE", "LARNITE", "HATRURITE", "LIME",
                     "MAGNESIOWUSTITE", "OLIVINE", "CLINOPYROXENE", "ORTHOPYROXENE"]
         if phases.index(p) in present]
for m, ph in enumerate(order):
    y = 0.89 - m * 0.085
    lx.add_patch(Rectangle((0, y - 0.028), 0.09, 0.056, color=COLOUR[ph]))
    if ph in HATCHED:
        for k in range(4):
            lx.plot([0.012 + 0.024 * k, 0.03 + 0.024 * k], [y - 0.028, y + 0.028], color="white", lw=1.6)
    label = NAME[ph] if ABBR[ph] == NAME[ph] else f"{NAME[ph]}  ({ABBR[ph]})"
    lx.text(0.13, y, label, color=INK, fontsize=10.5, va="center")
yl = 0.89 - len(order) * 0.085
lx.plot([0, 0.09], [yl, yl], color=INK, lw=0.9)
lx.text(0.13, yl, "Liquidus isotherm, K", color=INK, fontsize=10.5, va="center")

out = HERE / "fig_crystallization_cms.png"
fig.savefig(out, facecolor="white")
print("wrote", out)
