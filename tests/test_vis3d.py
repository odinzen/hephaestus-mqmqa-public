"""The 3D module, steps 1 and 2 of docs/VISUALIZATION_3D.md (src/vis3d.c).

Step 1, the deterministic refined liquid: the same input gives the same hull bit for bit;
the refined tie-lines agree with the model's own equilibrium (pycalphad on the committed
combined .dat) to X_TOL whatever the sampling seed; the liquid minimizer reaches the
single-phase minimum pycalphad finds. Step 2, the isothermal section as mesh patches:
one label per triangle, the labels agree with the existing 2D assemblage lookup on the
same candidates, and the phase-field areas converge as the lattice is refined.

X_TOL is the default boundary tolerance of the module (cation mole fraction), 1e-3:
below the width of a pixel on any diagram of the triangle, and well above the ~1e-4
scatter of the converged boundaries between sampling seeds.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

import mqmqa                                           # noqa: E402
from mqmqa import vis3d                                # noqa: E402
from mqmqa._abi import _ffi, _lib                      # noqa: E402

_ffi.cdef("int mqmqa_hull_assemblage_2d(const double *pts, int n, const int *facets, int nf,"
          " double qx, double qy, int *tri_out, double *w_out, double *g_out);", override=True)

X_TOL = 1e-3
FMS = ROOT / "data" / "feo-mgo-sio2" / "FeO-MgO-SiO2-combined.dat"
CAS = ROOT / "web" / "CaO-Al2O3-SiO2.dat"
LIQ = "FEO-MGO-SIO2-LIQUID"
PHASES = [LIQ, "OLIVINE", "ORTHOPYROXENE", "MAGNESIOWUSTITE", "CRISTOBALITE"]


@pytest.fixture(scope="module")
def fms():
    return mqmqa.Database.read(str(FMS))


_hulls = {}


def _hull(db, T, seed=0):
    """Hulls are the expensive part (seconds each); tests share them."""
    key = (id(db), T, seed)
    if key not in _hulls:
        _hulls[key] = vis3d.Hull(db, T, seed=seed)
    return _hulls[key]


def _pyc_equilibrium(T, x_fe, x_si, phases=PHASES):
    """[(phase, x_fe, x_si)] of the model's equilibrium, from pycalphad on the same file."""
    from pycalphad import Database, equilibrium, variables as v
    dbf = _pyc_equilibrium.dbf = getattr(_pyc_equilibrium, "dbf", None) or Database(str(FMS))
    x_mg = 1.0 - x_fe - x_si
    tot = 1.0 + x_fe + x_mg + 2.0 * x_si
    eq = equilibrium(dbf, ["FE", "MG", "SI", "O"], phases,
                     {v.T: T, v.P: 1e5, v.N: 1,
                      v.X("FE"): x_fe / tot, v.X("MG"): x_mg / tot, v.X("SI"): x_si / tot})
    names = np.ravel(eq.Phase.values)
    X = eq.X.values.reshape(len(names), -1)
    NP = np.ravel(eq.NP.values)
    comp = list(eq.component.values)
    out = []
    for name, row, amt in zip(names, X, NP):
        if str(name) in ("", "nan") or amt < 1e-3:
            continue
        d = dict(zip(comp, row))
        ncat = d["FE"] + d["MG"] + d["SI"]
        out.append((str(name), d["FE"] / ncat, d["SI"] / ncat))
    return sorted(out), float(eq.GM.values.squeeze()) * tot


def _mine(h, x_fe, x_si):
    """The hull's assemblage as [(phase, x_fe, x_si)], liquid order x1 = Fe, x2 = Mg, x3 = Si."""
    return sorted((p, 1.0 - x2 - x3, x3) for p, amt, x2, x3 in h.assemblage(1 - x_fe - x_si, x_si)
                  if amt > 1e-3)


# ------------------------------------------------------------------ step 1: the liquid

