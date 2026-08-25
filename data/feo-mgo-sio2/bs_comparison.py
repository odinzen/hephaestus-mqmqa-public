"""Compare our FeO-MgO-SiO2 liquidus surface with Bowen & Schairer 1935 Fig. 6.

Two panels:
  (left)  our primary-phase fields + liquidus isotherms, converted from cation mole fraction
          to WEIGHT PERCENT (their axis) and drawn in their orientation (SiO2 apex, MgO left,
          FeO right);
  (right) our liquidus isotherms registered directly onto their scanned Fig. 6, so isotherm
          positions can be read against their measured contours.

Isotherms are computed DIRECTLY, one temperature at a time: at a fixed T the liquidus isotherm
is the boundary of the single-phase-liquid field, i.e. the contour where the equilibrium liquid
phase-fraction drops below one. That is exact (no temperature quantization) and inherently
smooth, unlike contouring a coarse temperature-descent field. Levels are chosen to MATCH Bowen &
Schairer's isotherms, which are in degC: 1200-1700 degC = 1473-1973 K, so the same contour can be
read directly against theirs.

The Fig. 6 scan is page index 9 of the trove PDF (odinzen_assessment_workspace, gitignored). The
triangle vertices below were detected from the scan (corner-dot centroids; validated by checking
that the marked compounds Fe2SiO4/Mg2SiO4/MgSiO3 map onto their labelled points).
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PROJ_NPZ = HERE / "_liquidus_projection.npz"      # primary-phase fields (temperature descent)
ISO_NPZ = HERE / "_isotherm_fields.npz"           # liquid-fraction fields at the matched levels

# oxide molar masses (g/mol) for the cation-fraction -> weight-percent conversion
M = {"FeO": 71.844, "MgO": 40.304, "SiO2": 60.083}

# Isotherm levels, chosen to coincide with Bowen & Schairer's degC contours.
LEVELS_C = [1200, 1300, 1400, 1500, 1600, 1700]

# Triangle vertices in the dpi=300 scan (pixels), from corner-dot centroids.
V_SIO2 = np.array([962.7, 665.5])
V_MGO = np.array([372.9, 1715.0])
V_FEO = np.array([1538.6, 1711.9])


def levels_K():
    return [c + 273.15 for c in LEVELS_C]


def to_weight(x_fe, x_si):
    """Cation fractions (x_Fe, x_Si; x_Mg = 1-x_Fe-x_Si) -> oxide weight fractions.
    One cation per oxide, so oxide moles equal cation moles."""
    x_fe = np.asarray(x_fe); x_si = np.asarray(x_si)
    x_mg = 1.0 - x_fe - x_si
    m = x_fe * M["FeO"] + x_mg * M["MgO"] + x_si * M["SiO2"]
    return x_fe * M["FeO"] / m, x_mg * M["MgO"] / m, x_si * M["SiO2"] / m


def _tri_xy(w_feo, w_mgo, w_sio2):
    """Weight-fraction barycentric -> Cartesian, SiO2 apex, MgO left, FeO right (unit triangle)."""
    X = w_feo * 1.0 + w_mgo * 0.0 + w_sio2 * 0.5
    Y = w_sio2 * (np.sqrt(3) / 2)
    return X, Y


def _to_px(w_feo, w_mgo, w_sio2):
    """Weight-fraction barycentric -> scan pixel, using the detected triangle vertices."""
    return (np.outer(w_mgo, V_MGO) + np.outer(w_feo, V_FEO) + np.outer(w_sio2, V_SIO2))


def _arclen(xy):
    return float(np.sum(np.hypot(np.diff(xy[:, 0]), np.diff(xy[:, 1]))))


def _interior_runs(xy, edge_eps=0.014):
    """Split a contour polyline (cation x_fe, x_si) into maximal runs of INTERIOR vertices,
    dropping vertices that lie on a composition-triangle edge (min barycentric coord < eps,
    i.e. near x_Fe=0, x_Si=0, or x_Mg=1-x_Fe-x_Si=0). The interior runs are the liquidus arcs;
    the dropped edge-hugging segments are just the liquid field reaching a binary join."""
    x_fe, x_si = xy[:, 0], xy[:, 1]
    interior = np.minimum.reduce([x_fe, x_si, 1.0 - x_fe - x_si]) > edge_eps
    runs, cur = [], []
    for k, ok in enumerate(interior):
        if ok:
            cur.append(xy[k])
        elif cur:
            runs.append(np.array(cur)); cur = []
    if cur:
        runs.append(np.array(cur))
    return [r for r in runs if len(r) >= 4]


def _smooth_polyline(xy, smooth=0.0025):
    """Smoothing-spline resample of a contour polyline. The liquidus surface is smooth within
    each primary-phase field, so the grid-scale staircase of the raw frac=1 boundary is a
    discretization artifact; a spline with a small smoothing budget removes it without moving
    the curve. `smooth` is the total allowed squared deviation (cation-fraction units)."""
    from scipy.interpolate import splprep, splev
    xy = np.asarray(xy, float)
    if len(xy) < 6:
        return xy
    # drop consecutive duplicate points (splprep needs strictly advancing parameter)
    keep = np.r_[True, (np.abs(np.diff(xy, axis=0)).sum(1) > 1e-9)]
    xy = xy[keep]
    if len(xy) < 6:
        return xy
    try:
        tck, _ = splprep([xy[:, 0], xy[:, 1]], s=smooth * len(xy), k=3)
    except Exception:
        return xy
    u = np.linspace(0, 1, max(60, len(xy)))
    x, y = splev(u, tck)
    return np.column_stack([x, y])


def compute_isotherm_fields(ngrid=150, nsamp=9000):
    """Build the equilibrium liquid phase-fraction on a fine cation grid at each matched level
    and cache it. The liquidus isotherm at level T is the 1.0 contour of this field."""
    spec = importlib.util.spec_from_file_location("ternary_diagram", HERE / "ternary_diagram.py")
    td = importlib.util.module_from_spec(spec); spec.loader.exec_module(td)
    sys.path.insert(0, str(HERE.parents[1] / "python"))
    from mqmqa import ternary as tern

    comps = []
    for i in range(ngrid + 1):
        for j in range(ngrid + 1 - i):
            xfe, xsi = i / ngrid, j / ngrid
            if xfe + xsi <= 1.0:
                comps.append((xfe, xsi))
    comps = np.array(comps)

    fields = {}
    for c, Tk in zip(LEVELS_C, levels_K()):
        pts, facets = td.build(Tk, nsamp=nsamp)
        frac = np.full(len(comps), np.nan)
        for k, (xfe, xsi) in enumerate(comps):
            a = tern.assemblage(pts, facets, xfe, xsi)
            if a is None:
                continue
            frac[k] = sum(amt for ph, amt, xf, xs in a if ph == "LIQUID")
        fields[f"f_{c}"] = frac
        n_liq = int(np.nansum(frac > 0.9995))
        print(f"  isotherm {c} degC ({Tk:.0f} K): {n_liq}/{len(comps)} fully-liquid pts")

    np.savez(ISO_NPZ, comps=comps, levels_C=np.array(LEVELS_C), **fields)
    print(f"wrote {ISO_NPZ}")
    return ISO_NPZ


def _isotherm_segments(level_frac_contour=0.9995):
    """Extract each isotherm as smoothed polylines in cation (x_fe, x_si) space from the cached
    liquid-fraction fields."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    d = np.load(ISO_NPZ)
    comps = d["comps"]
    out = {}
    fig = plt.figure()
    ax = fig.add_subplot(111)
    for c in LEVELS_C:
        frac = d[f"f_{c}"]
        m = np.isfinite(frac)
        if m.sum() < 10 or (frac[m] > level_frac_contour).sum() < 8:
            out[c] = []
            continue
        cs = ax.tricontour(comps[m, 0], comps[m, 1], frac[m], levels=[level_frac_contour])
        arcs = []
        for s in cs.allsegs[0]:
            # a frac=1 contour bounds the whole single-liquid region; keep only its INTERIOR
            # arcs (the liquidus), dropping the parts that run along the composition-triangle
            # edges (where the liquid field merely reaches a binary join, not a real isotherm)
            for run in _interior_runs(np.asarray(s)):
                if _arclen(run) > 0.2:
                    arcs.append(_smooth_polyline(run))
        out[c] = arcs
    plt.close(fig)
    return out


