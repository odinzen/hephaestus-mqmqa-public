"""Black-and-white MgO-SiO2 v0.4 binary phase diagram (T vs x_SiO2).

At each temperature the stable state is the lower convex hull of the liquid G(x) curve
(MQMQA engine) plus the fixed-composition solids (periclase, forsterite, enstatite,
cristobalite; Neumann-Kopp Gibbs from phase_diagram.py). Sweeping T over the hull
traces every boundary:
  - liquid + solid tie  -> LIQUIDUS (split per crystallising solid, and per branch),
  - liquid + liquid tie -> the two-liquid miscibility gap BINODAL,
  - the T at which liquid disappears at a given x -> the SOLIDUS, below which the join
    is two coexisting solids.

CONDENSED-ONLY: there is no gas phase. At high T the real system vaporises (SiO(g),
Mg(g), O2), which both caps the condensed field and (with the missing excess entropy)
is why the modelled two-liquid dome runs unphysically hot - see PROVENANCE.md.
"""

import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "python"))

import mqmqa
from mqmqa import equilibrium as eq
import _activity as act
import phase_diagram as pdg

COMPONENTS = pdg.COMPONENTS
DAT = HERE / "MgO-SiO2-liquid.dat"
XC = {n: pdg.SOLIDS[n][1] / (pdg.SOLIDS[n][0] + pdg.SOLIDS[n][1]) for n in pdg.SOLIDS}


def liquid_curve(db, p, T, xs):
    inp = eq.build_inputs(db, p, T, components=COMPONENTS)
    g_mg = act.g_pure_liquid(inp, "MgO")
    g_si = act.g_pure_liquid(inp, "SiO2")
    return np.array([act.delta_g_mix(inp, float(x)) + (1 - x) * g_mg + x * g_si
                     for x in xs])


def lower_hull(pts):
    pts = sorted(pts, key=lambda q: q[0])
    h = []
    for x, g, lab in pts:
        while len(h) >= 2:
            (x1, g1, _), (x2, g2, _) = h[-2], h[-1]
            if (x2 - x1) * (g - g1) - (g2 - g1) * (x - x1) <= 1e-9:
                h.pop()
            else:
                break
        h.append((x, g, lab))
    return h


def sweep(db, p, Tgrid, xs):
    """liquidus[(solid, side)] -> [(x,T)]; binodal -> [(x,T)]; solidus -> [(x,T)]."""
    dx = xs[1] - xs[0]
    liquidus = {}
    binodal = []
    liquid_present = np.zeros((len(Tgrid), len(xs)), bool)
    for it, T in enumerate(Tgrid):
        g = liquid_curve(db, p, T, xs)
        pts = [(float(x), float(gg), "L") for x, gg in zip(xs, g)]
        for name in pdg.SOLIDS:
            gs, xsld = pdg.solid_gibbs_per_formula_unit(name, T)
            pts.append((float(xsld), float(gs), name))
        hull = lower_hull(pts)
        hx = np.array([h[0] for h in hull])
        for i in range(len(hull) - 1):
            xl, _, ll = hull[i]
            xr, _, lr = hull[i + 1]
            if xr - xl <= 1.8 * dx:
                continue
            if ll == "L" and lr == "L":
                binodal += [(xl, T), (xr, T)]
            else:
                if ll == "L":               # liquid on the left of a solid on its right
                    side = "R" if xl < XC[lr] else "L"
                    liquidus.setdefault((lr, side), []).append((xl, T))
                if lr == "L":
                    side = "R" if xr > XC[ll] else "L"
                    liquidus.setdefault((ll, side), []).append((xr, T))
        for ix, x in enumerate(xs):
            j = min(max(int(np.searchsorted(hx, x)), 1), len(hull) - 1)
            liquid_present[it, ix] = (hull[j - 1][2] == "L") or (hull[j][2] == "L")
    solidus = []
    for ix, x in enumerate(xs):
        col = np.where(liquid_present[:, ix])[0]
        if len(col):
            solidus.append((x, Tgrid[col.min()]))
    return liquidus, np.array(binodal), np.array(solidus)