def test_liquid_minimizer_reaches_the_single_phase_minimum(fms):
    """The minimizer against pycalphad restricted to the liquid, where pycalphad finds one
    liquid. (The Nelder-Mead path behind mqmqa_equilibrate_db is kJ above this minimum in
    FeO-rich, low-silica liquid at 2000 K; that is why the module has its own.)

    The reference is the energy of pycalphad's equilibrium state, recomputed there with
    calculate(), not eq.GM: eq.GM comes from its chemical potentials and was found 1.1 mJ
    below the energy of its own state at x = (0.058, 0.391, 0.551), 1500 K."""
    pytest.importorskip("pycalphad")
    from pycalphad import Database, calculate, equilibrium, variables as v
    dbf = Database(str(FMS))
    rng = np.random.default_rng(4)
    checked = 0
    for T in (1500.0, 2000.0):
        for _ in range(15):
            x = rng.dirichlet([1.0, 1.0, 1.0])
            x_fe, x_mg, x_si = x
            tot = 1.0 + x_fe + x_mg + 2.0 * x_si
            eq = equilibrium(dbf, ["FE", "MG", "SI", "O"], [LIQ],
                             {v.T: T, v.P: 1e5, v.N: 1, v.X("FE"): x_fe / tot,
                              v.X("MG"): x_mg / tot, v.X("SI"): x_si / tot})
            if sum(str(n) not in ("", "nan") for n in np.ravel(eq.Phase.values)) != 1:
                continue        # pycalphad splits it into two liquids: not a single-phase check
            y = np.ravel(eq.Y.values)
            y = y[~np.isnan(y)]
            st = calculate(dbf, ["FE", "MG", "SI", "O"], LIQ, T=T, P=1e5, N=1, points=y[None, :])
            got = [float(st.X.sel(component=e).values.squeeze()) for e in ("FE", "MG", "SI")]
            assert np.allclose(got, [x_fe / tot, x_mg / tot, x_si / tot], atol=1e-10)
            g_pyc = float(st.GM.values.squeeze()) * tot
            g, X = vis3d.liquid_gibbs(fms, LIQ, T, x_mg, x_si)
            assert abs(g - g_pyc) < 1e-3, f"T={T} x={x}: {g} vs pycalphad {g_pyc}"
            assert X.min() > 0.0
            checked += 1
    assert checked >= 20


def test_liquid_on_an_edge_despite_rounding(fms):
    """1 - 0.55 - 0.45 is -5.6e-17 in floating point: the MgO-SiO2 edge, not outside it."""
    g, X = vis3d.liquid_gibbs(fms, LIQ, 1623.26, 0.55, 0.45)
    assert np.isfinite(g) and X[0] == 0.0


def test_same_input_same_hull(fms):
    a = vis3d.Hull(fms, 1900.0, seed=3)
    b = vis3d.Hull(fms, 1900.0, seed=3)
    pa, pb = a.points(), b.points()
    assert pa.shape == pb.shape and np.array_equal(pa, pb)
    assert np.array_equal(a.facets(), b.facets())
    assert a.passes == b.passes


def test_olivine_tieline_converges_to_the_model_value_for_every_seed(fms):
    """The 1900 K olivine-liquid tie-line on the x_Si = 1/3 join, the case the random
    sampler of python/mqmqa/ternary.py put anywhere from 0.33 to 0.47 (liquidus, join
    X_Fe) depending on the seed. Each seed must land within X_TOL of the model's
    equilibrium, so the seeds also agree with each other."""
    pytest.importorskip("pycalphad")
    T, x_fe, x_si = 1900.0, 0.20, 1.0 / 3.0
    ref, _ = _pyc_equilibrium(T, x_fe, x_si)
    assert [p for p, _, _ in ref] == [LIQ, "OLIVINE"]
    liq_ref, sol_ref = ref[0][1], ref[1][1]
    liq, sol = [], []
    for seed in range(5):
        got = _mine(_hull(fms, T, seed), x_fe, x_si)
        assert [p for p, _, _ in got] == [LIQ, "OLIVINE"], (seed, got)
        # both ends on the join (the liquid end is interpolated between samples)
        assert abs(got[0][2] - 1 / 3) < 1e-6 and abs(got[1][2] - 1 / 3) < 1e-6
        liq.append(got[0][1])
        sol.append(got[1][1])
    assert max(abs(v - liq_ref) for v in liq) < X_TOL, (liq, liq_ref)
    assert max(abs(v - sol_ref) for v in sol) < X_TOL, (sol, sol_ref)
    assert max(liq) - min(liq) < X_TOL and max(sol) - min(sol) < X_TOL


