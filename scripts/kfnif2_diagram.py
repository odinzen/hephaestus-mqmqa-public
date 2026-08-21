#!/usr/bin/env python
"""KF-NiF2 pseudo-binary phase diagram from the Hephaestus MQMQA engine.

The liquidus is computed entirely by this engine (the LIQUID2 MQMQA solution plus
the database's stoichiometric condensed phases, resolved by a lower convex hull on
the KF-NiF2 join) and validated against pycalphad as an independent oracle.

What actually reaches the hull in the KF-NIF2_switched database is narrow: LIQUID2,
NiF2 solid (NIF2_S1) below its melting point, and NiF2 liquid (NIF2_L1) above it.
The KF-rich and intermediate solids (KF_S1, NIKF3, NIK2F4) never become stable on
this join, so they appear only as metastable composition markers. The diagram is
therefore a single NiF2 liquidus, i.e. the solubility limit of NiF2 in the LIQUID2
solution, closing at the NiF2 melting invariant near 1627 K.

Two numerical points matter for a clean liquidus:
  - The reference SLSQP solver in equilibrium.py lands on slightly different local
    minima from a single fixed start, which injects a few kJ of composition noise.
    A short multi-start (uniform + previous-composition + random) and keeping the
    lowest feasible energy removes it, giving a smooth G(xi) curve.
  - The dilute liquidus sits where the LIQUID2 curve first splits off a tie-line to
    the far NiF2 point. That boundary is read by classifying the assemblage at each
    bulk xi (lower convex hull) and bisecting in xi, which is well conditioned,
    rather than by extracting the tangent point to the distant xi=1 vertex.
"""

import os

import numpy as np
from scipy.optimize import minimize
from scipy.interpolate import RectBivariateSpline

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import mqmqa
from mqmqa.equilibrium import build_inputs, gibbs_per_quad, element_moles, _lower_hull

DB_PATH = "C:/Users/busta/Code/pycalphad/pycalphad/tests/databases/KF-NIF2_switched.dat"
PHASE = "LIQUID2"
COMPONENTS = ["K", "NI", "F"]
OUT_PNG = "web/kfnif2_diagram.png"

# Endmembers of the join and the map xi (mol fraction NiF2) -> element amounts.
# Along the join a "salt formula unit" is (1-xi) KF + xi NiF2, with 2+xi atoms.
def join_target(xi):
    return {"K": 1.0 - xi, "NI": xi, "F": 1.0 + xi}

def atoms_per_salt(xi):
    return (1.0 - xi) * 2.0 + xi * 3.0

# Discrete (fixed-composition) phases on the join, as
# name -> (xi, stoich-key, salt-formula-units per formula, kind).
DISCRETE = {
    "KF_S1(S)":    (0.0,       "KF_S1(S)",    1, "solid"),
    "NIF2_S1(S)":  (1.0,       "NIF2_S1(S)",  1, "solid"),
    "NIKF3_S1(S)": (0.5,       "NIKF3_S1(S)", 2, "solid"),
    "NIK2F4_S1(S)":(1.0 / 3.0, "NIK2F4_S1(S)",3, "solid"),
    "KF_L1(LIQ)":  (0.0,       "KF_L1(LIQ)",  1, "liquid"),
    "NIF2_L1(LIQ)":(1.0,       "NIF2_L1(LIQ)",1, "liquid"),
}


def discrete_gibbs(db, sidx, T):
    """Per-salt-formula Gibbs energy of every discrete phase at T."""
    out = {}
    for name, (xi, key, units, kind) in DISCRETE.items():
        out[name] = (xi, db.stoich_gibbs(sidx[key], T) / units, kind)
    return out


