"""v0.5 fit: CALPHAD-style simultaneous optimization of the MgO-SiO2 liquid to the
measured invariants, on top of measured compound heat capacities (Fix A).

Two changes from v0.4:
  A) SOLIDS use their own measured Cp(T) (R&H 1995), not Neumann-Kopp (pdg.USE_COMPOUND_CP).
  B) the liquid excess is fit SIMULTANEOUSLY to the measured invariant temperatures
     (forsterite congruent, periclase-forsterite eutectic, enstatite peritectic,
     enstatite-cristobalite eutectic), instead of the v0.4 single-point anchoring.

Excess form (Q-code cation-mixing on (Mg,Si,O,O) + one silica-weighted gap term):
    Delta_g/O = (a00 + b00*T) + (a10 + b10*T)*chi_Mg + L_si * chi_Si^q
Free: a00, b00, a10, b10, L_si (q fixed). The b10 (chi_Mg entropy slope) is the new DOF
v0.4 lacked - it is the handle on the enstatite-side liquidus that a T-independent skew
could not turn without also moving forsterite.
"""
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "python"))

import build_dat as bd
import mqmqa
from mqmqa import equilibrium as eq
import _activity as act
import phase_diagram as pdg
import phase_hull as ph

pdg.USE_COMPOUND_CP = True          # Fix A on
COMPONENTS = pdg.COMPONENTS
Q_SI = 5

# resolution: coarse during optimization (FAST), fine for the final report (FINE).
FAST = dict(xhull=24, nbis=22, neut=22, xeut=13)
FINE = dict(xhull=60, nbis=48, neut=40, xeut=25)
RES = FAST

# measured invariant targets (K); compositions where relevant
T_FORST, X_FORST = 2163.0, 1.0 / 3.0
T_PERI_FORST_EUT = 2123.0            # periclase + forsterite eutectic (Bowen-Andersen)
T_ENST_PERI = 1830.0                 # enstatite incongruent melting
T_ENCR_EUT = 1816.0                  # enstatite + cristobalite eutectic
T_MONO, X_GAP_MG = 1968.0, 0.59      # Greig monotectic + MgO-side conjugate


def build_db(pp):
    a00, b00, a10, b10, L_si = pp
    excess = [dict(code="Q", li=[1, 2, 3, 3], exp=[0, 0, 0, 0],
                   coeffs=[a00, b00, 0, 0, 0, 0]),
              dict(code="Q", li=[1, 2, 3, 3], exp=[1, 0, 0, 0],
                   coeffs=[a10, b10, 0, 0, 0, 0]),
              dict(code="Q", li=[1, 2, 3, 3], exp=[0, Q_SI, 0, 0],
                   coeffs=[L_si, 0, 0, 0, 0, 0])]
    import os
    path = HERE / f"_v05_scaffold_{os.getpid()}.dat"
    path.write_text(bd.build(excess, version="v0.5"), encoding="ascii")
    db = mqmqa.Database.read(str(path))
    return db, db.phase_index("MGO-SIO2-LIQUID"), excess


def _bisect(f, lo, hi, n=55):
    flo, fhi = f(lo), f(hi)
    if flo == 0:
        return lo
    if flo * fhi > 0:
        return None
    for _ in range(n):
        m = 0.5 * (lo + hi)
        fm = f(m)
        if flo * fm > 0:
            lo, flo = m, fm
        else:
            hi = m
    return 0.5 * (lo + hi)


def _hull_pts(db, p, T, exclude):
    xs = np.linspace(0.03, 0.985, RES["xhull"])
    inp = eq.build_inputs(db, p, T, components=COMPONENTS)
    pts = [(float(x), pdg.liquid_gibbs_per_formula_unit(inp, float(x), T), "L") for x in xs]
    for name in pdg.SOLIDS:
        if name == exclude:
            continue
        g, x = pdg.solid_gibbs_per_formula_unit(name, T)
        pts.append((x, g, name))
    return pts