@pytest.mark.parametrize("T, x_fe, x_si", [
    (1800.0, 0.30, 1.0 / 3.0),     # liquid + olivine
    (2000.0, 0.10, 1.0 / 3.0),     # liquid + olivine
    (1900.0, 0.15, 0.80),          # two liquids (the silica-rich miscibility gap)
    (1900.0, 0.30, 0.10),          # liquid + periclase
    (2000.0, 0.20, 0.15),          # liquid + periclase
    (1800.0, 0.10, 0.10),          # liquid + olivine + periclase
    (1700.0, 0.35, 0.60),          # liquid + orthopyroxene, next to a metastable two-liquid field
])
def test_tielines_match_the_model_equilibrium(fms, T, x_fe, x_si):
    pytest.importorskip("pycalphad")
    ref, g_ref = _pyc_equilibrium(T, x_fe, x_si)
    h = _hull(fms, T)
    got = _mine(h, x_fe, x_si)
    assert [p for p, _, _ in got] == [p for p, _, _ in ref], (got, ref)
    for (p, a1, a3), (_, b1, b3) in zip(got, ref):
        assert np.hypot(a1 - b1, a3 - b3) < X_TOL, (p, (a1, a3), (b1, b3))
    # The hull energy is a lever sum of real phase states, so it cannot fall below the
    # true minimum (beyond solver noise); it lies above it by the chord error between
    # samples, ~0.1 J on these tie-lines.
    dg = h.gibbs(1 - x_fe - x_si, x_si) - g_ref
    assert -1e-2 < dg < 1.0, dg


# --------------------------------------------------------------------- the exact hull

def test_exact_hull_agrees_with_scipy_and_survives_degenerate_input(fms):
    """The module's hull decides orientations exactly; mqmqa_lower_hull_2d can loop
    without end once refinement puts many samples on one line, so the refined point set
    goes only to this one."""
    scipy_spatial = pytest.importorskip("scipy.spatial")
    h = _hull(fms, 1900.0)
    P = h.points()[:, :3].copy()
    F = vis3d.lower_hull(P)
    S = scipy_spatial.ConvexHull(P)
    low = np.array([s for e, s in zip(S.equations, S.simplices) if e[2] < -1e-12])

    def hull_g(facets, q):
        best = np.inf
        for f in facets:
            a, b, c = P[f, :2]
            M = np.array([[a[0] - c[0], b[0] - c[0]], [a[1] - c[1], b[1] - c[1]]])
            if abs(np.linalg.det(M)) < 1e-15:
                continue
            w = np.linalg.solve(M, q - c)
            w = np.array([w[0], w[1], 1 - w.sum()])
            if (w >= -1e-9).all():
                best = min(best, w @ P[f, 2])
        return best

    rng = np.random.default_rng(1)
    for q in rng.dirichlet([1, 1, 1], 25)[:, 1:]:
        # rounding to the exact grid moves a sample by < 5e-10 in composition
        assert abs(hull_g(F, q) - hull_g(low, q)) < 1e-2

    n = 40
    pts = [(i / n, j / n, (i / n - 0.3) ** 2 + (j / n - 0.4) ** 2)
           for i in range(n + 1) for j in range(n + 1 - i)]
    pts += [(0.2 + t * 1e-3, 0.3 + t * 2e-3, 0.0) for t in range(30)]   # collinear, coplanar
    pts += pts[:25]                                                       # duplicates
    assert len(vis3d.lower_hull(np.array(pts))) > 0


# ------------------------------------------------------------------ step 2: the section

