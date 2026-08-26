"""Single-phase MQMQA equilibrium: given a bulk composition and temperature, find
the quadruplet distribution that minimizes the molar Gibbs energy.

The energy is the C core (reference + ideal-mixing + excess); this module adds the
constrained minimization over the quadruplet fractions. It is the Python reference
solver, validated against pycalphad; the browser build ports the same algorithm to C.

The constraints are all linear in the quadruplet fractions X:
  - normalization: sum(X) = 1 (one mole of quadruplets),
  - mass balance: each element's mole fraction matches the target composition.
Charge neutrality is automatic (every quadruplet is neutral). The molar Gibbs energy
per mole of atoms is G_per_quad / n_atoms, where n_atoms is the total moles of cation
and anion species (Poschmann eq 7-8).

scipy is used for the minimization here; it is a reference-solver dependency, not an
engine dependency (the C/WASM engine carries its own minimizer).
"""

import re

import numpy as np
from scipy.optimize import minimize

import mqmqa


def _element(name):
    return re.match(r"[A-Z]+", name).group(0)


def build_inputs(db, phase, T, components=None):
    """Assemble everything the energy routines need for one phase at temperature T.

    components, if given, restricts the model to cations/anions whose element is in
    the set (a subsystem, e.g. only CaO-SiO2 out of a larger slag). Indices are
    remapped to the subsystem so the arrays feed the C routines directly.
    """
    cats = db.cations(phase)
    ans = db.anions(phase)
    if components is not None:
        comp = {c.upper() for c in components}
        cat_keep = [i for i, c in enumerate(cats) if _element(c["name"]) in comp]
        an_keep = [k for k, a in enumerate(ans) if _element(a["name"]) in comp]
    else:
        cat_keep = list(range(len(cats)))
        an_keep = list(range(len(ans)))
    cat_new = {old: new for new, old in enumerate(cat_keep)}
    an_new = {old: new for new, old in enumerate(an_keep)}
    cats = [cats[i] for i in cat_keep]
    ans = [ans[k] for k in an_keep]
    ncat, nan = len(cats), len(ans)
    if ncat == 0 or nan == 0:
        raise ValueError("subsystem has no cations or no anions")

    q_cat = [c["charge"] for c in cats]
    q_an = [a["charge"] for a in ans]

    qca, qcb, qax, qay = mqmqa.enumerate_quadruplets(ncat, nan)
    quads = list(zip(qca, qcb, qax, qay))

    # coordination table, restricted and reindexed to the subsystem
    mz = db.mqmz(phase)
    mzA, mzB, mzX, mzY, mzZ = [], [], [], [], []
    for i in range(len(mz["A"])):
        A, B, X, Y = mz["A"][i], mz["B"][i], mz["X"][i], mz["Y"][i]
        if A in cat_new and B in cat_new and X in an_new and Y in an_new:
            mzA.append(cat_new[A]); mzB.append(cat_new[B])
            mzX.append(an_new[X]); mzY.append(an_new[Y])
            mzZ.extend(mz["Z"][i * 4:i * 4 + 4])

    def Z(is_cat, sp, A, B, X, Y):
        return mqmqa.coordination(is_cat, sp, A, B, X, Y, ncat, nan, q_cat, q_an,
                                  mzA, mzB, mzX, mzY, mzZ)

    Za = [Z(1, A, A, B, X, Y) for A, B, X, Y in quads]
    Zb = [Z(1, B, A, B, X, Y) for A, B, X, Y in quads]
    Zx = [Z(0, X, A, B, X, Y) for A, B, X, Y in quads]
    Zy = [Z(0, Y, A, B, X, Y) for A, B, X, Y in quads]

    # pairs (MQMG), restricted and reindexed
    pr = db.pairs(phase, T)
    pcat, pan, pG, pstoich, pzeta = [], [], [], [], []
    for c, a, g, s, z in zip(pr["cat"], pr["an"], pr["G"], pr["stoich"], pr["zeta"]):
        if c in cat_new and a in an_new:
            pcat.append(cat_new[c]); pan.append(an_new[a])
            pG.append(g); pstoich.append(s); pzeta.append(z)
    Ztab = []
    for pc in pcat:
        for A, B, X, Y in quads:
            Ztab.append(Z(1, pc, A, B, X, Y) if pc in (A, B) else 1.0)
    zeta = [0.0] * (ncat * nan)
    for c, a, z in zip(pcat, pan, pzeta):
        zeta[c * nan + a] = z

    # excess (MQMX), restricted and reindexed
    mx = db.mqmx(phase, T)
    ex = {k: [] for k in ("mix", "code", "A", "B", "X", "Y", "p", "q", "L", "r", "addcat")}
    for i in range(len(mx["A"])):
        A, B, X, Y = mx["A"][i], mx["B"][i], mx["X"][i], mx["Y"][i]
        if A in cat_new and B in cat_new and X in an_new and Y in an_new:
            m = mx.get("addcat", [-1] * len(mx["A"]))[i]
            if m >= 0 and m not in cat_new:
                continue    # ternary constituent absent -> its pair fraction is 0 -> term is 0
            ex["A"].append(cat_new[A]); ex["B"].append(cat_new[B])
            ex["X"].append(an_new[X]); ex["Y"].append(an_new[Y])
            ex["addcat"].append(cat_new[m] if m >= 0 else -1)
            ex["r"].append(mx.get("r", [0.0] * len(mx["A"]))[i])
            for k in ("mix", "code", "p", "q", "L"):
                ex[k].append(mx[k][i])

    return {
        "ncat": ncat, "nan": nan, "quads": quads,
        "qca": qca, "qcb": qcb, "qax": qax, "qay": qay,
        "Za": Za, "Zb": Zb, "Zx": Zx, "Zy": Zy, "Ztab": Ztab, "zeta": zeta,
        "pcat": pcat, "pan": pan, "pG": pG, "pstoich": pstoich,
        "ex": ex, "soln_type": db.is_subq(phase), "T": T,
        "cat_el": [_element(c["name"]) for c in cats],
        "an_el": [_element(a["name"]) for a in ans],
    }


