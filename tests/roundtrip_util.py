"""Shared machinery for the database-writer tests: which files ship, and a structural
plus numerical comparison of two loaded databases (the original and its conversion).

Energies are compared as a relative deviation |a - b| / max(|a|, 1 J). The writers
print every coefficient with enough digits to read back as the same double, so a
conversion read by the same engine reproduces the original bit for bit (observed
deviation 0 for every shipped file) and one read by the other engine differs only by
the order terms are summed in (observed <= 2e-15). REL_TOL = 1e-14 leaves a few tens
of ulps for that and still catches a change in the 14th significant digit of an
endmember coefficient (test_comparison_catches_a_planted_change).

ORACLE_TOL = 1e-10 applies where pycalphad evaluates the file: a different
implementation of the same model, whose magnetic term differs from this engine's by
up to 5e-12 relative on the unconverted source as well.
"""
import glob
import os
import subprocess
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "python"))

from mqmqa import Database  # noqa: E402
from mqmqa.equilibrium import build_inputs  # noqa: E402
from mqmqa._abi import c_equilibrate  # noqa: E402

REL_TOL = 1e-14
ORACLE_TOL = 1e-10
# 300-3000 K, offset so no point sits on an interval breakpoint, plus two points
# above the 6000 K limit of the ChemSage data, where those data are zero.
T_GRID = [float(t) for t in np.linspace(300.37, 3000.37, 28)] + [6500.37, 8000.0]

DB_EXT = (".dat", ".tdb", ".utdb", ".xtdb")


def shipped_databases():
    """Every tracked database file under data/ and web/ (git's view, so untracked
    local scratch never counts); falls back to a glob outside a git checkout."""
    try:
        out = subprocess.run(["git", "ls-files", "data", "web"], cwd=ROOT, check=True,
                             capture_output=True, text=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        out = [os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, "data", "**", "*"),
                                                           recursive=True)]
        out += [os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, "web", "*"))]
    files = sorted(p.replace("\\", "/") for p in out if p.lower().endswith(DB_EXT))
    return [os.path.join(ROOT, p) for p in files]


def pycalphad_fixtures(names):
    """pycalphad's own test databases that the engine reads: extra coverage (SUBG and
    reciprocal SUBQ liquids, magnetic and multi-phase TDBs) beyond the shipped files.
    Empty when pycalphad or its test data is absent."""
    try:
        import pycalphad
    except ImportError:
        return []
    root = os.path.join(os.path.dirname(pycalphad.__file__), "tests", "databases")
    return [os.path.join(root, n) for n in names if os.path.exists(os.path.join(root, n))]


def is_nasa_thermo(path):
    """The NASA 7-coefficient gas file shares the .dat extension but is read by the
    gas module, not the database reader; it is not a ChemSage database."""
    with open(path, encoding="ascii", errors="replace") as f:
        return f.readline().strip().upper().startswith("THERMO")


def rel(a, b):
    return abs(a - b) / max(abs(a), 1.0)


def _base(name):
    """Constituent name without a charge suffix (a writer may add one to a bare ion)."""
    i = len(name)
    while i and (name[i - 1].isdigit() or name[i - 1] == "."):
        i -= 1
    if i and name[i - 1] in "+-":
        return name[:i - 1]
    return name


def _endmembers(subls):
    idx = [range(len(s["constituents"])) for s in subls]
    for combo in np.array(np.meshgrid(*idx, indexing="ij")).reshape(len(idx), -1).T:
        Y = []
        for s, k in zip(subls, combo):
            y = [0.0] * len(s["constituents"])
            y[k] = 1.0
            Y += y
        yield Y


def _random_Y(subls, rng):
    Y = []
    for s in subls:
        y = rng.uniform(0.02, 1.0, len(s["constituents"]))
        Y += list(y / y.sum())
    return Y


def _neutral_composition(db, p, weights):
    cats, ans = db.cations(p), db.anions(p)
    comp = {}
    pos = 0.0
    for c, w in zip(cats, weights):
        el = _element(c["name"])
        comp[el] = comp.get(el, 0.0) + w
        pos += w * c["charge"]
    for a in ans:
        el = _element(a["name"])
        comp[el] = comp.get(el, 0.0) + pos / (len(ans) * a["charge"])
    return comp


def _element(name):
    import re
    return re.match(r"[A-Z]+", name).group(0)


