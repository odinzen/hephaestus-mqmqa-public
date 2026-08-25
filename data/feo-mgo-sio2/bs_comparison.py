"""Compare our FeO-MgO-SiO2 liquidus projection with Bowen & Schairer 1935 Fig. 6.

Two panels:
  (left)  our primary-phase fields + liquidus isotherms, converted from cation mole fraction
          to WEIGHT PERCENT (their axis) and drawn in their orientation (SiO2 apex, MgO left,
          FeO right);
  (right) our liquidus isotherms registered directly onto their scanned Fig. 6, so isotherm
          positions can be read against their measured contours.

Reads the cached projection fields (data/feo-mgo-sio2/_liquidus_projection.npz). The Fig. 6
scan is page index 9 of the trove PDF (odinzen_assessment_workspace, gitignored); the path is
passed in or defaults to None (left panel still renders).
"""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
NPZ = HERE / "_liquidus_projection.npz"

# oxide molar masses (g/mol) for the cation-fraction -> weight-percent conversion
M = {"FeO": 71.844, "MgO": 40.304, "SiO2": 60.083}


def to_weight(x_fe, x_si):
    """Cation fractions (x_Fe, x_Si; x_Mg = 1-x_Fe-x_Si) -> oxide weight fractions.
    One cation per oxide, so oxide moles equal cation moles."""
    x_mg = 1.0 - x_fe - x_si
    m = x_fe * M["FeO"] + x_mg * M["MgO"] + x_si * M["SiO2"]
    return x_fe * M["FeO"] / m, x_mg * M["MgO"] / m, x_si * M["SiO2"] / m  # w_FeO, w_MgO, w_SiO2


def _tri_xy(w_feo, w_mgo, w_sio2):
    """Barycentric -> Cartesian for a unit triangle, SiO2 apex, MgO left, FeO right."""
    X = w_feo * 1.0 + w_mgo * 0.0 + w_sio2 * 0.5
    Y = w_sio2 * (np.sqrt(3) / 2)
    return X, Y


def main(bs_fig=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    d = np.load(NPZ, allow_pickle=True)
    comps = d["comps"]; liqT = d["liqT"]; prim = d["prim"].astype(str)
    m = (prim != "") & np.isfinite(liqT)
    xfe, xsi = comps[m, 0], comps[m, 1]
    T = liqT[m]; ph = prim[m]
    wf, wm, ws = to_weight(xfe, xsi)
    X, Y = _tri_xy(wf, wm, ws)

    ncol = 2 if bs_fig else 1
    fig, axes = plt.subplots(1, ncol, figsize=(6.2 * ncol, 5.8))
    axL = axes[0] if ncol == 2 else axes

    greys = [("CRISTOBALITE", 0.93), ("OLIVINE", 0.80), ("ORTHOPYROXENE", 0.60),
             ("PERICLASE", 0.40), ("WUSTITE", 0.18)]
    for name, g in greys:
        sel = ph == name
        if sel.any():
            axL.scatter(X[sel], Y[sel], s=26, marker="s", color=str(g),
                        edgecolors="none", label=name.title())
    cs = axL.tricontour(X, Y, T, levels=np.arange(1500, 2200, 100), colors="0.05", linewidths=0.7)
    axL.clabel(cs, fmt="%.0f", fontsize=6)
    for a, b in [((0, 0), (1, 0)), ((1, 0), (0.5, np.sqrt(3) / 2)), ((0.5, np.sqrt(3) / 2), (0, 0))]:
        axL.plot([a[0], b[0]], [a[1], b[1]], color="0.1", lw=1.2)
    axL.text(-0.02, -0.045, "MgO", ha="right"); axL.text(1.02, -0.045, "FeO", ha="left")
    axL.text(0.5, np.sqrt(3) / 2 + 0.03, "SiO$_2$", ha="center")
    axL.set_title("Ours (weight %, isotherms in K)", fontsize=10)
    axL.set_aspect("equal"); axL.axis("off")
    axL.legend(loc="upper left", fontsize=7, frameon=False, title="Primary phase")

    if bs_fig:
        # registered overlay: map weight fractions onto their triangle pixels and draw our
        # isotherms on top of the scan. Corner pixels found from the scan (dpi=300 render).
        import matplotlib.image as mpimg
        im = mpimg.imread(bs_fig)
        axR = axes[1]
        axR.imshow(im, cmap="gray")
        MgO = np.array([364.0, 1714.0]); FeO = np.array([1549.0, 1714.0])
        SiO2 = np.array([956.5, 688.0])  # equilateral apex from the base corners

        def to_px(w_feo, w_mgo, w_sio2):
            return w_mgo * MgO + w_feo * FeO + w_sio2 * SiO2

        px = np.array([to_px(a, b, c) for a, b, c in zip(wf, wm, ws)])
        cs2 = axR.tricontour(px[:, 0], px[:, 1], T, levels=np.arange(1500, 2200, 100),
                             colors="red", linewidths=1.0)
        axR.clabel(cs2, fmt="%.0f", fontsize=6, colors="red")
        axR.set_title("Our isotherms (red, K) on Bowen-Schairer Fig. 6", fontsize=10)
        axR.axis("off")

    fig.tight_layout()
    out = HERE / "bs_comparison.png"
    fig.savefig(out, dpi=160)
    print(f"wrote {out}")
    return out


if __name__ == "__main__":
    bs = sys.argv[1] if len(sys.argv) > 1 else None
    main(bs)