# isotherm colours (degC): a distinct cool -> warm progression, readable on the grey scan
PALETTE = {1200: "#5b2c9e", 1300: "#1f6fb2", 1400: "#0f9bd7",
           1500: "#2ca030", 1600: "#e2661f", 1700: "#c81e2c"}


def _draw_isos(ax, isos, to_cart, lw=1.5, label=True, label_dx=0.01, fs=7):
    """Draw each isotherm's polylines, mapping cation (x_fe,x_si) through `to_cart`; label the
    longest segment of each level at its silica-ward end (where the isotherms fan apart, rather
    than the FeO corner where they all converge)."""
    for c in LEVELS_C:
        col = PALETTE[c]
        for seg in isos.get(c, []):
            X, Y = to_cart(seg[:, 0], seg[:, 1])
            ax.plot(X, Y, color=col, lw=lw, solid_capstyle="round")
        if label and isos.get(c):
            seg = max(isos[c], key=len)
            k = int(np.argmin(seg[:, 0]))  # smallest x_Fe = silica/MgO-ward, spread-apart end
            X, Y = to_cart(seg[:, 0], seg[:, 1])
            ax.text(X[k] - label_dx, Y[k], f"{c}", color=col, fontsize=fs, va="center",
                    ha="right", fontweight="bold", clip_on=True)