def main():
    db = mqmqa.Database.read(str(DAT))
    p = db.phase_index("MGO-SIO2-LIQUID")
    xs = np.linspace(0.002, 0.998, 320)
    Tgrid = np.linspace(1350.0, 3170.0, 240)
    liquidus, binodal, solidus = sweep(db, p, Tgrid, xs)

    plt.rcParams.update({"font.size": 10, "axes.linewidth": 1.0})
    fig, ax = plt.subplots(figsize=(8.0, 6.2))

    # liquidus branches (each crystallising solid, each side) as smooth black lines
    for (name, side), pts in liquidus.items():
        a = np.array(sorted(pts, key=lambda q: q[1]))
        if len(a) > 2:
            ax.plot(a[:, 0], a[:, 1], "-", c="k", lw=1.5)

    # two-liquid gap binodal (dashed) - the v0.4 feature
    if len(binodal):
        Ts = np.unique(binodal[:, 1])
        left = np.array([[binodal[binodal[:, 1] == T, 0].min(), T] for T in Ts])
        right = np.array([[binodal[binodal[:, 1] == T, 0].max(), T] for T in Ts])
        dome = np.vstack([left[np.argsort(left[:, 1])], right[np.argsort(-right[:, 1])]])
        ax.plot(dome[:, 0], dome[:, 1], "--", c="k", lw=1.5,
                label="two-liquid gap (model)")

    # solidus horizontals
    s = solidus[np.argsort(solidus[:, 0])]
    ax.plot(s[:, 0], s[:, 1], "-", c="k", lw=1.5)

    # sub-solidus compound dividers
    for xc in (1.0 / 3.0, 0.5):
        ax.plot([xc, xc], [1350, np.interp(xc, s[:, 0], s[:, 1])], "-", c="0.6", lw=0.8)

    # invariant / anchor markers
    ax.plot(1.0 / 3.0, 2163, "*", ms=15, mfc="k", mec="k", zorder=6)
    ax.annotate("forsterite congruent\n2163 K (obs.)", (1.0 / 3.0, 2163),
                xytext=(0.36, 2320), fontsize=8, ha="left")
    # Greig measured monotectic (what the model should ideally reproduce)
    ax.plot([0.59, 0.99], [1968, 1968], "o", ms=6, mfc="white", mec="k", zorder=6)
    ax.plot([0.59, 0.99], [1968, 1968], "-", c="0.5", lw=0.8)
    ax.annotate("Greig monotectic 1968 K\n(measured; model runs hot)",
                (0.79, 1968), xytext=(0.55, 1640), fontsize=8, ha="left",
                arrowprops=dict(arrowstyle="->", color="0.5", lw=0.8))

    # phase-field labels
    fields = [(0.28, 2780, "liquid  (L)"), (0.10, 2380, "MgO + L"),
              (0.83, 2620, "two liquids\n(L$_1$ + L$_2$)"),
              (0.165, 1600, "MgO\n+ Mg$_2$SiO$_4$"),
              (0.415, 1600, "Mg$_2$SiO$_4$\n+ MgSiO$_3$"),
              (0.75, 1560, "MgSiO$_3$ + SiO$_2$")]
    for x, T, txt in fields:
        ax.text(x, T, txt, fontsize=8.5, c="0.25", ha="center", va="center",
                style="italic")

    ax.set_xlim(0, 1)
    ax.set_ylim(1350, 3170)
    ax.set_xlabel("$x_{\\mathrm{SiO_2}}$  (mole fraction SiO$_2$)")
    ax.set_ylabel("Temperature (K)")
    ax.set_title("MgO-SiO$_2$ from the open v0.4 MQMQA model  (condensed phases only)",
                 fontsize=11)
    ax.legend(loc="lower right", fontsize=8, frameon=True, framealpha=0.95)

    out = HERE / "phase_diagram_v04.png"
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    print(f"wrote {out}")
    print(f"liquidus branches: {len(liquidus)}  binodal: {len(binodal)}  solidus: {len(solidus)}")


if __name__ == "__main__":
    main()
