"""Regenerate fig3_ternary.png: (a) liquidus projection, (b) isothermal section at 1873 K.

Both panels draw the browser's precomputed exports (web/ternary_feo_mgo_sio2.json and
web/ternary_isothermal_feo_mgo_sio2.json), so the figure shows what the application shows; those
files are written from the shipped combined database by data/feo-mgo-sio2/export_*_json.py.
Colour fields with direct labels and halos, Kelvin throughout, no baked caption. The field colours
are the ones on the group deck's slide 18 and pass the dataviz palette check on white.
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import to_rgba
from matplotlib.patches import Polygon
from scipy.ndimage import (binary_dilation, distance_transform_edt, gaussian_filter,
                           map_coordinates)

HERE = Path(__file__).resolve().parent
WEB = HERE.parents[1] / "web"
H = np.sqrt(3) / 2
INK = "#1a1a1a"
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"]})

COLOUR = {"CRISTOBALITE": "#8f84c9", "OLIVINE": "#44a065", "ORTHOPYROXENE": "#3d78d6",
          "MAGNESIOWUSTITE": "#d07a43"}
ABBR = {"LIQUID": "L", "CRISTOBALITE": "Crs", "OLIVINE": "Ol", "ORTHOPYROXENE": "Opx",
        "MAGNESIOWUSTITE": "Mw"}
R = 1400                       # raster columns per panel


def tint(c, f):
    """c mixed toward white, f = share of the colour kept."""
    r = np.array(to_rgba(c))
    r[:3] = 1.0 - f * (1.0 - r[:3])
    return tuple(r)


def raster(field_rows, n):
    """Nearest-node raster of an export's field digits, with a one-node blur on each field's
    indicator so edges follow the grid without stairs (boundaries move under one node)."""
    grid = np.full((n + 1, n + 1), -1, int)
    for i, row in enumerate(field_rows):
        for j, ch in enumerate(row):
            if ch != ".":
                grid[i, j] = int(ch)
    _, (ii, jj) = distance_transform_edt(grid < 0, return_indices=True)
    full = grid[ii, jj]
    X, Y = np.meshgrid(np.linspace(0, 1, R), np.linspace(0, H, int(R * H)))
    xsi = Y / H
    xfe = X - 0.5 * xsi
    inside = (xfe >= -1e-9) & (xsi >= -1e-9) & (xfe + xsi <= 1 + 1e-9)
    coords = [np.clip(xfe * n, 0, n), np.clip(xsi * n, 0, n)]
    k_all = sorted(set(full.ravel()) - {-1})
    stack = np.stack([map_coordinates(gaussian_filter((full == k).astype(float), 1.0), coords,
                                      order=1, mode="nearest") for k in k_all])
    idx = np.array(k_all)[np.argmax(stack, axis=0)]
    idx[~inside] = -1
    return X, Y, idx


def paint(ax, idx, colours):
    rgba = np.zeros(idx.shape + (4,))
    for k, c in colours.items():
        rgba[idx == k] = to_rgba(c)
    ax.imshow(rgba, origin="lower", extent=(0, 1, 0, H), interpolation="nearest")


def label_fields(ax, X, Y, idx, names, blocked, size=12.5, min_frac=0.02):
    """Each field labelled at its most interior point, away from lines and their labels. A field
    too thin to hold its label gets it outside the left edge with a leader line."""
    for k, name in names.items():
        dist = distance_transform_edt(np.pad((idx == k) & ~blocked, 1),
                                      sampling=(1.0, 0.35))[1:-1, 1:-1]
        if dist.max() < min_frac * R:
            band = distance_transform_edt(np.pad(idx == k, 1))[1:-1, 1:-1]
            if band.max() == 0:
                continue
            rows, cols = np.nonzero(band >= 0.5 * band.max())
            m = np.argmin(X[rows, cols])                 # the band's end nearest the left edge
            x0, y0 = X[rows[m], cols[m]] + 0.04, Y[rows[m], cols[m]]
            ax.annotate(name, xy=(x0, y0), xytext=(y0 / (2 * H) - 0.09, y0 + 0.05),
                        fontsize=size, color=INK, ha="right", va="center", zorder=7,
                        arrowprops=dict(arrowstyle="-", color=INK, lw=0.9))
            continue
        r, c = np.unravel_index(np.argmax(dist), dist.shape)
        ax.text(X[r, c], Y[r, c], name, color=INK, fontsize=size, ha="center", va="center",
                zorder=5, path_effects=[pe.withStroke(linewidth=3.2, foreground="white")])


def frame(ax, title):
    ax.add_patch(Polygon([(0, 0), (1, 0), (0.5, H)], closed=True, fill=False, ec=INK, lw=1.2,
                         zorder=6))
    for x, y, s, ha, va in ((-0.012, -0.025, "MgO", "right", "top"),
                            (1.012, -0.025, "FeO", "left", "top"),
                            (0.5, H + 0.02, "SiO$_2$", "center", "bottom")):
        ax.text(x, y, s, color=INK, fontsize=13, ha=ha, va=va)
    ax.set_xlim(-0.1, 1.1)
    ax.set_ylim(-0.08, H + 0.08)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, fontsize=14)


fig, (axa, axb) = plt.subplots(1, 2, figsize=(12.6, 5.6), dpi=600)

# ---------- (a) liquidus projection ----------
d = json.load(open(WEB / "ternary_feo_mgo_sio2.json", encoding="utf-8"))
X, Y, idx = raster(d["field_rows"], d["ngrid"])
missing = set(d["phases"]) - set(COLOUR)
assert not missing, f"no colour for {missing}"
paint(axa, idx, {k: COLOUR[p] for k, p in enumerate(d["phases"])})
arcs = [(it["degC"], np.column_stack((np.asarray(a)[:, 0] + 0.5 * np.asarray(a)[:, 1],
                                      H * np.asarray(a)[:, 1])))
        for it in d["isotherms"] for a in it["arcs"]]
for _, P in arcs:
    axa.plot(P[:, 0], P[:, 1], color=INK, lw=1.0, zorder=3)
# each isotherm labelled where it crosses x_SiO2 = 0.24 or 0.32 (alternating), on the olivine
# side, where every isotherm crosses once and they are evenly spaced
halo = [pe.withStroke(linewidth=3, foreground="white")]
for m, it in enumerate(sorted(d["isotherms"], key=lambda q: q["degC"])):
    y0 = H * (0.32 if m % 2 else 0.24)
    hits = [(P[k, 0] + (y0 - P[k, 1]) / (P[k + 1, 1] - P[k, 1]) * (P[k + 1, 0] - P[k, 0]), y0)
            for t, P in arcs if t == it["degC"] for k in range(len(P) - 1)
            if (P[k, 1] - y0) * (P[k + 1, 1] - y0) <= 0 and P[k, 1] != P[k + 1, 1]]
    if hits:
        x, y = min(hits)
        axa.text(x, y, f"{it['degC'] + 273}", color=INK, fontsize=9.5, ha="center", va="center",
                 zorder=4, path_effects=halo,
                 bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.75))
lines = np.zeros(idx.shape, bool)
ny, nx = idx.shape
for _, P in arcs:
    t = np.linspace(0, 1, 40 * len(P))
    px = np.interp(t, np.linspace(0, 1, len(P)), P[:, 0])
    py = np.interp(t, np.linspace(0, 1, len(P)), P[:, 1])
    lines[np.clip((py / H * (ny - 1)).astype(int), 0, ny - 1),
          np.clip((px * (nx - 1)).astype(int), 0, nx - 1)] = True
label_fields(axa, X, Y, idx, {k: ABBR[p] for k, p in enumerate(d["phases"])},
             binary_dilation(lines, iterations=int(0.02 * R)))
frame(axa, "(a)")

# ---------- (b) isothermal section, 1873 K ----------
iso = json.load(open(WEB / "ternary_isothermal_feo_mgo_sio2.json", encoding="utf-8"))
sec = next(s for s in iso["sections"] if s["degC"] == 1600)        # 1873 K
X, Y, idx = raster(sec["field_rows"], iso["ngrid"])


def assemblage_colour(phs):
    solids = [p for p in phs if p != "LIQUID"]
    if not solids:
        return "#f6f3ec"                                  # liquid alone
    if len(solids) == 1:
        c = COLOUR[solids[0]]
        return tint(c, 0.45) if "LIQUID" in phs else c    # pale where liquid coexists
    if "LIQUID" in phs:
        return "#b9b9b9"                                  # three-phase triangle
    mix = np.mean([np.array(to_rgba(COLOUR[s])) for s in solids], axis=0)
    return tuple(mix)


asm = sec["assemblages"]
paint(axb, idx, {k: assemblage_colour(p) for k, p in enumerate(asm)})
label_fields(axb, X, Y, idx, {k: " + ".join(ABBR[p] for p in ["LIQUID"] * ("LIQUID" in a)
                                            + sorted(q for q in a if q != "LIQUID"))
                              for k, a in enumerate(asm)},
             np.zeros(idx.shape, bool), size=11.5, min_frac=0.025)
frame(axb, "(b)")

fig.savefig(HERE / "fig3_ternary.png", bbox_inches="tight", facecolor="white")
print("fig3_ternary.png written")
