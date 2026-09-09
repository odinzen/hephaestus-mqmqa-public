"""Third-generation XTDB reader: model convention and diagram invariants.

The reader (src/xtdb.c, compiled to WASM) is specced by the Python reference evaluator
data/xtdb-alc/xtdb_ref.py, and the two agree to < 1e-6 J/mol-atom. These checks lock the
science of the reference, which the C port reproduces:

  1. The Einstein term is weighted by the atom count of the formula unit. Without it a
     compound gets ~1/N of its heat capacity (Al4C3 came out with NEGATIVE Cp at 300 K and
     destabilised at ~1050 K). Guard: Al4C3 Cp is positive at 300 K and approaches 7*3R.
  2. Pure-Al melts at 933.47 K and graphite Cp is ~8.5 J/mol/K (unchanged by the fix, since
     both are single-atom references).
  3. The Al-C diagram reproduces the He et al. (2021) Al4C3 peritectic near 2429 K.
  4. Pb-Sn (classic assessment in XTDB, read by the same engine) gives the eutectic at ~456 K
     and x(Sn) ~ 0.74.
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "data", "xtdb-alc"))
import xtdb_ref as X  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
ALC = os.path.join(ROOT, "data", "xtdb", "AlC.xtdb")
PBSN = os.path.join(ROOT, "web", "PbSn.xtdb")
R = 8.31451


def _endmember_cp(tp, params, phases, phase, cons, T, h=0.05):
    g = lambda t: X.endmember_G(tp, params, phases, phase, cons, t)
    return -T * (g(T + h) - 2 * g(T) + g(T - h)) / h ** 2


def _assemblage(tp, params, phases, names, B, T, ns=200):
    """Phases on the lower convex hull of G(x) at temperature T (same construction as the
    C engine and the browser). Returns {phase_name: (x_min, x_max)}."""
    xs, gs, ps = [], [], []
    for p, nm in enumerate(names):
        _, fixed = X.phase_G(tp, params, phases, nm, B, 1e-6, T)
        if fixed is not None:
            g, _ = X.phase_G(tp, params, phases, nm, B, fixed, T)
            if g is not None:
                xs.append(fixed); gs.append(g); ps.append(p)
            continue
        for i in range(ns + 1):
            x = min(max(i / ns, 1e-6), 1 - 1e-6)
            g, _ = X.phase_G(tp, params, phases, nm, B, x, T)
            if g is not None:
                xs.append(x); gs.append(g); ps.append(p)
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    cx, cg, cp = [], [], []
    for i in order:
        if cx and abs(xs[i] - cx[-1]) < 1e-9:
            if gs[i] < cg[-1]:
                cg[-1] = gs[i]; cp[-1] = ps[i]
        else:
            cx.append(xs[i]); cg.append(gs[i]); cp.append(ps[i])
    hv = []
    for i in range(len(cx)):
        while len(hv) >= 2:
            a, b = hv[-2], hv[-1]
            cross = (cx[b] - cx[a]) * (cg[i] - cg[a]) - (cg[b] - cg[a]) * (cx[i] - cx[a])
            if cross <= 1e-6:
                hv.pop()
            else:
                break
        hv.append(i)
    out = {}
    for i in hv:
        nm = names[cp[i]]
        lo, hi = out.get(nm, (cx[i], cx[i]))
        out[nm] = (min(lo, cx[i]), max(hi, cx[i]))
    return out


def test_alc_pure_al_melting():
    tp, params, phases = X.parse(ALC)
    f = lambda T: (X.endmember_G(tp, params, phases, "LIQUID", "AL", T)
                   - X.endmember_G(tp, params, phases, "FCC_A1", "AL:VA", T))
    lo, hi = 700.0, 1100.0
    for _ in range(80):
        m = 0.5 * (lo + hi)
        if f(lo) * f(m) <= 0:
            hi = m
        else:
            lo = m
    assert abs(0.5 * (lo + hi) - 933.47) < 0.5


def test_graphite_heat_capacity():
    tp, params, phases = X.parse(ALC)
    cp = _endmember_cp(tp, params, phases, "GRAPHITE", "C", 298.15)
    assert 7.0 < cp < 10.0                       # graphite ~8.5 J/mol/K


def test_al4c3_heat_capacity_atom_count_weighted():
    """Regression for the Einstein atom-count weight: Al4C3 (7 atoms) must have a physical,
    positive Cp approaching 7*3R, not the ~3R (and negative at low T) the unweighted term gave."""
    tp, params, phases = X.parse(ALC)
    cp300 = _endmember_cp(tp, params, phases, "AL4C3", "AL:C", 300.0)
    cp2000 = _endmember_cp(tp, params, phases, "AL4C3", "AL:C", 2000.0)
    assert cp300 > 0.0                            # was negative before the fix
    dulong_petit = 7 * 3 * R                       # 174.6 J/mol/K
    assert 0.5 * dulong_petit < cp2000 < 1.25 * dulong_petit


def test_alc_al4c3_peritectic_near_2429K():
    tp, params, phases = X.parse(ALC)
    names = list(phases.keys())
    stable = lambda T: "AL4C3" in _assemblage(tp, params, phases, names, "C", T)
    lo, hi = 2000.0, 2600.0                        # bracket, then bisect the upper stability edge
    assert stable(lo) and not stable(hi)
    for _ in range(40):
        m = 0.5 * (lo + hi)
        if stable(m):
            lo = m
        else:
            hi = m
    assert abs(0.5 * (lo + hi) - 2429.0) < 25.0    # He et al. (2021): 2156 degC = 2429 K


def test_pbsn_eutectic():
    tp, params, phases = X.parse(PBSN)
    names = list(phases.keys())
    # just below the eutectic the two terminal solids coexist without liquid; just above,
    # liquid appears. Bracket the eutectic temperature between those.
    asm_lo = _assemblage(tp, params, phases, names, "SN", 450.0)
    asm_hi = _assemblage(tp, params, phases, names, "SN", 460.0)
    assert "LIQUID" not in asm_lo
    assert "LIQUID" in asm_hi
    lo_x, hi_x = asm_hi["LIQUID"]                   # eutectic liquid composition
    assert 0.70 < 0.5 * (lo_x + hi_x) < 0.78        # x(Sn) ~ 0.74
