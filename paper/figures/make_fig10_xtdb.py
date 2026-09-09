"""Figure 10: third-generation XTDB diagrams computed by the browser engine.

The XTDB reader (src/xtdb.c, compiled to WASM) parses the open XML CALPHAD format and
assembles third-generation Gibbs energies: an Einstein heat-capacity term, GEIN(theta) =
1.5 R theta + 3 R T ln(1 - exp(-theta/T)), and a two-state liquid, -R T ln(1 + exp(-dG/RT)).
The binary diagram is the lower convex hull of the phase Gibbs energies at each temperature
(common-tangent construction), the same computation the web app runs live.

(a) Al-C from the third-generation assessment of He et al., Calphad 72 (2021) 102250: the
    Al-rich liquid, the Al4C3 line compound at x_C = 3/7, and graphite. Pure-Al melts at
    933.47 K, reproducing the assessment.
(b) Pb-Sn (classic SGTE unaries + Redlich-Kister excess written in XTDB) reproduces the
    eutectic at 456 K and x(Sn) ~ 0.74.

Reference evaluator shared with the C engine (validated to < 1e-6 J/mol-atom). Greyscale,
>= 600 DPI, no baked text; the caption carries the description.
"""
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "data" / "xtdb-alc"))
import xtdb_ref as X  # noqa: E402


def region_grid(path, B, Tlo, Thi, NX=320, NT=300, NS=140):
    """Stable-phase map: grid[r,c] = phase index, or -1 for a two-phase (tie-line) region.
    Mirrors the lower-hull construction in src/xtdb.c and the web app."""
    tp, params, phases = X.parse(str(path))
    names = list(phases.keys())
    # which phases are stoichiometric (line compounds / terminal edges), and at what x
    stoich = {}
    for p, nm in enumerate(names):
        _, fixed = X.phase_G(tp, params, phases, nm, B, 0.5, (Tlo + Thi) / 2)
        if fixed is not None:
            stoich[p] = fixed
    line_T = {p: [] for p in stoich}                   # temperatures where each is a hull vertex
    grid = np.full((NT, NX), -1, dtype=int)
    for r in range(NT):
        T = Thi - (Thi - Tlo) * r / (NT - 1)          # row 0 = hottest (top)
        xs, gs, ps = [], [], []
        for p, nm in enumerate(names):
            g0, fixed = X.phase_G(tp, params, phases, nm, B, 1e-6, T)
            if fixed is not None:                      # stoichiometric: single point
                g, _ = X.phase_G(tp, params, phases, nm, B, fixed, T)
                if g is not None and np.isfinite(g):
                    xs.append(fixed); gs.append(g); ps.append(p)
                continue
            for i in range(NS + 1):
                x = min(max(i / NS, 1e-6), 1 - 1e-6)
                g, _ = X.phase_G(tp, params, phases, nm, B, x, T)
                if g is not None and np.isfinite(g):
                    xs.append(x); gs.append(g); ps.append(p)
        order = np.argsort(xs)
        cx, cg, cp = [], [], []
        for i in order:                                # collapse duplicate x to lowest G
            if cx and abs(xs[i] - cx[-1]) < 1e-9:
                if gs[i] < cg[-1]:
                    cg[-1] = gs[i]; cp[-1] = ps[i]
            else:
                cx.append(xs[i]); cg.append(gs[i]); cp.append(ps[i])
        hv = []                                        # monotone-chain lower hull
        for i in range(len(cx)):
            while len(hv) >= 2:
                a, b = hv[-2], hv[-1]
                cross = (cx[b] - cx[a]) * (cg[i] - cg[a]) - (cg[b] - cg[a]) * (cx[i] - cx[a])
                if cross <= 1e-6:
                    hv.pop()
                else:
                    break
            hv.append(i)
        vertex_phases = {cp[i] for i in hv}            # phases present as hull vertices at this T
        for p in stoich:
            if p in vertex_phases:
                line_T[p].append(T)
        for c in range(NX):
            x = c / (NX - 1)
            k = 0
            while k < len(hv) - 1 and cx[hv[k + 1]] < x:
                k += 1
            if k >= len(hv) - 1:
                grid[r, c] = cp[hv[-1]]
            else:
                pa, pb = cp[hv[k]], cp[hv[k + 1]]
                grid[r, c] = pa if pa == pb else -1
    lines = {p: (stoich[p], min(ts), max(ts)) for p, ts in line_T.items() if ts}
    return grid, names, lines


def draw_panel(ax, grid, names, lines, Tlo, Thi, elemA, elemB, title):
    NT, NX = grid.shape
    T_of = lambda r: Thi - (Thi - Tlo) * r / (NT - 1)     # row 0 = top = hottest
    # classic convention: two-phase fields shaded light grey, single-phase fields left white
    rgb = np.ones((NT, NX, 3))
    rgb[grid == -1] = 0.85
    ax.imshow(rgb, extent=[0, 1, Tlo, Thi], aspect="auto", origin="upper", interpolation="nearest")
    # phase boundaries: black where the stable state changes (row 0 at top via origin='upper')
    bnd = np.zeros((NT, NX), bool)
    bnd[:, :-1] |= grid[:, :-1] != grid[:, 1:]
    bnd[:-1, :] |= grid[:-1, :] != grid[1:, :]
    ys, xs = np.where(bnd)
    ax.scatter(xs / (NX - 1), np.array([T_of(y) for y in ys]), s=0.6, c="black", marker="s", linewidths=0)
    # line compounds / terminal edges: drawn from the hull-vertex record, not the grid pixels
    # (a zero-width compound almost never lands on a grid column)
    for p, (xc, tmn, tmx) in lines.items():
        edge = xc > 0.999 or xc < 0.001
        ax.plot([xc, xc], [tmn, tmx], color="black", lw=(0.9 if edge else 1.5))
        if not edge:
            ax.text(xc + 0.02, 0.5 * (tmn + tmx), names[p], rotation=90, ha="left", va="center", fontsize=8)
        elif xc > 0.999:
            ax.text(0.975, 0.5 * (tmn + tmx), names[p], rotation=90, ha="right", va="center", fontsize=8)
    # labels for solution phases at the centroid of their single-phase area
    for p, nm in enumerate(names):
        if p in lines:
            continue
        yy, xx = np.where(grid == p)
        if len(xx) < 0.02 * NT * NX:
            continue
        ax.text(xx.mean() / (NX - 1), T_of(int(yy.mean())), nm, ha="center", va="center", fontsize=8.5,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.75))
    ax.set_xlabel(f"x({elemB})")
    ax.set_ylabel("Temperature (K)")
    ax.set_xlim(0, 1); ax.set_ylim(Tlo, Thi)
    ax.set_title(title, fontsize=11)
    for sp in ax.spines.values():
        sp.set_linewidth(0.8)
    ax.tick_params(labelsize=9)


def main():
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(9.4, 4.2))
    gA, nA, lA = region_grid(ROOT / "data" / "xtdb" / "AlC.xtdb", "C", 300, 3000)
    draw_panel(axA, gA, nA, lA, 300, 3000, "Al", "C", "(a)  Al–C, third generation")
    gB, nB, lB = region_grid(ROOT / "web" / "PbSn.xtdb", "SN", 300, 620)
    draw_panel(axB, gB, nB, lB, 300, 620, "Pb", "Sn", "(b)  Pb–Sn, classic in XTDB")
    fig.tight_layout()
    out = HERE / "fig10_xtdb.png"
    fig.savefig(out, dpi=600, facecolor="white")
    print("fig10_xtdb.png written", out.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