def solve_liquid(inp, xi, extra=None, nrand=2, seed=0):
    """Minimum molar Gibbs energy of LIQUID2 at composition xi on the join.

    Returns (G_per_atom, X) or (None, None) if no start met the composition
    constraint. The multi-start guards against SLSQP settling on a higher local
    minimum, which is what makes the raw curve noisy.
    """
    tg = join_target(xi)
    tot = sum(tg.values())
    tg = {k: v / tot for k, v in tg.items()}
    els = sorted(tg)
    n = len(inp["quads"])

    def resid(X):
        m = element_moles(inp, X)
        t = sum(m.values())
        return [m.get(e, 0.0) / t - tg[e] for e in els[:-1]]

    cons = [{"type": "eq", "fun": lambda X: sum(X) - 1.0},
            {"type": "eq", "fun": resid}]
    rng = np.random.default_rng(seed)
    starts = [np.full(n, 1.0 / n)]
    if extra is not None:
        starts.append(extra)
    starts += [rng.dirichlet(np.ones(n)) for _ in range(nrand)]

    best_g, best_x = None, None
    for x0 in starts:
        r = minimize(lambda X: gibbs_per_quad(inp, X), x0, method="SLSQP",
                     bounds=[(1e-12, 1.0)] * n, constraints=cons,
                     options={"ftol": 1e-12, "maxiter": 400})
        m = element_moles(inp, r.x)
        t = sum(m.values())
        err = max(abs(m.get(e, 0.0) / t - tg[e]) for e in els)
        if err < 1e-7:
            g = gibbs_per_quad(inp, r.x) / t
            if best_g is None or g < best_g:
                best_g, best_x = g, r.x
    return best_g, best_x


def precompute_liquid(db, phase, xi_grid, T_grid):
    """One multi-start minimization per (xi, T) node. Sweeping xi ascending and
    feeding the previous solution as an extra start keeps neighbouring nodes on the
    same branch, so the surface is smooth."""
    G = np.zeros((len(xi_grid), len(T_grid)))
    for j, T in enumerate(T_grid):
        inp = build_inputs(db, phase, float(T), components=COMPONENTS)
        prev = None
        for i, xi in enumerate(xi_grid):
            g, prev = solve_liquid(inp, float(xi), extra=prev)
            if g is None:  # keep the surface finite; nodes this deep are unused
                g = G[i - 1, j] if i else 0.0
            G[i, j] = g
        print(f"  T={T:6.1f} K done ({j + 1}/{len(T_grid)})", flush=True)
    return G


class Liquidus:
    """Liquidus (NiF2 solubility boundary) from the precomputed LIQUID2 surface.

    The LIQUID2 energy is carried per salt formula so it shares a basis with the
    discrete phases; the stable assemblage at a bulk xi is the lower convex hull of
    the liquid curve plus the discrete points.
    """

    def __init__(self, db, sidx, xi_grid, T_grid, G_atom):
        self.db = db
        self.sidx = sidx
        self.xi_grid = xi_grid
        G_salt = G_atom * atoms_per_salt(xi_grid)[:, None]
        self.spl = RectBivariateSpline(xi_grid, T_grid, G_salt, kx=3, ky=3, s=0)
        self.xi_lo = float(xi_grid[0])
        self.xi_hi = float(xi_grid[-1])

    def liquid_salt(self, xi, T):
        return float(self.spl(xi, T))

    def hull(self, T):
        u = np.linspace(self.xi_lo, self.xi_hi, 400)
        g = self.spl(u, T).ravel()
        pts = [(float(x), float(gg), ("LIQUID2", float(x))) for x, gg in zip(u, g)]
        for name, (xi, gsalt, _kind) in discrete_gibbs(self.db, self.sidx, T).items():
            pts.append((xi, gsalt, (name, xi)))
        return _lower_hull(pts)

    def assemblage(self, xi, T):
        """Stable phases and molar Gibbs energy (per mole of atoms) at bulk xi."""
        h = self.hull(T)
        hx = [v[0] for v in h]
        k = min(max(int(np.searchsorted(hx, xi)), 1), len(h) - 1)
        left, right = h[k - 1], h[k]
        g_salt = left[1] + (right[1] - left[1]) * (xi - left[0]) / (right[0] - left[0])
        gm = g_salt / atoms_per_salt(xi)
        if left[2][0] == right[2][0] or abs(right[0] - left[0]) < 1e-9:
            return [left[2][0]], gm
        return [left[2][0], right[2][0]], gm

    def is_two_phase(self, xi, T):
        return len(self.assemblage(xi, T)[0]) > 1

    def xi_at(self, T):
        """Liquidus composition at T by bisection on the assemblage classifier."""
        lo, hi = self.xi_lo + 1e-3, self.xi_hi
        if not self.is_two_phase(hi, T):
            return np.nan
        if self.is_two_phase(lo, T):
            return lo
        for _ in range(40):
            m = 0.5 * (lo + hi)
            if self.is_two_phase(m, T):
                hi = m
            else:
                lo = m
        return 0.5 * (lo + hi)

    def T_at(self, xi, T_lo, T_hi):
        """Liquidus temperature at fixed xi by bisection in T.

        At fixed xi the LIQUID2 solution is stable above the liquidus and two-phase
        below it, so the transition in T is monotone and well conditioned. This is
        the smooth-boundary route the coarse-grid-plus-contour approach fails at.
        Returns None if xi stays single-phase (below the liquidus foot) or two-phase
        (its liquidus lies above T_hi) across the whole bracket.
        """
        if not self.is_two_phase(xi, T_lo):
            return None
        if self.is_two_phase(xi, T_hi):
            return None
        for _ in range(46):
            m = 0.5 * (T_lo + T_hi)
            if self.is_two_phase(xi, m):
                T_lo = m
            else:
                T_hi = m
        return 0.5 * (T_lo + T_hi)