def main(bs_fig=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    isos = _isotherm_segments()

    ncol = 2 if bs_fig else 1
    fig, axes = plt.subplots(1, ncol, figsize=(6.6 * ncol, 6.2))
    axL = axes[0] if ncol == 2 else axes

    def cart_wt(x_fe, x_si):
        return _tri_xy(*to_weight(x_fe, x_si))

    # left panel: primary-phase fields (weight %) + our isotherms
    if PROJ_NPZ.exists():
        d = np.load(PROJ_NPZ, allow_pickle=True)
        comps = d["comps"]; prim = d["prim"].astype(str)
        greys = [("CRISTOBALITE", 0.93), ("OLIVINE", 0.80), ("ORTHOPYROXENE", 0.60),
                 ("PERICLASE", 0.40), ("WUSTITE", 0.18)]
        for name, gv in greys:
            sel = prim == name
            if sel.any():
                X, Y = cart_wt(comps[sel, 0], comps[sel, 1])
                axL.scatter(X, Y, s=42, marker="s", color=str(gv), edgecolors="none",
                            label=name.title())
    _draw_isos(axL, isos, cart_wt, label_dx=0.012, fs=7)
    for a, b in [((0, 0), (1, 0)), ((1, 0), (0.5, np.sqrt(3) / 2)), ((0.5, np.sqrt(3) / 2), (0, 0))]:
        axL.plot([a[0], b[0]], [a[1], b[1]], color="0.1", lw=1.2)
    axL.text(-0.02, -0.045, "MgO", ha="right"); axL.text(1.02, -0.045, "FeO", ha="left")
    axL.text(0.5, np.sqrt(3) / 2 + 0.03, "SiO$_2$", ha="center")
    axL.set_title("Ours: primary-phase fields + liquidus isotherms (degC)", fontsize=10)
    axL.set_aspect("equal"); axL.axis("off")
    axL.legend(loc="upper left", fontsize=7, frameon=False, title="Primary phase")

    if bs_fig:
        import matplotlib.image as mpimg
        im = mpimg.imread(bs_fig)
        axR = axes[1]
        axR.imshow(im, cmap="gray")

        def cart_px(x_fe, x_si):
            px = _to_px(*to_weight(x_fe, x_si))
            return px[:, 0], px[:, 1]

        _draw_isos(axR, isos, cart_px, lw=1.4, label_dx=9, fs=7.5)
        axR.set_xlim(300, 1620); axR.set_ylim(1780, 600)
        axR.set_title("Our isotherms (coloured, degC) on Bowen-Schairer Fig. 6 (black)",
                      fontsize=10)
        axR.axis("off")

    fig.tight_layout()
    out = HERE / "bs_comparison.png"
    fig.savefig(out, dpi=170)
    print(f"wrote {out}")
    return out


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "compute":
        compute_isotherm_fields()
    else:
        bs = sys.argv[1] if len(sys.argv) > 1 else None
        main(bs)