def gibbs_per_quad(inp, X):
    Xl = list(X)
    ex = inp["ex"]
    return (
        mqmqa.reference_energy(inp["qca"], inp["qcb"], inp["qax"], inp["qay"], Xl,
                               inp["pcat"], inp["pan"], inp["pG"], inp["pstoich"], inp["Ztab"])
        + mqmqa.ideal_mixing_energy(inp["T"], inp["ncat"], inp["nan"],
                                    inp["qca"], inp["qcb"], inp["qax"], inp["qay"], Xl,
                                    inp["Za"], inp["Zb"], inp["Zx"], inp["Zy"], inp["zeta"],
                                    inp["soln_type"])
        + mqmqa.excess_energy(inp["ncat"], inp["nan"],
                              inp["qca"], inp["qcb"], inp["qax"], inp["qay"], Xl,
                              inp["Za"], inp["Zb"], inp["Zx"], inp["Zy"],
                              ex["mix"], ex["code"], ex["A"], ex["B"], ex["X"], ex["Y"],
                              ex["p"], ex["q"], ex["L"],
                              ex.get("r"), ex.get("addcat"))
    )


def _species_moles(inp, X):
    nc = np.zeros(inp["ncat"])
    na = np.zeros(inp["nan"])
    for q in range(len(X)):
        nc[inp["qca"][q]] += X[q] / inp["Za"][q]
        nc[inp["qcb"][q]] += X[q] / inp["Zb"][q]
        na[inp["qax"][q]] += X[q] / inp["Zx"][q]
        na[inp["qay"][q]] += X[q] / inp["Zy"][q]
    return nc, na


def element_moles(inp, X):
    nc, na = _species_moles(inp, X)
    els = {}
    for i, e in enumerate(inp["cat_el"]):
        els[e] = els.get(e, 0.0) + nc[i]
    for k, e in enumerate(inp["an_el"]):
        els[e] = els.get(e, 0.0) + na[k]
    return els


