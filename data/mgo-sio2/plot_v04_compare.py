"""Side-by-side MgO-SiO2 phase diagrams: our open v0.4 model vs the measured diagram.

Both panels are drawn in the same clean schematic style so the two are directly
comparable, and every liquidus is snapped to its solidus so the invariants close to
sharp points. Liquidus curves are monotone (PCHIP) splines through the invariant knots;
the KNOTS are the physics:
  - MODEL knots are the invariants computed from the v0.4 engine (v04_fit.py /
    phase_hull.py / the two-liquid hull sweep) - see PROVENANCE.md.
  - MEASURED knots are the classic experimental invariants: Bowen & Andersen 1914
    (forsterite congruent 2163 K; periclase-forsterite eutectic 2123 K), the enstatite
    incongruent (peritectic) melting 1830 K and enstatite-silica eutectic ~1816 K, and
    Greig 1927's two-liquid immiscibility (monotectic 1968 K, conjugate liquids
    ~0.59/0.99). Both are CONDENSED-only (no gas phase).

The comparison makes the documented model limits visible: the periclase-forsterite
eutectic squashed against forsterite melting, the peritectic + eutectic compressed, and
above all the two-liquid gap running far too hot (model monotectic ~2365 K vs 1968 K).
"""

import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.interpolate import PchipInterpolator

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "python"))

# ----------------------------------------------------------------------------
# Diagram data. Points are (x_SiO2, T[K]). Liquidus segments are lists of knots.
# ----------------------------------------------------------------------------

# MODEL: invariants computed from the open v0.4 model (PROVENANCE.md).
MODEL = dict(
    liquidus=[
        [(0.0, 3098), (0.12, 2760), (0.22, 2430), (0.315, 2162)],   # periclase
        [(0.315, 2162), (1.0 / 3, 2163)],                            # -> forsterite max
        [(1.0 / 3, 2163), (0.42, 2060), (0.50, 1946)],               # forsterite -> peritectic
        [(0.50, 1946), (0.55, 1935)],                                # enstatite -> eutectic
        [(0.55, 1935), (0.60, 2100), (0.64, 2365)],                  # cristobalite -> monotectic
        [(0.96, 2365), (0.985, 2150), (1.0, 1996)],                  # silica-side cristobalite
    ],
    dome=dict(xL=0.64, xR=0.96, Tm=2365, xc=0.83, Tc=3115),          # two-liquid gap
    solidus=[(0.0, 1.0 / 3, 2162), (1.0 / 3, 0.50, 1946), (0.50, 1.0, 1935)],
    congruent=(1.0 / 3, 2163),
    mono_pts=[(0.64, 2365), (0.96, 2365)],
    title="Open v0.4 MQMQA model (computed)",
)

# MEASURED: classic experimental invariants (Bowen-Andersen 1914; Greig 1927).
MEAS = dict(
    liquidus=[
        [(0.0, 3098), (0.12, 2760), (0.22, 2420), (0.265, 2123)],   # periclase
        [(0.265, 2123), (0.30, 2150), (1.0 / 3, 2163)],              # -> forsterite max
        [(1.0 / 3, 2163), (0.42, 1980), (0.52, 1830)],               # forsterite -> peritectic
        [(0.52, 1830), (0.55, 1816)],                                # enstatite -> eutectic
        [(0.55, 1816), (0.575, 1900), (0.588, 1968)],                # cristobalite -> monotectic
        [(0.988, 1968), (0.995, 1985), (1.0, 1996)],                 # silica-side cristobalite
    ],
    dome=dict(xL=0.588, xR=0.988, Tm=1968, xc=0.80, Tc=2150),        # Greig immiscibility
    solidus=[(0.0, 1.0 / 3, 2123), (1.0 / 3, 0.50, 1830), (0.50, 1.0, 1816)],
    congruent=(1.0 / 3, 2163),
    mono_pts=[(0.588, 1968), (0.988, 1968)],
    title="Measured (Bowen-Andersen 1914, Greig 1927)",
)


def spline(knots, n=80):
    a = np.array(knots)
    if len(a) == 2:
        return a[:, 0], a[:, 1]
    xs = np.linspace(a[0, 0], a[-1, 0], n)
    return xs, PchipInterpolator(a[:, 0], a[:, 1])(xs)