def _compound_stable(db, p, name, T):
    g_c, xC = pdg.solid_gibbs_per_formula_unit(name, T)
    hull = ph.lower_hull(_hull_pts(db, p, T, exclude=name))
    left, right = ph.hull_bracket(hull, xC)
    if abs(right[0] - left[0]) < 1e-9:
        gh = left[1]
    else:
        f = (xC - left[0]) / (right[0] - left[0])
        gh = left[1] + f * (right[1] - left[1])
    return g_c < gh - 1.0, (left[2], right[2])


def forsterite_T(db, p, lo=1600.0, hi=2900.0):
    def f(T):
        inp = eq.build_inputs(db, p, T, components=COMPONENTS)
        return (pdg.liquid_gibbs_per_formula_unit(inp, X_FORST, T)
                - pdg.solid_gibbs_per_formula_unit("M2S(forsterite)", T)[0])
    return _bisect(f, lo, hi, n=RES["nbis"])


def enstatite_peritectic_T(db, p, lo=1500.0, hi=2600.0):
    """Highest T at which solid enstatite is below the hull of everything else
    (liquid + other solids). Above it, enstatite has decomposed/melted."""
    def stable(T):
        return _compound_stable(db, p, "MS(enstatite)", T)[0]
    if not stable(lo):
        return None
    if stable(hi):
        return hi
    for _ in range(RES["nbis"]):
        m = 0.5 * (lo + hi)
        lo, hi = (m, hi) if stable(m) else (lo, m)
    return 0.5 * (lo + hi)


def eutectic_T(db, p, n1, n2, lo=1300.0, hi=2400.0):
    """Common-tangent eutectic between two solids (lean version of ph.eutectic)."""
    x1 = pdg.SOLIDS[n1][1] / (pdg.SOLIDS[n1][0] + pdg.SOLIDS[n1][1])
    x2 = pdg.SOLIDS[n2][1] / (pdg.SOLIDS[n2][0] + pdg.SOLIDS[n2][1])
    xa, xb = sorted((x1, x2))
    xs = np.linspace(xa + 0.02, xb - 0.02, RES["xeut"])

    def margin(T):
        g1 = pdg.solid_gibbs_per_formula_unit(n1, T)[0]
        g2 = pdg.solid_gibbs_per_formula_unit(n2, T)[0]
        inp = eq.build_inputs(db, p, T, components=COMPONENTS)
        gl = np.array([pdg.liquid_gibbs_per_formula_unit(inp, float(x), T) for x in xs])
        tie = g1 + (g2 - g1) * (xs - x1) / (x2 - x1)
        return (gl - tie).min()

    if margin(lo) > 0 and margin(hi) > 0:
        return None
    for _ in range(RES["neut"]):
        m = 0.5 * (lo + hi)
        lo, hi = (m, hi) if (margin(lo) < 0) == (margin(m) < 0) else (lo, m)
    return 0.5 * (lo + hi)


def gap(db, p, T, xlo=0.35, xhi=0.995, n=140):
    inp = eq.build_inputs(db, p, T, components=COMPONENTS)
    xs = np.linspace(xlo, xhi, n)
    g = np.array([act.delta_g_mix(inp, float(x)) for x in xs])
    H = []
    for x, y in zip(xs, g):
        while len(H) >= 2 and ((H[-1][0]-H[-2][0])*(y-H[-2][1])
                               - (H[-1][1]-H[-2][1])*(x-H[-2][0])) <= 0:
            H.pop()
        H.append((x, y))
    hx = [h[0] for h in H]
    gg = [(hx[i], hx[i+1]) for i in range(len(hx)-1) if hx[i+1]-hx[i] > 0.03]
    return gg[0] if gg else None


def all_invariants(db, p):
    return dict(
        forsterite=forsterite_T(db, p),
        peri_forst_eut=eutectic_T(db, p, "MgO(periclase)", "M2S(forsterite)"),
        enst_peri=enstatite_peritectic_T(db, p),
        encr_eut=eutectic_T(db, p, "MS(enstatite)", "SiO2(cristobalite)"),
        gap_mono=gap(db, p, T_MONO),
    )