def _areas(s):
    c = s.comp[:, 1:]
    a = c[s.tri[:, 1]] - c[s.tri[:, 0]]
    b = c[s.tri[:, 2]] - c[s.tri[:, 0]]
    return 0.5 * (a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0])


def _check_mesh(s, T, z_per_kelvin=1e-3):
    nt, nv = len(s.tri), len(s.comp)
    assert s.patch_start[0] == 0 and s.patch_start[-1] == nt
    assert np.all(np.diff(s.patch_start) > 0)
    assert np.all((s.patch_phase >= 0) & (s.patch_phase < len(s.labels)))
    assert len(set(s.labels)) == len(s.labels)
    assert s.tri.max() < nv
    # every vertex belongs to exactly one patch: seams are duplicated, never shared
    owner = np.full(nv, -1)
    for p in range(len(s.patch_phase)):
        v = np.unique(s.tri[s.patch_start[p]:s.patch_start[p + 1]])
        assert np.all(owner[v] == -1), "a vertex is shared between patches"
        owner[v] = p
    assert np.all(owner >= 0)
    ar = _areas(s)
    assert np.all(ar > 0), "every triangle counter-clockwise with positive area"
    assert abs(ar.sum() - 0.5) < 1e-9, "the patches tile the whole triangle"
    assert np.allclose(s.comp.sum(axis=1), 1.0, atol=1e-12)
    X = s.comp[:, 1] + 0.5 * s.comp[:, 2]
    Y = np.sqrt(3) / 2 * s.comp[:, 2]
    assert np.allclose(s.pos[:, 0], X, atol=1e-6) and np.allclose(s.pos[:, 1], Y, atol=1e-6)
    assert np.allclose(s.pos[:, 2], T * z_per_kelvin, rtol=1e-6)
    assert np.all(s.temp == T)
    assert len(s.line_pos) == 2 * (len(s.line_start) - 1)


def _labels_at(h, x2x3):
    out = []
    for x2, x3 in x2x3:
        out.append("+".join(sorted(p for p, amt, _, _ in h.assemblage(x2, x3))))
    return out


@pytest.mark.parametrize("db_path, T", [(FMS, 1900.0), (CAS, 1673.0)])
def test_section_patches_carry_one_label_each(db_path, T):
    """One label per triangle by construction, and it is the equilibrium at the triangle's
    centroid: the patches are the hull's own regions. Clipping along a facet edge leaves
    numerically degenerate slivers whose centroid can read the facet next door; together
    they must hold no measurable area."""
    db = mqmqa.Database.read(str(db_path))
    h = _hull(db, T)
    s = h.section(lattice_n=60)
    _check_mesh(s, T)
    tl = s.tri_label
    cen = s.comp[s.tri].mean(axis=1)[:, 1:]
    got = _labels_at(h, cen)
    bad = [k for k in range(len(tl)) if got[k] != s.labels[tl[k]]]
    ar = _areas(s)
    assert ar[bad].sum() < 1e-6, f"{len(bad)} of {len(tl)} centroids disagree, area {ar[bad].sum()}"


def test_section_matches_the_2d_assemblage_lookup(fms):
    """The section's fields are the existing 2D lookup, mqmqa_hull_assemblage_2d, run on the
    same candidates and facets. That lookup has no notion of a miscibility gap, so phase
    sets are compared (two liquids count as liquid)."""
    h = _hull(fms, 1900.0)
    P = h.points()
    P[:, :2] = np.round(P[:, :2] * 2.0 ** 24) / 2.0 ** 24     # the hull's exact grid
    F = h.facets()
    names = h.phase_names
    pts = _ffi.new("double[]", P[:, :3].ravel().tolist())
    fac = _ffi.new("int[]", F.ravel().tolist())
    tri = _ffi.new("int[3]"); w = _ffi.new("double[3]"); g = _ffi.new("double[1]")
    n, total, same = 50, 0, 0
    for i in range(n + 1):
        for j in range(n + 1 - i):
            x2, x3 = i / n, j / n
            ok = _lib.mqmqa_hull_assemblage_2d(pts, len(P), fac, len(F), x2, x3, tri, w, g)
            assert ok == 1
            old = {names[int(P[tri[k], 3])] for k in range(3) if w[k] > 1e-6}
            new = {p for p, _, _, _ in h.assemblage(x2, x3)}
            total += 1
            same += old == new
    assert same == total, f"{total - same} of {total} disagree"


