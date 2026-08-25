"""Two-dimensional global equilibrium for a common-anion oxide ternary, by grid + hull.

The engine's per-composition solver minimizes one phase's internal (short-range-order)
degrees of freedom; a phase DIAGRAM needs the global minimum over ALL phases and the whole
composition field. This module does that the robust way (the same idea pycalphad uses):
sample every candidate phase's Gibbs energy across composition, pool the points, and take
their lower convex hull. Each lower-hull facet is an equilibrium tie-triangle (three phases),
edge (two phases) or vertex (one phase); the assemblage at any bulk composition is read off
the facet that covers it.

Basis. All phases here are fixed-valence and iron-saturated (Fe2+, Mg2+, Si4+, one anion O2-),
so oxygen is fixed by charge neutrality identically for every phase. The natural conserved
extensive quantity is therefore the mole of CATIONS: composition = cation fractions
(x_Fe, x_Si) with x_Mg = 1 - x_Fe - x_Si, and the hull coordinate is Gibbs energy per mole of
cations. On that basis the lower convex hull is exactly the equilibrium construction.

A phase contributes a set of `PhasePoint(x_fe, x_si, g, phase, y)` samples (y = the internal
state that produced g, kept for refinement/reporting). Solution phases are sampled over their
composition range; stoichiometric solids are a single point.
"""
from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize
from scipy.spatial import ConvexHull

from mqmqa import equilibrium as eqm


@dataclass
class PhasePoint:
    x_fe: float
    x_si: float
    g: float          # Gibbs energy per mole of cations
    phase: str
    y: object = None  # internal state (quad fractions / site fractions), for reporting


# ----------------------------------------------------------------------------- liquid
def _quad_to_point(inp, X):
    """A quadruplet distribution X -> (x_fe, x_si, g_per_cation) or None if degenerate."""
    els = eqm.element_moles(inp, X)
    ncat = els.get("FE", 0.0) + els.get("MG", 0.0) + els.get("SI", 0.0)
    if ncat <= 0:
        return None
    x_fe = els.get("FE", 0.0) / ncat
    x_si = els.get("SI", 0.0) / ncat
    g = eqm.gibbs_per_quad(inp, X) / ncat
    if not np.isfinite(g) or not np.isfinite(x_fe) or not np.isfinite(x_si):
        return None
    return x_fe, x_si, g


