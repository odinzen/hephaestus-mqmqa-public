"""FeO-MgO-SiO2 phase diagram via the 2-D global minimizer (mqmqa.ternary).

Assembles the candidate phases - the ternary MQMQA liquid, the olivine and orthopyroxene
CEF solid solutions, and the stoichiometric oxide solids (cristobalite SiO2, periclase MgO,
wustite FeO) - and computes the equilibrium assemblage across the cation simplex by lower
convex hull. All Gibbs energies are per mole of cations; composition is the cation fractions
(x_Fe, x_Si), x_Mg = 1 - x_Fe - x_Si.
"""
import importlib.util
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))

import mqmqa
from mqmqa import ternary as tern


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, HERE.parents[0] / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_feo = _load("bd_feo_td", "feo-sio2/build_dat.py")
_mgo = _load("bd_mgo_td", "mgo-sio2/build_dat.py")

LIQ = HERE / "FeO-MgO-SiO2-liquid.dat"
OLV = HERE.parents[0] / "olivine" / "Olivine-CEF.dat"
OPX = HERE.parents[0] / "olivine-opx" / "Olivine-Opx-CEF.dat"

T0 = 298.15


def _solid_oxide_g(ox, T):
    """Solid oxide Gibbs per formula (= per cation for a mono-cation oxide) from the
    Haas-Fisher Cp = a + b*T + c*T^-2 (no fusion term - this is the solid)."""
    a, b, c = ox["a"], ox["b"], ox["c"]
    H = ox["dHf"] + a * (T - T0) + 0.5 * b * (T * T - T0 * T0) - c * (1.0 / T - 1.0 / T0)
    S = (ox["S298"] + a * math.log(T / T0) + b * (T - T0)
         - 0.5 * c * (1.0 / (T * T) - 1.0 / (T0 * T0)))
    return H - T * S


def build(T, nsamp=12000, n_cef=81, refine=True):
    """Pool all candidate phases at T, build the lower hull, refine the liquid hull vertices,
    and re-hull. Returns (points, facets) ready for `assemblage` queries."""
    ldb = mqmqa.Database.read(str(LIQ))
    lp = ldb.phase_index("FEO-MGO-SIO2-LIQUID")
    cdb = mqmqa.Database.read(str(OLV))
    odb = mqmqa.Database.read(str(OPX))

    liq, inp = tern.liquid_points(ldb, lp, T, nsamp=nsamp)
    solids = tern.cef_line_points(cdb, "OLIVINE", T, x_si_line=1.0 / 3.0, n_cations=3, n=n_cef)
    solids += tern.cef_line_points(odb, "ORTHOPYROXENE", T, x_si_line=1.0 / 2.0, n_cations=4, n=n_cef)
    solids.append(tern.stoich_point("CRISTOBALITE", 0.0, 1.0, _solid_oxide_g(_feo.OXIDES["SiO2"], T)))
    solids.append(tern.stoich_point("PERICLASE", 0.0, 0.0, _solid_oxide_g(_mgo.OXIDES["MgO"], T)))
    solids.append(tern.stoich_point("WUSTITE", 1.0, 0.0, _solid_oxide_g(_feo.OXIDES["FeO"], T)))

    pts = liq + solids
    facets = tern.lower_hull(pts)
    if refine:
        pts = tern.refine_liquid(inp, pts, facets, "LIQUID")
        facets = tern.lower_hull(pts)
    return pts, facets


def equilibrium(T, x_fe, x_si, **kw):
    pts, facets = build(T, **kw)
    return tern.assemblage(pts, facets, x_fe, x_si)