def report(tag, pp):
    db, p, _ = build_db(pp)
    r = all_invariants(db, p)
    print(f"\n[{tag}]  params = "
          f"a00={pp[0]:.0f} b00={pp[1]:.4f} a10={pp[2]:.0f} b10={pp[3]:.4f} L_si={pp[4]:.0f}")
    rows = [("forsterite congruent", r["forsterite"], T_FORST),
            ("periclase-forst eutectic", r["peri_forst_eut"], T_PERI_FORST_EUT),
            ("enstatite peritectic", r["enst_peri"], T_ENST_PERI),
            ("enstatite-crist eutectic", r["encr_eut"], T_ENCR_EUT)]
    for name, v, tgt in rows:
        vs = f"{v:6.0f} K" if v else "  none "
        d = f"{v - tgt:+5.0f}" if v else "   - "
        print(f"    {name:28s} {vs}  meas {tgt:5.0f}  dT {d} K")
    gp = r["gap_mono"]
    print(f"    silica gap @1968K            "
          f"{f'{gp[0]:.3f}-{gp[1]:.3f}' if gp else 'none'}  (Greig 0.59-0.99)")
    return r


# targets and weights for the simultaneous fit (condensed invariants; the monotectic is
# reported, not fit - see the honest-limit discussion). Scale 1/100 K so residuals are O(1).
TARGETS = [("forsterite", T_FORST),
           ("peri_forst_eut", T_PERI_FORST_EUT),
           ("enst_peri", T_ENST_PERI),
           ("encr_eut", T_ENCR_EUT)]
PENALTY = 8.0  # residual (in 100-K units) charged when an invariant fails to compute


def residuals(pp):
    db, p, _ = build_db(pp)
    r = all_invariants(db, p)
    out = []
    for key, tgt in TARGETS:
        v = r[key]
        out.append((v - tgt) / 100.0 if v else PENALTY)
    # keep the gap anchored near Greig's MgO-side conjugate (0.59) so the fit cannot
    # trade the gap away to lower the silica-side invariants.
    gp = r["gap_mono"]
    out.append(((gp[0] - X_GAP_MG) / 0.05) if gp else PENALTY)
    return np.asarray(out, dtype=float)


def fit(p0, verbose=True):
    """Optimize the 4 effective parameters (a00, b00, a10, L_si); b10 stays 0 (its
    finite-difference step collapses at a zero start and it adds no leverage the other
    terms lack). p0 is the full 5-vector; b10 is carried through unchanged."""
    global RES
    RES = FAST
    b10 = p0[3]
    nfev = [0]

    def expand(q):
        return [q[0], q[1], q[2], b10, q[3]]

    def fun(q):
        nfev[0] += 1
        pp = expand(q)
        res = residuals(pp)
        if verbose:
            cost = 0.5 * float(res @ res)
            print(f"  eval {nfev[0]:3d}  cost={cost:8.3f}  "
                  f"a00={pp[0]:8.0f} b00={pp[1]:+7.3f} a10={pp[2]:8.0f} Lsi={pp[4]:8.0f}")
        return res

    q0 = [p0[0], p0[1], p0[2], p0[4]]
    sol = least_squares(fun, q0, diff_step=0.03, max_nfev=120,
                        x_scale=[5e4, 5.0, 5e4, 5e4])
    return expand(sol.x)


if __name__ == "__main__":
    import time, os
    if os.environ.get("HEPH_NO_FIXA"):
        pdg.USE_COMPOUND_CP = False       # Fix B alone: Neumann-Kopp solids + fitted liquid
        print("### Fix A OFF (Neumann-Kopp solids); fitting liquid only ###")
    p0 = [-79055.6, -3.5875, 30163.1, 0.0, 100958.1]

    RES = FAST
    t = time.time()
    residuals(p0)
    print(f"one FAST residual eval: {time.time()-t:.1f}s")

    RES = FINE
    report("Fix A on, v0.4 excess (not re-fit)", p0)

    pf = fit(p0)
    RES = FINE
    report("v0.5 simultaneous fit (Fix A + Fix B)", pf)
    print("\nfinal params:", [round(x, 2) for x in pf])
