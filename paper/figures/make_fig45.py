"""Regenerate fig4 (LiCl-KCl) and fig5 (Al-Zn) at 600 DPI.

Same physics as the worked-example listings (paper/examples_salt.py and
paper/examples_alloy.py), rendered as the greyscale class maps the captions
describe: light liquid, mid two-phase, dark subsolidus, with the calculated
eutectic as a dot and the measured/assessed one as a star.
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "python"))

from mqmqa import Database
from mqmqa.equilibrium import build_inputs, multiphase_binary

plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"]})

SHADE = {0: 0.90, 1: 0.62, 2: 0.22}   # liquid, liquid+solid, subsolidus


def render(grid, Ts, xs, dot, star, xlabel, out):
    fig, ax = plt.subplots(figsize=(4.6, 3.5), dpi=650)
    ax.imshow(grid, origin="lower", aspect="auto", cmap="gray", vmin=0.0, vmax=1.0,
              extent=[xs[0], xs[-1], Ts[0], Ts[-1]])
    ax.plot(*dot, "o", color="black", markersize=6)
    ax.plot(*star, "*", color="white", markeredgecolor="black", markersize=13)
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel("T (K)", fontsize=11)
    ax.tick_params(labelsize=10)
    fig.savefig(HERE / out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(out, "written")


def salt():
    db = Database.read(str(ROOT / "web" / "LiCl-KCl.dat"))
    liq = db.phase_index("LICL-KCL-LIQUID")
    LiCl, KCl = {"LI": 1, "CL": 1}, {"K": 1, "CL": 1}
    Ts = np.arange(500.0, 1101.0, 10.0)
    xs = np.arange(0.025, 1.0, 0.025)
    grid = np.zeros((len(Ts), len(xs)))
    for i, T in enumerate(Ts):
        inp = build_inputs(db, liq, T)
        solids = [(0.0, db.stoich_gibbs(0, T), "LiCl(s)"),
                  (1.0, db.stoich_gibbs(1, T), "KCl(s)")]
        for j, xi in enumerate(xs):
            ph = multiphase_binary(inp, LiCl, KCl, solids, xi, ngrid=80)["phases"]
            n_liq = sum(1 for q in ph if q == "LIQUID")
            cls = 0 if ph == ["LIQUID"] else (1 if n_liq else 2)
            grid[i, j] = SHADE[cls]
    render(grid, Ts, xs, (0.400, 640.0), (0.415, 626.0), r"$x_\mathrm{KCl}$",
           "fig4_salt_example.png")


def lower_hull(pts):
    pts = sorted(pts)
    hull = []
    for pt in pts:
        while len(hull) >= 2:
            (x1, g1, _), (x2, g2, _) = hull[-2], hull[-1]
            if (g2 - g1) * (pt[0] - x1) >= (pt[1] - g1) * (x2 - x1):
                hull.pop()
            else:
                break
        hull.append(pt)
    return hull


def alloy():
    db = Database.read(str(ROOT / "web" / "AlZn.tdb"))
    phases = [(db.phase_index(n), n) for n in db.phase_names]
    Ts = np.arange(300.0, 1001.0, 5.0)
    xs = np.arange(0.0125, 1.0, 0.0125)
    grid = np.zeros((len(Ts), len(xs)))
    for i, T in enumerate(Ts):
        pts = []
        for p, name in phases:
            for y in np.linspace(1e-4, 1 - 1e-4, 60):
                g = db.cef_gibbs(p, [1.0 - y, y], T, per_mole_atoms=True)
                pts.append((y, g, "liq" if "LIQUID" in name else "sol"))
        hull = lower_hull(pts)
        hx = [h[0] for h in hull]
        for j, xi in enumerate(xs):
            k = int(np.searchsorted(hx, xi))
            k = min(max(k, 1), len(hull) - 1)
            a, b = hull[k - 1][2], hull[k][2]
            cls = 0 if (a == "liq" and b == "liq") else (2 if (a == "sol" and b == "sol") else 1)
            grid[i, j] = SHADE[cls]
    render(grid, Ts, xs, (0.890, 660.0), (0.885, 654.0), r"$x_\mathrm{Zn}$",
           "fig5_alloy_example.png")


if __name__ == "__main__":
    salt()
    alloy()