def dome_curve(d, n=120):
    xs_l = np.linspace(d["xL"], d["xc"], n // 2)
    xs_r = np.linspace(d["xc"], d["xR"], n // 2)
    left = PchipInterpolator([d["xL"], d["xc"]], [d["Tm"], d["Tc"]])
    right = PchipInterpolator([d["xc"], d["xR"]], [d["Tc"], d["Tm"]])
    x = np.concatenate([xs_l, xs_r])
    T = np.concatenate([left(xs_l), right(xs_r)])
    return x, T


def draw(ax, D, fields, c="k", ls="-", lw=1.6, gap_ls="--", verticals=True, markers=True):
    for seg in D["liquidus"]:
        x, T = spline(seg)
        ax.plot(x, T, ls, c=c, lw=lw)
    x, T = dome_curve(D["dome"])
    ax.plot(x, T, gap_ls, c=c, lw=lw)
    for x0, x1, Ts in D["solidus"]:
        ax.plot([x0, x1], [Ts, Ts], ls, c=c, lw=lw)
    if verticals:
        for xc in (1.0 / 3, 0.5):
            Ts = next(Ts for a, b, Ts in D["solidus"] if a <= xc <= b)
            ax.plot([xc, xc], [1350, Ts], "-", c="0.65", lw=0.8)
    if markers:
        ax.plot(*D["congruent"], "*", ms=13, mfc=c, mec=c, zorder=6)
        mp = np.array(D["mono_pts"])
        ax.plot(mp[:, 0], mp[:, 1], "o", ms=5, mfc="white", mec=c, zorder=6)
        ax.plot(mp[:, 0], mp[:, 1], "-", c=c, lw=0.8)
    for x, T, txt in fields:
        ax.text(x, T, txt, fontsize=7.5, c="0.3", ha="center", va="center", style="italic")
    ax.set_xlim(0, 1); ax.set_ylim(1350, 3170)
    ax.set_xlabel("$x_{\\mathrm{SiO_2}}$")


FIELDS = [(0.14, 2500, "MgO + L"), (0.30, 2800, "L"), (0.82, 2500, "L$_1$+L$_2$"),
          (0.165, 1620, "MgO +\nMg$_2$SiO$_4$"), (0.415, 1620, "Mg$_2$SiO$_4$\n+MgSiO$_3$"),
          (0.75, 1560, "MgSiO$_3$ + SiO$_2$")]


def main():
    plt.rcParams.update({"font.size": 10})
    fig = plt.figure(figsize=(12.4, 9.0))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.35, 1.0], hspace=0.28, wspace=0.06)
    axm = fig.add_subplot(gs[0, 0])
    axe = fig.add_subplot(gs[0, 1], sharey=axm)
    axz = fig.add_subplot(gs[1, :])

    draw(axm, MODEL, FIELDS)
    draw(axe, MEAS, FIELDS)
    axm.set_ylabel("Temperature (K)")
    axe.tick_params(labelleft=False)
    axm.set_title(MODEL["title"], fontsize=10)
    axe.set_title(MEAS["title"], fontsize=10)
    axm.annotate("gap too hot\n(monotectic ~2365 K,\nconsolute ~3115 K)", (0.83, 2900),
                 xytext=(0.36, 2900), fontsize=8, ha="left",
                 arrowprops=dict(arrowstyle="->", color="0.4"))
    axe.annotate("monotectic 1968 K\n(low, flat dome)", (0.80, 1990), xytext=(0.40, 2350),
                 fontsize=8, ha="left", arrowprops=dict(arrowstyle="->", color="0.4"))

    # overlay zoom of the forsterite -> enstatite -> silica region: model vs measured
    draw(axz, MODEL, [], c="k", ls="-", gap_ls="--", verticals=False)
    draw(axz, MEAS, [], c="0.55", ls="-", lw=1.4, gap_ls="--", verticals=False, markers=False)
    axz.set_xlim(0.24, 0.72); axz.set_ylim(1780, 2260)
    axz.set_ylabel("Temperature (K)")
    axz.set_title("Overlay of the forsterite -> enstatite -> silica region "
                  "(black = model, grey = measured)", fontsize=9.5)
    axz.annotate("periclase-forsterite eutectic:\nmodel ~2160 K (squashed onto\nforsterite "
                 "melting) vs measured 2123 K", (0.30, 2140), xytext=(0.245, 1960),
                 fontsize=7.5, arrowprops=dict(arrowstyle="->", color="0.4", lw=0.7))
    axz.annotate("enstatite peritectic + En-Crs eutectic:\nmodel ~1946/1935 K (merged) "
                 "vs measured 1830/1816 K", (0.52, 1940), xytext=(0.45, 2120),
                 fontsize=7.5, arrowprops=dict(arrowstyle="->", color="0.4", lw=0.7))
    axz.plot(1.0/3, 2163, "*", ms=12, mfc="k", mec="k")

    fig.suptitle("MgO-SiO$_2$ condensed phase diagram: open v0.4 model vs measured\n"
                 "(same drawing style; liquidus splined through the invariant knots; "
                 "no gas phase in either)", fontsize=11)
    out = HERE / "phase_diagram_v04_compare.png"
    fig.savefig(out, dpi=160, bbox_inches="tight")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