def _lower_hull(points):
    """Lower convex hull of (x, g) points, sorted by x. Returns the hull vertices
    as (x, g, payload) in increasing x (monotone chain, keeping the lower side)."""
    pts = sorted(points, key=lambda q: q[0])
    hull = []
    for x, g, tag in pts:
        while len(hull) >= 2:
            (x1, g1, _), (x2, g2, _) = hull[-2], hull[-1]
            if (x2 - x1) * (g - g1) - (g2 - g1) * (x - x1) <= 0:
                hull.pop()
            else:
                break
        hull.append((x, g, tag))
    return hull


def _edge_is_tieline(all_x, xl, xr, eps=1e-9):
    """A lower-hull edge from xl to xr is a genuine two-phase tie-line iff it skips over
    sampled compositions between its endpoints (those interior points lie above the
    chord, so they are metastable). If no sample lies strictly between, the edge simply
    follows a continuous solution-phase curve and the state is single-phase."""
    lo, hi = min(xl, xr), max(xl, xr)
    return any(lo + eps < x < hi - eps for x in all_x)


def binary_hull_equilibrium(phase_points, x_overall, tie_tol=1e-6):
    """General binary multiphase equilibrium by lower convex hull + lever rule.

    phase_points is an iterable of (x, G, phase, comp): x the shared composition
    coordinate (mole fraction of one component, on a consistent extensive basis, e.g.
    per formula unit), G the molar Gibbs energy on that same basis, phase the phase
    name, and comp any tag describing the internal composition (reported back). A
    SOLUTION phase contributes many points (a sampled G(x) curve, whether an MQMQA
    liquid or a CEF solid solution); a STOICHIOMETRIC phase contributes one point.

    The stable state at x_overall is the lower convex hull of all points. Returns the
    assemblage: a single phase, or a two-phase tie-line with each endpoint's phase and
    composition, plus the equilibrium GM (same basis) and the lever-rule fractions.
    A solution phase in a two-phase field reports its equilibrium composition (the tie
    point on its curve); a solution phase unmixing (both endpoints the same phase name,
    different comp) is a miscibility gap / solvus.
    """
    pts = [(float(x), float(g), (phase, comp)) for x, g, phase, comp in phase_points]
    all_x = sorted(p[0] for p in pts)
    hull = _lower_hull(pts)
    hx = [h[0] for h in hull]
    j = int(np.searchsorted(hx, x_overall))
    j = min(max(j, 1), len(hull) - 1)
    left, right = hull[j - 1], hull[j]
    g_at = left[1] + (right[1] - left[1]) * (x_overall - left[0]) / (right[0] - left[0])

    if abs(right[0] - left[0]) < tie_tol or not _edge_is_tieline(all_x, left[0], right[0]):
        # bracketing hull vertices are consecutive samples of one solution phase (or a
        # single point): the stable state is that one phase at the overall composition.
        return {"phases": [left[2][0]], "compositions": [x_overall],
                "fractions": [1.0], "endpoints": [x_overall], "GM": g_at}
    fr = (x_overall - left[0]) / (right[0] - left[0])
    return {"phases": [left[2][0], right[2][0]],
            "compositions": [left[2][1], right[2][1]],
            "fractions": [1 - fr, fr], "endpoints": [left[0], right[0]], "GM": g_at}


def miscibility_conjugates(phase_points, min_span=1e-3):
    """Conjugate compositions of every tie-line on the lower hull (hull edges that span
    a finite composition range). For a single solution phase's G(x) curve this returns
    the solvus binodal - the pair of coexisting compositions - as (x_left, comp_left,
    x_right, comp_right). Empty when the curve is convex (one stable phase everywhere).
    """
    pts = [(float(x), float(g), (phase, comp)) for x, g, phase, comp in phase_points]
    all_x = sorted(p[0] for p in pts)
    hull = _lower_hull(pts)
    out = []
    for a, b in zip(hull, hull[1:]):
        if b[0] - a[0] > min_span and _edge_is_tieline(all_x, a[0], b[0]):
            out.append((a[0], a[2][1], b[0], b[2][1]))
    return out


