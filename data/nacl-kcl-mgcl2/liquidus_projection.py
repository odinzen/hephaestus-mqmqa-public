"""Draw the NaCl-KCl-MgCl2 liquidus-temperature projection from the assembled model.

Over a triangular grid of salt compositions, pycalphad equilibrium (all phases) is
evaluated on a temperature axis; the liquidus is the lowest T at which the assemblage is
fully liquid. The map is coloured by that temperature, with the deep eutectic valley on
the MgCl2-KCl side and the Mohan 2018 measured eutectic marked.
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.tri as mtri

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))
_spec = importlib.util.spec_from_file_location("nkm_build", HERE / "build_dat.py")
bd = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(bd)

LIQ = "NACL-KCL-MGCL2-LIQUID"
TGRID = np.arange(600.0, 820.0, 5.0)


def bary(xk, xmg):
    """Corner order: NaCl (0,0), KCl (1,0), MgCl2 apex (0.5, sqrt3/2)."""
    return xk + 0.5 * xmg, (np.sqrt(3) / 2) * xmg


def main():
    from pycalphad import Database as PDB, equilibrium, variables as v
    dat = HERE / "NaCl-KCl-MgCl2.dat"
    if not dat.exists():
        bd.build()
    pdb = PDB(str(dat))

    pts, temps = [], []
    step = 0.05
    grid = np.arange(step, 1.0, step)
    for xna in grid:
        for xk in grid:
            xmg = 1.0 - xna - xk
            if xmg < step / 2:
                continue
            el = {"NA": xna, "K": xk, "MG": xmg, "CL": xna + xk + 2 * xmg}
            tot = sum(el.values())
            r = equilibrium(pdb, ["NA", "K", "MG", "CL"], list(pdb.phases.keys()),
                            {v.T: TGRID, v.P: 101325, v.N: 1,
                             v.X("NA"): el["NA"] / tot, v.X("K"): el["K"] / tot,
                             v.X("MG"): el["MG"] / tot})
            T_liq = None
            for i, Tt in enumerate(TGRID):
                ph = set(str(x) for x in r.Phase.isel(T=i).values.ravel() if x)
                if ph == {LIQ}:
                    T_liq = float(Tt)
                    break
            if T_liq is not None:
                pts.append(bary(xk, xmg))
                temps.append(T_liq - 273.15)

    pts = np.array(pts); temps = np.array(temps)
    tri = mtri.Triangulation(pts[:, 0], pts[:, 1])

    fig, ax = plt.subplots(figsize=(6.4, 5.6))
    tcf = ax.tricontourf(tri, temps, levels=14, cmap="viridis")
    ax.tricontour(tri, temps, levels=14, colors="k", linewidths=0.3, alpha=0.4)
    cb = fig.colorbar(tcf, ax=ax, shrink=0.8)
    cb.set_label("Liquidus temperature (degC)")

    # measured Mohan eutectic
    m = {"NaCl": 24.5 / 58.442, "KCl": 20.5 / 74.551, "MgCl2": 55.0 / 95.211}
    s = sum(m.values())
    ex, ey = bary(m["KCl"] / s, m["MgCl2"] / s)
    ax.plot(ex, ey, "*", color="#d81010", ms=15, mec="k", mew=0.5, zorder=5)
    ax.annotate("Mohan eutectic\n387 degC (measured)", (ex, ey), xytext=(ex + 0.02, ey - 0.12),
                fontsize=8, color="#d81010")

    for (x, y), lab in [((0, 0), "NaCl"), ((1, 0), "KCl"), (bary(0, 1.0), "MgCl$_2$")]:
        dy = -0.05 if y < 0.1 else 0.03
        ax.text(x, y + dy, lab, ha="center", fontsize=11, weight="bold")
    ax.plot([0, 1, 0.5, 0], [0, 0, np.sqrt(3) / 2, 0], "k-", lw=1)
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("NaCl-KCl-MgCl$_2$ Liquidus Projection (Hephaestus v0.2)", fontsize=11)
    fig.tight_layout()
    out = HERE / "nacl_kcl_mgcl2_liquidus.png"
    fig.savefig(out, dpi=160)
    print("wrote", out, "|", len(temps), "grid points, T range",
          round(temps.min()), "-", round(temps.max()), "degC")


if __name__ == "__main__":
    main()