def test_section_boundaries_converge_with_the_lattice(fms):
    """Field areas at lattice 30, 60 and 120: the changes shrink (or are already zero to
    rounding, when every seam is a straight tie-line), and the last is below what a boundary
    shift of X_TOL along the whole boundary length would give."""
    h = _hull(fms, 1900.0)
    area = {}
    for n in (30, 60, 120):
        s = h.section(lattice_n=n)
        _check_mesh(s, 1900.0)
        ar = _areas(s)
        tl = s.tri_label
        area[n] = {lab: ar[tl == k].sum() for k, lab in enumerate(s.labels)}
    labs = set(area[30]) | set(area[60]) | set(area[120])
    d1 = sum(abs(area[30].get(l, 0) - area[120].get(l, 0)) for l in labs)
    d2 = sum(abs(area[60].get(l, 0) - area[120].get(l, 0)) for l in labs)
    assert d2 < d1 or d2 < 1e-12
    boundary_length = 6.0   # generous: the seams of this section total well under this
    assert d2 < X_TOL * boundary_length


def test_section_seams_are_located_to_x_tol(fms):
    """Along the olivine join the seam crossings of a lattice-60 and a lattice-120 section
    are the same boundaries, within X_TOL."""
    h = _hull(fms, 1900.0)
    y = np.sqrt(3) / 2 / 3                         # x3 = 1/3 in Cartesian Y

    def crossings(s):
        seg = s.line_pos[:, :2].reshape(-1, 2, 2).astype(np.float64)
        out = []
        for (x0, y0), (x1, y1) in seg:
            if (y0 - y) * (y1 - y) < 0:
                out.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
        return np.sort(out)

    c60, c120 = crossings(h.section(lattice_n=60)), crossings(h.section(lattice_n=120))
    assert len(c60) > 0
    for c in c120:
        assert np.min(np.abs(c60 - c)) < X_TOL
    for c in c60:
        assert np.min(np.abs(c120 - c)) < X_TOL


def test_same_input_same_section(fms):
    a = vis3d.section(fms, 1900.0, lattice_n=30)
    b = vis3d.section(fms, 1900.0, lattice_n=30)
    for f in ("pos", "comp", "temp", "tri", "patch_start", "patch_phase", "line_pos", "line_start"):
        assert np.array_equal(getattr(a, f), getattr(b, f)), f
    assert a.labels == b.labels


# ----------------------------------------------------------------------- loud failures

def test_refuses_rather_than_approximates(fms):
    with pytest.raises(vis3d.Vis3DError, match="did not converge"):
        vis3d.Hull(fms, 1900.0, max_refine=1)
    with pytest.raises(vis3d.Vis3DError, match="no phase named"):
        vis3d.Hull(fms, 1900.0, phases=[LIQ, "NOT-A-PHASE"])
    salt = mqmqa.Database.read(str(ROOT / "web" / "LiCl-KCl.dat"))
    with pytest.raises(vis3d.Vis3DError, match="three"):
        vis3d.Hull(salt, 900.0)
    with pytest.raises(vis3d.Vis3DError, match="lattice_n"):
        vis3d.section(fms, 1900.0, lattice_n=0)


# ---------------------------------------------------------- step 3: the liquidus surface

WINDOW = (1300.0, 3200.0)     # the whole FeO-MgO-SiO2 liquidus, MgO melting at 3098 K