def liquid_points(db, phase, T, nsamp=12000, seed=0):
    """Sample the liquid Gibbs surface (per mole cation) by drawing quadruplet distributions
    directly - fast C evaluations, no per-composition minimization. The lower convex hull of
    the pooled samples is its Gibbs envelope; hull vertices are tightened later by
    `refine_liquid`. Structured draws (pure endmembers, binary edges, and Dirichlet mixes at
    several concentrations) give broad coverage of the cation simplex."""
    p = phase if isinstance(phase, int) else db.phase_index(phase)
    inp = eqm.build_inputs(db, p, T, components=["FE", "MG", "SI", "O"])
    n = len(inp["quads"])
    rng = np.random.default_rng(seed)
    draws = []
    for a in (0.15, 0.4, 1.0, 3.0):          # concentration: corners -> center
        draws.append(rng.dirichlet(np.full(n, a), size=nsamp // 4))
    X = np.vstack(draws)
    # add the pure-quadruplet vertices (each single quad = one ordered state)
    X = np.vstack([X, np.eye(n)])
    pts = []
    for row in X:
        r = _quad_to_point(inp, row)
        if r is not None:
            pts.append(PhasePoint(r[0], r[1], r[2], "LIQUID", row))
    return pts, inp


def refine_liquid(inp, points, facets, phase="LIQUID"):
    """Tighten every LIQUID hull vertex by locally minimizing the liquid Gibbs at its
    composition (a handful of SLSQP solves, warm-started from the sampled state). Returns a
    new point list with the refined liquid points replacing the sampled ones."""
    used = set()
    for tri in facets:
        for idx in tri:
            if points[idx].phase == phase:
                used.add(idx)
    refined = list(points)
    for idx in used:
        pp = points[idx]
        g, X = _liquid_g_at(inp, pp.x_fe, pp.x_si, np.asarray(pp.y, float))
        if np.isfinite(g) and g < pp.g:
            refined[idx] = PhasePoint(pp.x_fe, pp.x_si, g, phase, X)
    return refined


def _liquid_g_at(inp, x_fe, x_si, warm):
    """Minimize the liquid Gibbs (per mole cation) at cation fractions (x_fe, x_si).
    Warm-started from `warm` (the previous grid point's optimum) plus light multi-start;
    returns (g_per_cation, X_opt) or (nan, warm) if infeasible."""
    n = len(inp["quads"])
    x_mg = 1.0 - x_fe - x_si
    if x_mg < -1e-9 or x_fe < -1e-9 or x_si < -1e-9:
        return np.nan, warm
    # cation mole targets (per 1 mole cation): Fe=x_fe, Mg=x_mg, Si=x_si
    order = ["FE", "MG", "SI"]
    tgt = {"FE": x_fe, "MG": x_mg, "SI": x_si}

    def cat_fracs(X):
        els = eqm.element_moles(inp, X)
        ncat = els.get("FE", 0.0) + els.get("MG", 0.0) + els.get("SI", 0.0)
        return {e: els.get(e, 0.0) / ncat for e in order}, ncat

    def resid(X):
        f, _ = cat_fracs(X)
        return [f[e] - tgt[e] for e in order[:-1]]

    cons = [{"type": "eq", "fun": lambda X: sum(X) - 1.0},
            {"type": "eq", "fun": resid}]
    rng = np.random.default_rng(0)
    starts = [warm, np.full(n, 1.0 / n)] + [rng.dirichlet(np.ones(n)) for _ in range(3)]
    best, bestX = None, warm
    for x0 in starts:
        r = minimize(lambda X: eqm.gibbs_per_quad(inp, X), x0, method="SLSQP",
                     bounds=[(1e-12, 1.0)] * n, constraints=cons,
                     options={"ftol": 1e-14, "maxiter": 3000})
        f, ncat = cat_fracs(r.x)
        if max(abs(f[e] - tgt[e]) for e in order) < 1e-7:
            g = eqm.gibbs_per_quad(inp, r.x) / ncat
            if best is None or g < best:
                best, bestX = g, r.x
    return (best if best is not None else np.nan), bestX


# --------------------------------------------------------------------------- CEF lines
def cef_line_points(cdb, phase, T, x_si_line, n_cations, n=61, mg_endmember_shift=None):
    """Sample a CEF (Mg,Fe) solid solution along its fixed-silica line. `x_si_line` is its
    cation silica fraction (olivine 1/3, opx 1/2); `n_cations` the cations per formula the
    cef_gibbs per-formula value divides by. `mg_endmember_shift`, if given, is a callable
    shift(T) added to the Mg endmember reference (contributes shift*y_Mg to the formula
    Gibbs) - used for the enstatite high-T entropy calibration."""
    p = cdb.phase_index(phase) if isinstance(phase, str) else phase
    dmg = mg_endmember_shift(T) if mg_endmember_shift else 0.0
    pts = []
    for xFe in np.linspace(1e-4, 1 - 1e-4, n):
        y = [xFe, 1.0 - xFe, 1.0, 1.0]  # reader order [Fe, Mg], Si, O
        g_formula = cdb.cef_gibbs(p, y, T, per_mole_atoms=False) + dmg * (1.0 - xFe)
        g_cat = g_formula / n_cations
        # cation fractions: metals total (n_cations - n_si), Si = n_si
        n_si = x_si_line * n_cations
        n_metal = n_cations - n_si
        x_fe = n_metal * xFe / n_cations
        pts.append(PhasePoint(x_fe, x_si_line, g_cat, phase if isinstance(phase, str) else "CEF", y))
    return pts


def stoich_point(name, x_fe, x_si, g_per_cation):
    return PhasePoint(x_fe, x_si, g_per_cation, name, None)


# ------------------------------------------------------------------------------- hull
def lower_hull(points):
    """Lower convex hull of the pooled (x_fe, x_si, g) points. Returns the list of lower
    facets as index triples into `points` (each facet is a candidate tie-triangle)."""
    P = np.array([[p.x_fe, p.x_si, p.g] for p in points])
    hull = ConvexHull(P)
    facets = []
    for eq, simplex in zip(hull.equations, hull.simplices):
        # lower hull: outward normal points down in g (eq[2] < 0)
        if eq[2] < -1e-12:
            facets.append(tuple(int(i) for i in simplex))
    return facets


def _bary(P, tri, q):
    """Barycentric coordinates of 2-D point q in triangle tri (indices into P[:, :2])."""
    a, b, c = P[tri[0], :2], P[tri[1], :2], P[tri[2], :2]
    T = np.array([[a[0] - c[0], b[0] - c[0]], [a[1] - c[1], b[1] - c[1]]])
    try:
        l1, l2 = np.linalg.solve(T, q - c)
    except np.linalg.LinAlgError:
        return None
    return np.array([l1, l2, 1.0 - l1 - l2])


def hull_g(points, facets, x_fe, x_si, tol=1e-9):
    """Lower-hull Gibbs energy (per mole cation) at bulk (x_fe, x_si): the covering facet's
    plane evaluated there. This is the equilibrium G the minimizer delivers - well conditioned
    even where the tie-line endpoints themselves are (a flat liquid surface makes the endpoint
    lateral position soft, but the energy is not). Returns nan if outside the sampled domain."""
    P = np.array([[p.x_fe, p.x_si, p.g] for p in points])
    q = np.array([x_fe, x_si])
    for tri in facets:
        w = _bary(P, tri, q)
        if w is not None and (w >= -tol).all():
            return float(sum(wi * P[idx, 2] for wi, idx in zip(w, tri)))
    return float("nan")


def assemblage(points, facets, x_fe, x_si, tol=1e-9):
    """Stable phase assemblage at bulk cation composition (x_fe, x_si): the lower-hull facet
    covering it. Returns [(phase, amount, x_fe_phase, x_si_phase), ...] (amounts = mole
    fraction of cations in each phase), or None if outside the sampled domain."""
    P = np.array([[p.x_fe, p.x_si, p.g] for p in points])
    q = np.array([x_fe, x_si])
    for tri in facets:
        w = _bary(P, tri, q)
        if w is not None and (w >= -tol).all():
            out = []
            for wi, idx in zip(w, tri):
                if wi > 1e-6:
                    p = points[idx]
                    out.append((p.phase, float(wi), p.x_fe, p.x_si))
            # merge duplicate-phase vertices (same solution phase, adjacent samples)
            return out
    return None