def nif2_melting(db, sidx, lo=1400.0, hi=1800.0):
    """Temperature where NiF2 solid and NiF2 liquid share a Gibbs energy."""
    for _ in range(60):
        m = 0.5 * (lo + hi)
        s = db.stoich_gibbs(sidx["NIF2_S1(S)"], m)
        l = db.stoich_gibbs(sidx["NIF2_L1(LIQ)"], m)
        if s < l:
            lo = m
        else:
            hi = m
    return 0.5 * (lo + hi)


def validate(db, sidx, liq, points):
    """Compare engine assemblage and GM against pycalphad at chosen points."""
    import warnings
    warnings.filterwarnings("ignore")
    from pycalphad import Database, equilibrium, variables as v

    dbf = Database(DB_PATH)
    phases = list(dbf.phases.keys())
    rows = []
    for xi, T in points:
        eng_phases, eng_gm = liq.assemblage(xi, T)
        xni = xi / (2.0 + xi)
        xf = (1.0 + xi) / (2.0 + xi)
        eq = equilibrium(dbf, ["K", "NI", "F", "VA"], phases,
                         {v.T: T, v.P: 1e5, v.N: 1, v.X("NI"): xni, v.X("F"): xf})
        pyc_phases = sorted({str(p) for p in np.asarray(eq.Phase.values).ravel() if p})
        pyc_gm = float(np.asarray(eq.GM.values).ravel()[0])
        rows.append(dict(xi=xi, T=T,
                         eng_phases=sorted(eng_phases), eng_gm=eng_gm,
                         pyc_phases=pyc_phases, pyc_gm=pyc_gm,
                         d_gm=eng_gm - pyc_gm))
    return rows


def phase_key(names):
    """Compact label mapping engine phase names to diagram phases."""
    s = set(names)
    if s == {"LIQUID2"}:
        return "L"
    if "NIF2_S1(S)" in s:
        return "L+NiF2(s)"
    if "NIF2_L1(LIQ)" in s:
        return "L+NiF2(liq)"
    return "+".join(sorted(s))