def _pyc_liquidus(x2, x3, T_lo, T_hi):
    """pycalphad's liquidus: bisection on whether its equilibrium holds a solid."""
    from pycalphad import Database, equilibrium, variables as v
    dbf = _pyc_equilibrium.dbf = getattr(_pyc_equilibrium, "dbf", None) or Database(str(FMS))
    x_fe = 1.0 - x2 - x3
    tot = 1.0 + x_fe + x2 + 2.0 * x3

    def solids(T):
        eq = equilibrium(dbf, ["FE", "MG", "SI", "O"], PHASES,
                         {v.T: T, v.P: 1e5, v.N: 1, v.X("FE"): x_fe / tot,
                          v.X("MG"): x2 / tot, v.X("SI"): x3 / tot})
        return sorted({str(n) for n, a in zip(np.ravel(eq.Phase.values), np.ravel(eq.NP.values))
                       if str(n) not in ("", "nan") and str(n) != LIQ and a > 1e-6})

    assert solids(T_lo) and not solids(T_hi)
    while T_hi - T_lo > 0.05:
        mid = 0.5 * (T_lo + T_hi)
        if solids(mid):
            T_lo = mid
        else:
            T_hi = mid
    return 0.5 * (T_lo + T_hi), solids(T_lo)


def test_liquidus_at_the_liquid_end_of_the_1900K_tieline(fms):
    """The liquid end of the 1900 K olivine tie-line (from pycalphad) has its liquidus at
    exactly 1900 K, with olivine first to crystallize."""
    pytest.importorskip("pycalphad")
    ref, _ = _pyc_equilibrium(1900.0, 0.20, 1.0 / 3.0)
    x_fe = ref[0][1]
    T, prim = vis3d.liquidus_point(fms, 1.0 - x_fe - 1.0 / 3.0, 1.0 / 3.0, *WINDOW, t_tol=1e-3)
    assert prim == "OLIVINE"
    assert abs(T - 1900.0) < 0.01


@pytest.mark.parametrize("x2, x3", [(0.5, 0.1), (0.3, 0.3), (0.2, 0.2), (0.3, 0.5)])
def test_liquidus_matches_pycalphad_where_the_liquid_is_one_phase(fms, x2, x3):
    pytest.importorskip("pycalphad")
    T, prim = vis3d.liquidus_point(fms, x2, x3, *WINDOW, t_tol=1e-2)
    T_ref, sol = _pyc_liquidus(x2, x3, T - 20.0, T + 20.0)
    assert sol == [prim]
    assert abs(T - T_ref) < 0.1, (T, T_ref)       # pycalphad bisected to 0.05 K


@pytest.mark.parametrize("x2, x3", [(0.1, 0.3), (0.05, 0.45), (0.3, 0.5)])
def test_liquidus_agrees_with_the_full_equilibrium(fms, x2, x3):
    """Two degrees above the liquidus the refined hull holds no solid; two below it holds the
    primary phase. Hulls at x_tol 1e-4: two degrees under a flat silica liquidus the primary
    phase can be under 1e-3 of the mass (0.0007 at (0.05, 0.45))."""
    T, prim = vis3d.liquidus_point(fms, x2, x3, *WINDOW, t_tol=1e-2)
    above = {p for p, _, _, _ in vis3d.Hull(fms, T + 2.0, x_tol=1e-4).assemblage(x2, x3)}
    below = {p for p, _, _, _ in vis3d.Hull(fms, T - 2.0, x_tol=1e-4).assemblage(x2, x3)}
    assert above == {LIQ}
    assert prim in below


def _check_surface(s, zpk=1e-3):
    nt, nv = len(s.tri), len(s.comp)
    assert s.patch_start[0] == 0 and s.patch_start[-1] == nt and np.all(np.diff(s.patch_start) > 0)
    owner = np.full(nv, -1)
    for p in range(len(s.patch_phase)):
        v = np.unique(s.tri[s.patch_start[p]:s.patch_start[p + 1]])
        assert np.all(owner[v] == -1)
        owner[v] = p
    ar = _areas(s)
    assert np.all(ar > 0) and abs(ar.sum() - 0.5) < 1e-9
    assert np.allclose(s.pos[:, 2], s.temp * zpk, rtol=1e-6)
    assert np.all((s.temp >= WINDOW[0]) & (s.temp <= WINDOW[1]))


