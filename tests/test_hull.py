"""The C lower convex hull (src/hull.c) must match scipy's ConvexHull lower faces,
including degenerate grid data. This is the geometric core of the multiphase
equilibrium: the facet under a bulk composition gives the coexisting phases."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
from mqmqa._abi import _ffi, _lib                       # noqa: E402

ConvexHull = pytest.importorskip("scipy.spatial").ConvexHull

_ffi.cdef("int mqmqa_lower_hull_1d(const double*, int, int*, int);"
          "int mqmqa_lower_hull_2d(const double*, int, int*, int);", override=True)


def _c_lower_2d(P):
    n = len(P)
    flat = _ffi.new("double[]", [c for xyz in P for c in xyz])
    out = _ffi.new("int[]", 3 * (6 * n + 16))
    nf = _lib.mqmqa_lower_hull_2d(flat, n, out, 6 * n + 16)
    return [(out[3*i], out[3*i+1], out[3*i+2]) for i in range(nf)] if nf > 0 else []


def _scipy_lower_vertices(P):
    h = ConvexHull(np.array(P))
    v = set()
    for eq, simp in zip(h.equations, h.simplices):
        if eq[2] < -1e-9:
            v.update(int(s) for s in simp)
    return v


def test_random_clouds_match_scipy():
    rng = np.random.default_rng(7)
    tested = 0
    for _ in range(40):
        n = int(rng.integers(6, 40))
        P = [[float(rng.random()) for _ in range(3)] for _ in range(n)]
        fac = _c_lower_2d(P)
        if not fac:
            continue
        tested += 1
        cv = set().union(*[set(t) for t in fac])
        assert cv == _scipy_lower_vertices(P)
    assert tested >= 30


def test_degenerate_grid_matches_scipy():
    G = []
    for i in range(6):
        for j in range(6 - i):
            x, y = i / 5, j / 5
            G.append([x, y, 0.3*x*x + 0.2*y*y - 0.1*x*y - 0.05*x - 0.05*y])
    fac = _c_lower_2d(G)
    cv = set().union(*[set(t) for t in fac])
    assert cv == _scipy_lower_vertices(G)


def test_binary_lower_hull():
    pts = [[0.0, 0.0], [0.25, -0.5], [0.5, -0.3], [0.5, -0.9],
           [0.75, -0.4], [1.0, 0.0], [0.5, 0.2]]
    flat = _ffi.new("double[]", [c for xy in pts for c in xy])
    out = _ffi.new("int[]", 20)
    m = _lib.mqmqa_lower_hull_1d(flat, len(pts), out, 20)
    xs = [pts[out[i]][0] for i in range(m)]
    assert xs == [0.0, 0.25, 0.5, 1.0]           # dominated (0.5,-0.3) dropped, (0.5,-0.9) kept