def make_figure(liq, T_melt, T_grid, val_points, out_png):
    Tmin, Tmax = 450.0, 1700.0
    Tline = np.linspace(Tmin, Tmax, 260)
    xiL = np.array([liq.xi_at(T) for T in Tline])
    good = np.isfinite(xiL)
    xL_pct = xiL * 100.0

    fig, ax = plt.subplots(figsize=(7.2, 5.4))

    # Region shading (greyscale-friendly, light).
    solidus_pct = liq.xi_at(T_melt) * 100.0
    # single-phase LIQUID2 to the left of the liquidus
    ax.fill_betweenx(Tline[good], 0.0, xL_pct[good], color="0.93", zorder=0)
    # two-phase fields to the right, split by the NiF2 melting invariant
    Tb = Tline[good]
    xr = xL_pct[good]
    below = Tb <= T_melt
    ax.fill_betweenx(Tb[below], xr[below], 100.0, color="0.82", zorder=0)
    ax.fill_betweenx(Tb[~below], xr[~below], 100.0, color="0.72", zorder=0)

    # Liquidus and the NiF2 melting invariant.
    ax.plot(xL_pct[good], Tline[good], color="black", lw=2.0, zorder=4,
            label="NiF2 liquidus (engine)")
    ax.hlines(T_melt, solidus_pct, 100.0, color="black", lw=1.4, ls="--", zorder=4,
              label=f"NiF2 melting invariant, {T_melt:.0f} K")
    ax.plot([100.0], [T_melt], marker="o", ms=6, mfc="white", mec="black",
            mew=1.4, zorder=5)

    # Metastable compound compositions (never on the hull in this database).
    for name, x in [("KF", 0.0), ("NiK2F4", 100.0 / 3.0), ("NiKF3", 50.0)]:
        if 0.0 < x < 100.0:
            ax.axvline(x, color="0.5", ls=":", lw=0.9, zorder=1)
        ax.text(x, Tmax - 30, name, rotation=90, ha="right", va="top",
                fontsize=8, color="0.35")

    # Validation markers.
    vx = [xi * 100.0 for xi, _ in val_points]
    vy = [T for _, T in val_points]
    ax.plot(vx, vy, linestyle="none", marker="s", ms=5, mfc="none",
            mec="black", mew=1.1, zorder=6, label="pycalphad validation points")

    # Region labels.
    ax.text(2.5, 1200, "LIQUID2", fontsize=10, rotation=90, va="center", color="0.15")
    ax.text(55, 1050, "LIQUID2 + NiF2(s)", fontsize=10, ha="center", color="0.15")
    ax.text(55, 1665, "LIQUID2 + NiF2(liq)", fontsize=9.5, ha="center", color="0.15")

    ax.set_xlim(0, 100)
    ax.set_ylim(Tmin, Tmax)
    ax.set_xlabel("Composition (mol% NiF2)")
    ax.set_ylabel("Temperature (K)")
    ax.set_title("KF-NiF2 Pseudo-Binary Phase Diagram")
    ax.text(0.0, Tmin - 42, "KF", ha="center", va="top", fontsize=9)
    ax.text(100.0, Tmin - 42, "NiF2", ha="center", va="top", fontsize=9)
    ax.legend(loc="center right", fontsize=8, framealpha=0.9)
    ax.grid(True, color="0.9", lw=0.6)
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def main():
    db = mqmqa.Database.read(DB_PATH)
    sidx = {n: i for i, n in enumerate(db.stoich)}
    phase = db.phase_index(PHASE)

    xi_grid = np.linspace(0.003, 0.16, 26)
    T_grid = np.linspace(450.0, 1700.0, 22)
    cache = os.environ.get("KFNIF2_CACHE")
    if cache and os.path.exists(cache):
        print(f"loading cached LIQUID2 surface from {cache}")
        data = np.load(cache)
        xi_grid, T_grid, G_atom = data["xi"], data["T"], data["G"]
    else:
        print(f"precomputing LIQUID2 on {len(xi_grid)}x{len(T_grid)} grid ...")
        G_atom = precompute_liquid(db, phase, xi_grid, T_grid)
        if cache:
            np.savez(cache, xi=xi_grid, T=T_grid, G=G_atom)
            print(f"cached surface to {cache}")

    liq = Liquidus(db, sidx, xi_grid, T_grid, G_atom)
    T_melt = nif2_melting(db, sidx)
    print(f"engine NiF2 melting invariant (NIF2_S1 = NIF2_L1): {T_melt:.2f} K")

    # Liquidus smoothness check against pycalphad reference compositions.
    ref = {500: 0.0379, 700: 0.0492, 900: 0.0581, 1100: 0.0650,
           1300: 0.0704, 1500: 0.0745}
    print("\nliquidus xi (mol fraction NiF2): engine vs pycalphad")
    x_prev = None
    monotone = True
    for T in sorted(ref):
        xe = liq.xi_at(T)
        print(f"  T={T:5.0f}  engine={xe:.4f}  pycalphad={ref[T]:.4f}  d={xe-ref[T]:+.4f}")
        if x_prev is not None and xe < x_prev - 1e-4:
            monotone = False
        x_prev = xe
    print(f"  liquidus monotonic in T: {monotone}")

    # Validation points: single-phase, two solid two-phase, one liquid two-phase.
    val_points = [(0.03, 900.0), (0.10, 900.0), (0.20, 1300.0),
                  (0.50, 1500.0), (0.50, 1660.0)]
    rows = validate(db, sidx, liq, val_points)
    print("\nvalidation (GM in J per mole of atoms):")
    for r in rows:
        ok = phase_key(r["eng_phases"]) == phase_key(r["pyc_phases"])
        print(f"  xi={r['xi']:.3f} T={r['T']:.0f}K")
        print(f"    engine   : {r['eng_phases']}  GM={r['eng_gm']:.1f}")
        print(f"    pycalphad: {r['pyc_phases']}  GM={r['pyc_gm']:.1f}")
        print(f"    assemblage match={ok}  dGM={r['d_gm']:+.1f} "
              f"({100*r['d_gm']/r['pyc_gm']:+.3f}%)")

    make_figure(liq, T_melt, T_grid, val_points, OUT_PNG)
    print(f"\nsaved {OUT_PNG}")


if __name__ == "__main__":
    main()