def test_liquidus_surface(fms):
    """One patch per primary-phase field, tiling the triangle; the corners carry the oxides'
    melting points; the fields and the valleys between them converge as the lattice goes
    from 10 to 20."""
    area = {}
    for n in (10, 20):
        s = vis3d.liquidus_surface(fms, *WINDOW, lattice_n=n)
        _check_surface(s)
        assert sorted(s.labels) == ["CRISTOBALITE", "MAGNESIOWUSTITE", "OLIVINE", "ORTHOPYROXENE"]
        assert len(s.patch_phase) == len(s.labels)
        ar, tl = _areas(s), s.tri_label
        area[n] = {lab: ar[tl == k].sum() for k, lab in enumerate(s.labels)}
    for corner, name in (((0.0, 0.0), "MAGNESIOWUSTITE"), ((1.0, 0.0), "MAGNESIOWUSTITE"),
                         ((0.0, 1.0), "CRISTOBALITE")):
        i = np.argmin((s.comp[:, 1] - corner[0]) ** 2 + (s.comp[:, 2] - corner[1]) ** 2)
        T, prim = vis3d.liquidus_point(fms, *corner, *WINDOW)
        assert prim == name and abs(s.temp[i] - T) < 1e-9
    for lab in area[20]:
        assert abs(area[10][lab] - area[20][lab]) < 0.01, lab


def test_liquidus_outside_the_window_is_an_error(fms):
    with pytest.raises(vis3d.Vis3DError, match="above t_hi"):
        vis3d.liquidus_point(fms, 0.9, 0.05, 1300.0, 2500.0)
    with pytest.raises(vis3d.Vis3DError, match="below t_lo"):
        vis3d.liquidus_point(fms, 0.1, 0.3, 1700.0, 3200.0)
    with pytest.raises(vis3d.Vis3DError, match="at most 50 K"):     # split-liquid accuracy
        vis3d.liquidus_point(fms, 0.1, 0.3, 1300.0, 3200.0, n_temps=20)


# ------------------------------------------------------------ step 4: Gibbs surfaces

def _patch_vertices(s, name):
    tl = s.tri_label
    return np.unique(s.tri[tl == s.labels.index(name)])


def test_gibbs_surfaces_against_equilibrium(fms):
    """Heights above equilibrium at 1900 K: zero wherever the equilibrium is the single
    liquid, never below it beyond the ~0.2 J the refined hull resolves in flat two-liquid
    regions, and the hull patch at zero. On the olivine join the liquid rises off zero
    exactly across the liquid end of the tie-line (from pycalphad)."""
    pytest.importorskip("pycalphad")
    s = vis3d.gibbs_surfaces(fms, 1900.0, relative=True, lattice_n=30)
    assert s.labels[-1] == "HULL" and LIQ in s.labels
    assert np.allclose(s.pos[:, 2], s.scalar * 1e-5, rtol=1e-5) and np.all(s.temp == 1900.0)
    h = _hull(fms, 1900.0)
    v = _patch_vertices(s, LIQ)
    assert s.scalar[v].min() > -0.5
    single = [i for i in v if [p for p, _, _, _ in h.assemblage(*s.comp[i, 1:])] == [LIQ]]
    assert len(single) > 50 and np.all(s.scalar[single] == 0.0)
    assert np.abs(s.scalar[_patch_vertices(s, "HULL")]).max() < 0.1
    height = {tuple(np.round(s.comp[i, 1:], 9)): s.scalar[i] for i in v}
    x_fe_liq = _pyc_equilibrium(1900.0, 0.20, 1.0 / 3.0)[0][0][1]
    # the lattice-30 join nodes either side of it (x2 = Mg = 2/3 - x_fe)
    k = int(np.floor((2.0 / 3.0 - x_fe_liq) * 30))
    liquid_side, solid_side = (round(k / 30, 9), round(1 / 3, 9)), (round((k + 1) / 30, 9), round(1 / 3, 9))
    assert 1 - k / 30 - 1 / 3 > x_fe_liq > 1 - (k + 1) / 30 - 1 / 3
    # The height grows about as the square of the distance past the liquid end, so how high the
    # first node sits depends on where the tie-line ends in its lattice cell (0.003 in x_Fe short
    # of it since the 2026-10-07 refit: 0.24 J, then 47 J one node on). Positive, then climbing.
    beyond = [height[(round((k + j) / 30, 9), round(1 / 3, 9))] for j in (1, 2, 3)]
    assert height[liquid_side] == 0.0 and height[solid_side] == beyond[0]
    assert 0.0 < beyond[0] < beyond[1] < beyond[2] and beyond[1] > 1.0, beyond