def multiphase_binary(inp, end0, end1, solids, xi, ngrid=400):
    """Stable phase assemblage along a binary join between two salt endmembers.

    end0, end1 are the endmember element compositions (dict element -> atom count),
    e.g. KF = {"K":1,"F":1} and NiF2 = {"NI":1,"F":2}. xi is the bulk mole fraction
    of end1. solids is a list of (xi_solid, G_per_formula_unit, name), each solid a
    point on the join. The liquid Gibbs energy along the join is computed from the C
    engine via the single-phase solver; the stable state at xi is the lower convex
    hull, a single phase or a two-phase tie-line.

    Returns {phases, fractions, GM} where GM is per mole of atoms, matching the
    convention of equilibrate. Energies are carried per mole of endmember ("salt")
    formula so the hull and lever rule stay in one consistent basis.
    """
    els = sorted(set(end0) | set(end1))

    def join_comp(t):
        return {e: (1 - t) * end0.get(e, 0.0) + t * end1.get(e, 0.0) for e in els}

    def atoms_per_salt(t):
        return sum(join_comp(t).values())

    def liq_g(t):
        comp = join_comp(t)
        return equilibrate(inp, comp)["GM"] * atoms_per_salt(t)

    grid = np.concatenate([np.linspace(1e-3, 0.12, ngrid // 3),
                           np.linspace(0.12, 1 - 1e-3, ngrid - ngrid // 3)])
    points = [(float(t), liq_g(float(t)), ("LIQUID", float(t))) for t in grid]
    for xs, gs, name in solids:
        points.append((xs, gs, (name, xs)))

    hull = _lower_hull(points)
    hx = [h[0] for h in hull]
    j = int(np.searchsorted(hx, xi))
    j = min(max(j, 1), len(hull) - 1)
    left, right = hull[j - 1], hull[j]
    g_at = left[1] + (right[1] - left[1]) * (xi - left[0]) / (right[0] - left[0])

    if abs(right[0] - left[0]) < 1e-9 or left[2][0] == right[2][0]:
        phases = [left[2][0]]
        fractions = [1.0]
    else:
        fr = (xi - left[0]) / (right[0] - left[0])
        phases = [left[2][0], right[2][0]]
        fractions = [1 - fr, fr]
    return {
        "phases": phases,
        "fractions": fractions,
        "endpoints": [left[2][1], right[2][1]],
        "GM": g_at / atoms_per_salt(xi),
    }


def equilibrate(inp, x_target):
    """Minimize G over the quadruplet fractions at fixed composition.

    x_target maps element -> mole fraction (need not be normalized). Returns a dict
    with the equilibrium quadruplet fractions X, molar Gibbs energy GM (J per mole of
    atoms), the resulting element moles, and the optimizer success flag.
    """
    total = sum(x_target.values())
    target = {e.upper(): v / total for e, v in x_target.items()}
    elements = sorted(target)
    n = len(inp["quads"])

    def comp_residual(X):
        els = element_moles(inp, X)
        tot = sum(els.values())
        return [els.get(e, 0.0) / tot - target[e] for e in elements[:-1]]

    cons = [
        {"type": "eq", "fun": lambda X: sum(X) - 1.0},
        {"type": "eq", "fun": comp_residual},
    ]
    x0 = np.full(n, 1.0 / n)
    res = minimize(lambda X: gibbs_per_quad(inp, X), x0, method="SLSQP",
                   bounds=[(1e-12, 1.0)] * n, constraints=cons,
                   options={"ftol": 1e-14, "maxiter": 2000})
    els = element_moles(inp, res.x)
    n_atoms = sum(els.values())

    # Success means the constraints are actually met. SLSQP's own flag is
    # unreliable at boundary solutions (a quadruplet fraction pinned near zero),
    # where it can report failure despite converging to the correct minimum.
    tot = sum(els.values())
    comp_err = max((abs(els.get(e, 0.0) / tot - target[e]) for e in elements), default=0.0)
    converged = comp_err < 1e-7 and abs(sum(res.x) - 1.0) < 1e-9
    return {
        "X": res.x,
        "GM": gibbs_per_quad(inp, res.x) / n_atoms,
        "elements": els,
        "success": converged,
        "comp_error": comp_err,
    }