def plot_isotherm(T, nsamp=15000, ngrid=160, out=None):
    """Isothermal section of the FeO-MgO-SiO2 diagram at T: classify every bulk cation
    composition by its stable phase assemblage (from the 2-D hull) and shade the fields on
    the cation ternary (corners FeO, MgO, SiO2)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    pts, facets = build(T, nsamp=nsamp)

    # classify grid points by assemblage; count phases for a greyscale by variance
    keys, xy = [], []
    for i in range(ngrid + 1):
        for j in range(ngrid + 1 - i):
            x_fe = i / ngrid
            x_si = j / ngrid
            if x_fe + x_si > 1.0:
                continue
            a = tern.assemblage(pts, facets, x_fe, x_si)
            if a is None:
                continue
            phases = frozenset(ph for ph, amt, xf, xs in a if amt > 1e-3)
            keys.append(phases)
            xy.append((x_fe, x_si))
    xy = np.array(xy)

    uniq = sorted(set(keys), key=lambda s: (len(s), sorted(s)))
    # greyscale: single-phase light, multi-phase darker; distinct hatch per assemblage label
    shade = {k: 0.92 - 0.5 * (len(k) - 1) / 2 for k in uniq}

    def to_xy(x_fe, x_si):  # cation ternary: SiO2 apex top, FeO left, MgO right
        x_mg = 1 - x_fe - x_si
        X = 0.5 * (2 * x_mg + x_si)
        Y = (np.sqrt(3) / 2) * x_si
        return X, Y

    fig, ax = plt.subplots(figsize=(6.2, 5.6))
    for k in uniq:
        m = np.array([kk == k for kk in keys])
        P = np.array([to_xy(*xy[i]) for i in range(len(xy)) if m[i]])
        if len(P):
            ax.scatter(P[:, 0], P[:, 1], s=8, marker="s",
                       color=str(shade[k]), edgecolors="none",
                       label=" + ".join(sorted(x.title() for x in k)))
    # triangle frame + corner labels
    for a, b in [((0, 0), (1, 0)), ((1, 0), (0.5, np.sqrt(3) / 2)), ((0.5, np.sqrt(3) / 2), (0, 0))]:
        ax.plot([a[0], b[0]], [a[1], b[1]], color="0.1", lw=1.2)
    ax.text(-0.02, -0.04, "FeO", ha="right", fontsize=10)
    ax.text(1.02, -0.04, "MgO", ha="left", fontsize=10)
    ax.text(0.5, np.sqrt(3) / 2 + 0.03, "SiO$_2$", ha="center", fontsize=10)
    ax.set_title(f"FeO-MgO-SiO$_2$ Isothermal Section, {T:.0f} K")
    ax.set_aspect("equal"); ax.axis("off")
    ax.legend(loc="upper right", fontsize=6.5, frameon=False, markerscale=1.5)
    fig.tight_layout()
    out = out or (HERE / f"ternary_isotherm_{int(T)}K.png")
    fig.savefig(out, dpi=150)
    print(f"wrote {out}  ({len(uniq)} distinct assemblages)")
    return out


def liquidus_projection(T_hi=2220.0, T_lo=1440.0, dT=40.0, ngrid=90, nsamp=9000, out=None):
    """Primary-phase-field / liquidus-projection diagram (the Bowen & Schairer 1935 view).
    Sweep temperature downward; the first T at which a bulk composition leaves the
    single-phase liquid field is its liquidus, and the solid it meets there is the primary
    crystallizing phase. Shades each primary-phase field on the cation ternary and draws
    liquidus isotherms."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    comps = []
    for i in range(ngrid + 1):
        for j in range(ngrid + 1 - i):
            xfe, xsi = i / ngrid, j / ngrid
            if xfe + xsi < 1.0:
                comps.append((xfe, xsi))
    liqT = {c: None for c in comps}
    prim = {c: None for c in comps}

    for T in np.arange(T_hi, T_lo - 1e-6, -dT):
        pts, facets = build(T, nsamp=nsamp)
        for c in comps:
            if liqT[c] is not None:
                continue
            a = tern.assemblage(pts, facets, c[0], c[1])
            if a is None:
                continue
            solids = [(ph, amt) for ph, amt, xf, xs in a if ph != "LIQUID" and amt > 1e-3]
            has_liq = any(ph == "LIQUID" and amt > 1e-3 for ph, amt, xf, xs in a)
            if solids:
                liqT[c] = T
                prim[c] = max(solids, key=lambda s: s[1])[0] if not has_liq else solids[0][0]
        print(f"  swept T={T:.0f} K  ({sum(v is not None for v in liqT.values())}/{len(comps)} assigned)")

    # cache the raw fields so the figure can be re-styled without recomputing
    np.savez(HERE / "_liquidus_projection.npz",
             comps=np.array(comps),
             liqT=np.array([liqT[c] if liqT[c] else np.nan for c in comps]),
             prim=np.array([prim[c] or "" for c in comps]))

    def to_xy(xfe, xsi):  # Bowen-Schairer orientation: SiO2 apex, MgO left, FeO right
        return 0.5 * (2 * xfe + xsi), (np.sqrt(3) / 2) * xsi

    prim_phases = sorted({p for p in prim.values() if p})
    shades = {p: 0.88 - 0.6 * k / max(1, len(prim_phases) - 1) for k, p in enumerate(prim_phases)}
    fig, ax = plt.subplots(figsize=(6.4, 5.8))
    for p in prim_phases:
        P = np.array([to_xy(*c) for c in comps if prim[c] == p])
        if len(P):
            ax.scatter(P[:, 0], P[:, 1], s=9, marker="s", color=str(shades[p]),
                       edgecolors="none", label=p.title())
    # liquidus isotherms (contour of liqT over the triangle)
    xs = np.array([to_xy(*c)[0] for c in comps if liqT[c]])
    ys = np.array([to_xy(*c)[1] for c in comps if liqT[c]])
    zs = np.array([liqT[c] for c in comps if liqT[c]])
    try:
        cs = ax.tricontour(xs, ys, zs, levels=np.arange(1500, 2200, 100),
                           colors="0.15", linewidths=0.6)
        ax.clabel(cs, fmt="%.0f", fontsize=6)
    except Exception:
        pass
    for a, b in [((0, 0), (1, 0)), ((1, 0), (0.5, np.sqrt(3) / 2)), ((0.5, np.sqrt(3) / 2), (0, 0))]:
        ax.plot([a[0], b[0]], [a[1], b[1]], color="0.1", lw=1.2)
    ax.text(-0.02, -0.04, "MgO", ha="right", fontsize=10)
    ax.text(1.02, -0.04, "FeO", ha="left", fontsize=10)
    ax.text(0.5, np.sqrt(3) / 2 + 0.03, "SiO$_2$", ha="center", fontsize=10)
    ax.set_title("FeO-MgO-SiO$_2$ Liquidus Projection (primary phase + isotherms/K)")
    ax.set_aspect("equal"); ax.axis("off")
    ax.legend(loc="upper right", fontsize=7, frameon=False, markerscale=1.6)
    fig.tight_layout()
    out = out or (HERE / "ternary_liquidus_projection.png")
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")
    return out


if __name__ == "__main__":
    T = 1800.0
    pts, facets = build(T)
    from collections import defaultdict
    for xfe, xsi, label in [(0.20, 1 / 3, "olivine-join X_Fe=0.3"),
                            (0.30, 0.55, "silica-rich (opx)"),
                            (0.10, 0.10, "MgO-rich (3-phase)")]:
        a = tern.assemblage(pts, facets, xfe, xsi)
        print(f"T={T} bulk(x_Fe={xfe:.2f},x_Si={xsi:.2f}): {label}")
        agg = defaultdict(lambda: [0.0, 0.0, 0.0])
        for ph, amt, xf, xs in (a or []):
            agg[ph][0] += amt; agg[ph][1] += amt * xf; agg[ph][2] += amt * xs
        for ph, (amt, sf, ss) in agg.items():
            print(f"   {ph:13s} amt={amt:.3f} x_Fe={sf/amt:.3f} x_Si={ss/amt:.3f}")