def test_gibbs_surfaces_against_the_pure_components(fms):
    """Relative to the plane through the pure components' equilibrium energies, the hull
    lies at or below zero and meets it at the corners."""
    s = vis3d.gibbs_surfaces(fms, 1900.0, relative=False, lattice_n=20)
    hv = _patch_vertices(s, "HULL")
    assert s.scalar[hv].max() < 1e-3
    corners = [i for i in hv if np.isclose(s.comp[i].max(), 1.0)]
    assert len(corners) >= 3 and np.abs(s.scalar[corners]).max() < 1e-3
    # CEF lines as curves and compounds as points: olivine, orthopyroxene, three oxides
    assert len(s.line_start) - 1 > 3


# ----------------------------------------------------- step 5: VTK layout and PyVista

def test_surface_arrays_are_vtk_layout(fms):
    s = _hull(fms, 1900.0).section(lattice_n=20)
    pts, faces, lab, lpts, lines = vis3d.surface_arrays(s)
    assert pts.shape == (len(s.pos), 3) and pts.dtype == np.float64
    f = faces.reshape(-1, 4)
    assert np.all(f[:, 0] == 3) and np.array_equal(f[:, 1:], s.tri.astype(np.int64))
    assert len(lab) == len(s.tri) and np.array_equal(lab, s.tri_label)
    k, nseg = 0, 0
    while k < len(lines):                      # [n, i0, ..., i_{n-1}] records
        assert lines[k] == 2 and lines[k + 1] < len(lpts) and lines[k + 2] < len(lpts)
        k += lines[k] + 1
        nseg += 1
    assert nseg == len(s.line_start) - 1


def test_prism_wedges_carry_the_equilibrium_below_them(fms):
    """Every wedge has one label, and it is the assemblage at the centroid of its lower
    triangle at that level."""
    hulls = [_hull(fms, T) for T in (1800.0, 1900.0, 2000.0)]
    pts, cells, types, lab, labels = vis3d.prism_arrays(hulls, lattice_n=12)
    n_node = 13 * 14 // 2
    assert pts.shape == (3 * n_node, 3) and np.all(types == vis3d.VTK_WEDGE)
    c = cells.reshape(-1, 7)
    assert np.all(c[:, 0] == 6) and len(c) == 2 * 144 and len(lab) == len(c)
    assert np.all(c[:, 4:] - c[:, 1:4] == n_node)             # top sits over bottom
    comp = pts[:, :2]
    for w in range(0, len(c), 17):
        level = c[w, 1] // n_node
        xy = comp[c[w, 1:4]].mean(axis=0)
        x3 = xy[1] / (np.sqrt(3) / 2)
        x2 = xy[0] - 0.5 * x3
        name = "+".join(sorted(p for p, _, _, _ in hulls[level].assemblage(x2, x3)))
        assert labels[lab[w]] == name


def test_pyvista_objects(fms):
    pv = pytest.importorskip("pyvista")
    s = _hull(fms, 1900.0).section(lattice_n=20)
    surf, lines = vis3d.to_polydata(s)
    assert surf.n_cells == len(s.tri) and surf.n_points == len(s.pos)
    assert np.array_equal(surf.cell_data["phase_field"], s.tri_label)
    grid = vis3d.to_unstructured([_hull(fms, 1800.0), _hull(fms, 1900.0)], lattice_n=10)
    assert grid.n_cells == 100 and isinstance(grid, pv.UnstructuredGrid)