def compare(orig, conv, rng_seed=11, T_grid=T_GRID, n_random=6):
    """Assert conv holds the same model as orig; return the worst relative deviation."""
    worst = 0.0
    rng = np.random.default_rng(rng_seed)
    assert [e for e, _ in orig.elements] == [e for e, _ in conv.elements]
    assert [m for _, m in orig.elements] == [m for _, m in conv.elements]
    assert orig.phase_names == conv.phase_names
    for p, name in enumerate(orig.phase_names):
        kind = orig.phase_kind(p)
        assert conv.phase_kind(p) == kind, name
        if kind == 1:
            so, sc = orig.cef_sublattices(p), conv.cef_sublattices(p)
            assert so == sc, name
            probes = list(_endmembers(so))
            for T in T_grid:
                pts = probes + [_random_Y(so, rng) for _ in range(n_random)]
                for Y in pts:
                    for atoms in (False, True):
                        a = orig.cef_gibbs(p, Y, T, per_mole_atoms=atoms)
                        b = conv.cef_gibbs(p, Y, T, per_mole_atoms=atoms)
                        d = rel(a, b)
                        assert d < REL_TOL, (name, T, Y, a, b)
                        worst = max(worst, d)
            continue
        # MQMQA liquid: species by position (a bare ion may gain its charge suffix)
        assert orig.is_subq(p) == conv.is_subq(p), name
        co, cc = orig.cations(p), conv.cations(p)
        ao, ac = orig.anions(p), conv.anions(p)
        assert [_base(c["name"]) for c in co] == [_base(c["name"]) for c in cc], name
        assert [_base(a["name"]) for a in ao] == [_base(a["name"]) for a in ac], name
        assert [(c["charge"], c["group"]) for c in co] == [(c["charge"], c["group"]) for c in cc]
        assert [(a["charge"], a["group"]) for a in ao] == [(a["charge"], a["group"]) for a in ac]
        assert orig.mqmz(p) == conv.mqmz(p), name
        for T in T_grid:
            po, pc = orig.pairs(p, T), conv.pairs(p, T)
            mo = {(c, a): (g, s, z) for c, a, g, s, z in
                  zip(po["cat"], po["an"], po["G"], po["stoich"], po["zeta"])}
            mc = {(c, a): (g, s, z) for c, a, g, s, z in
                  zip(pc["cat"], pc["an"], pc["G"], pc["stoich"], pc["zeta"])}
            assert mo.keys() == mc.keys(), name
            for k in mo:
                d = rel(mo[k][0], mc[k][0])
                assert d < REL_TOL, (name, k, T, mo[k], mc[k])
                assert mo[k][1:] == mc[k][1:], (name, k)
                worst = max(worst, d)
            xo, xc = orig.mqmx(p, T), conv.mqmx(p, T)
            for key in ("mix", "code", "A", "B", "X", "Y", "p", "q", "r", "addcat"):
                assert xo[key] == xc[key], (name, key)
            for a, b in zip(xo["L"], xc["L"]):
                d = rel(a, b)
                assert d < REL_TOL, (name, T, a, b)
                worst = max(worst, d)
        # the single-phase equilibrium (quadruplet distribution) at a few compositions
        n = len(co)
        for T in (1273.37, 1873.37, 2273.37):
            io, ic = build_inputs(orig, p, T), build_inputs(conv, p, T)
            for wts in (np.full(n, 1.0 / n), rng.dirichlet(np.ones(n))):
                comp = _neutral_composition(orig, p, wts)
                a = c_equilibrate(io, comp)["GM"]
                b = c_equilibrate(ic, comp)["GM"]
                d = rel(a, b)
                assert d < REL_TOL, (name, T, comp, a, b)
                worst = max(worst, d)
    assert orig.stoich == conv.stoich
    for i, name in enumerate(orig.stoich):
        assert orig.stoich_elements(i) == conv.stoich_elements(i), name
        for T in T_grid:
            d = rel(orig.stoich_gibbs(i, T), conv.stoich_gibbs(i, T))
            assert d < REL_TOL, (name, T)
            worst = max(worst, d)
    return worst


def roundtrip(db, method, tmp_path, suffix):
    """Write db with the named writer method, read the file back."""
    out = os.path.join(str(tmp_path), "converted" + suffix)
    getattr(db, method)(out)
    return Database.read(out), out


def cef_binary_points(db, A, B, T):
    """(x_B, G per mole of atoms, phase) samples of every CEF and stoichiometric phase
    made only of elements A and B (vacancies allowed), for a binary lower hull."""
    pts = []
    elems = [e for e, _ in db.elements]
    for p, name in enumerate(db.phase_names):
        if db.phase_kind(p) != 1:
            continue
        subls = db.cef_sublattices(p)
        cons = {c for s in subls for c in s["constituents"]}
        if not cons <= {A, B, "VA"}:
            continue
        mixing = [k for k, s in enumerate(subls) if len(s["constituents"]) > 1]
        if len(mixing) != 1 or len(subls[mixing[0]]["constituents"]) != 2:
            continue
        m = mixing[0]
        for y in np.linspace(1e-6, 1 - 1e-6, 161):
            Y, nA, nB = [], 0.0, 0.0
            for k, s in enumerate(subls):
                ys = [y, 1 - y] if k == m else [1.0]
                Y += ys
                for c, f in zip(s["constituents"], ys):
                    nA += s["site_ratio"] * f * (c == A)
                    nB += s["site_ratio"] * f * (c == B)
            if nA + nB <= 0:
                continue
            pts.append((nB / (nA + nB), db.cef_gibbs(p, Y, T, per_mole_atoms=True), name))
    for i, name in enumerate(db.stoich):
        el = dict(zip(elems, db.stoich_elements(i)))
        if any(v and e not in (A, B) for e, v in el.items()):
            continue
        tot = el.get(A, 0.0) + el.get(B, 0.0)
        pts.append((el.get(B, 0.0) / tot, db.stoich_gibbs(i, T) / tot, name))
    return pts


def lower_hull(points):
    """Lower convex hull vertices (x, g, phase), left to right."""
    pts = sorted(points, key=lambda q: (q[0], q[1]))
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


def compare_hulls(h1, h2):
    """Two binary sections must pick the same stable phases at the same compositions."""
    assert [(x, ph) for x, _, ph in h1] == [(x, ph) for x, _, ph in h2]
    worst = 0.0
    for (_, g1, _), (_, g2, _) in zip(h1, h2):
        d = rel(g1, g2)
        assert d < REL_TOL
        worst = max(worst, d)
    return worst
