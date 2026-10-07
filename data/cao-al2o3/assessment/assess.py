"""Assess the CaO-Al2O3 liquid against the Shepherd, Rankin & Wright (1909) liquidus and the
Rankin & Wright (1915) invariants, on the measured solids of build_dat.py (Bonnickson 1955
heat contents, hibonite from Geiger 1988).

The v0.1 fit scored the six invariants alone. Here each 1909 liquidus point is scored at the
lowest temperature where the liquid sits on the lower hull of the liquid and every solid, so a
metastable liquidus cannot count. 1909 temperatures are raised 13 K onto the 1911 scale of the
1915 paper (their CaAl2O4 melting, 1587 vs 1600 C). The excess temperature parts carry a prior of
0 +- 15 J/K.

Run:  python assess.py [--fit] [--p0=...]
"""
import csv
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[2] / "python"))

import build_dat                                   # noqa: E402
import v01_fit as v1                               # noqa: E402
from mqmqa.dbbuild import ExcessTerm               # noqa: E402

SCALE_1909 = 13.0
B_PRIOR = 15.0
# (p, q) of each term, as a + b T; p acts on CaO, q on AlO1.5
TERMS = [(0, 0), (1, 0), (0, 1), (2, 0), (0, 2)]

# DRY SLAGS ONLY. The invariants and fusion enthalpies are Jerebtsov & Mikhailov 2001 (DTA in argon).
# Rankin & Wright's 1915 binary invariants were measured in air and are not used. Of the 1909 liquidus
# (also in air) the three points in the Ca12Al14O33 field (51-53 wt% Al2O3) are left out, that
# compound needing absorbed water, and so is 75.22 wt%, in the dry hibonite field unknown in 1909.
PHASE = {"CaAl12O19": "CaAl12O19", "CaAl4O7": "CaAl4O7", "CaAl2O4": "CaAl2O4",
         "Ca3Al2O6": "Ca3Al2O6", "Al2O3": "Al2O3_corundum", "CaO": "CaO_solid"}
DRY = list(csv.DictReader(line for line in open(HERE / "jerebtsov_mikhailov2001.csv")
                          if not line.startswith("#")))

ROWS = [r for r in csv.DictReader(line for line in open(HERE / "shepherd_rankin_wright1909.csv")
                                  if not line.startswith("#"))
        if r["kind"] == "liquidus" and r["primary"] != "Ca12Al14O33" and float(r["Al2O3_wt"]) < 73.5]


# each aluminate's fusion enthalpy is taken at its own peritectic breakdown temperature
T_MELT = {PHASE[r["reaction"].split("=")[0].strip()]: float(r["T_C"]) + 273.15
          for r in DRY if r["kind"] == "peritectic"}


def phases_of(reaction):
    """The solids of a 'X = Y + L' or 'A + B = L' reaction, in model names."""
    names = [t.strip() for side in reaction.split("=") for t in side.split("+")]
    return [PHASE[n] for n in names if n != "L"]


def x_of(wt_al2o3):
    return v1.wt_to_x(100.0 - float(wt_al2o3))


def excess(pp):
    return [ExcessTerm(a=pp[2 * i], b=pp[2 * i + 1], p=p, q=q) for i, (p, q) in enumerate(TERMS)]


# Formation enthalpies from the oxides, shifted as assessed parameters under priors: CaAl4O7 by
# Geiger's own spread (Eqns 2 vs 3), the others by typical solution-calorimetry uncertainty, hibonite
# wider (its entropy rests on electrochemistry, Geiger Eqn 10).
SHIFTS = [("CaAl4O7", 4700.0), ("Ca3Al2O6", 3000.0), ("CaAl2O4", 3000.0), ("CaAl12O19", 5000.0)]
_BASE = {f: dict(build_dat.SOLIDS[f][2]) for f, _ in SHIFTS}
NAMES = [f"{c}{p}{q}" for p, q in TERMS for c in "ab"] + [f"dhf_{f}" for f, _ in SHIFTS] + ["ds_hibonite"]


# Hibonite's entropy of formation from the oxides is the least certain number here: no low-T
# calorimetry, Geiger's +24.3 J/K at 1100 K rests on two electrochemical studies, and estimates of
# S298 run from the oxide sum (344 J/K) to 432 J/K (Geiger 1988 section d). Assessed, 0 +- 15 J/K
# around Geiger's value. Machine-learned phonons are not used: they miss the measured entropies of
# the other aluminates (PROVENANCE.md); only a measurement settles this one.
DS_HIB_PRIOR = 15.0


# --ca2-entropy: the CaAl4O7 parameter shifts its entropy (J/K) instead of its enthalpy, to tell an
# enthalpy error (same at every T) from an entropy error (growing with T) in the dry diagram
CA2_ENTROPY = "--ca2-entropy" in sys.argv
CA2_DS_PRIOR = 10.0

# --cao-beta: the supercooled CaO(l) slope (data/cao-sio2 build_dat.CAO_LIQ_BETA, the value every
# CaO liquid reads) joins as the last parameter, 0 +- 5 J/K as for MgO(l)
CAO_BETA = "--cao-beta" in sys.argv
SIG_BETA = 5.0
I_HIB = 2 * len(TERMS) + len(SHIFTS)

# --ca2-plus=K: sensitivity test only. Raises the two invariants involving CaAl4O7 by K kelvin, the
# most favourable case for a kinetic (DTA lag, slow nucleation) explanation of the CaAl4O7 shift
CA2_PLUS = next((float(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--ca2-plus=")), 0.0)

# --dataset-offsets: one temperature correction per dataset (true = measured + offset), fitted under
# a prior of each dataset's stated accuracy, so a systematic bias (heating-rate lag, temperature
# scale, short quench holds) is carried by the dataset rather than by the thermodynamics. Last
# parameters, after the optional CaO(l) slope.
OFFSETS = "--dataset-offsets" in sys.argv
OFFSET_PRIOR = {"Jerebtsov & Mikhailov 2001 DTA": 10.0, "Shepherd, Rankin & Wright 1909": 25.0}
I_OFF = I_HIB + 1 + (1 if CAO_BETA else 0)


def offset(pp, k):
    return float(pp[I_OFF + k]) if OFFSETS else 0.0


def set_shifts(values, ds_hib=0.0):
    for (f, _), v in zip(SHIFTS, values):
        n_ca, n_al, _ = build_dat.SOLIDS[f]
        base = _BASE[f]["dHf"] - (build_dat.CA2_DHF_SHIFT if f == "CaAl4O7" else 0.0)
        extra = {"S298": _BASE[f]["S298"] + ds_hib} if f == "CaAl12O19" else {}
        if f == "CaAl4O7" and CA2_ENTROPY:
            extra, v = {"S298": _BASE[f]["S298"] + v}, 0.0
        build_dat.SOLIDS[f] = (n_ca, n_al, dict(_BASE[f], dHf=base + v, **extra))


# Each aluminate is a stable phase below its melting: none may fall apart into its solid neighbours
# at 800-1700 K. (On the measured values hibonite fails this above ~600 K, which drove the first
# dry fit to destabilize CaAl4O7 instead; C3A is checked from 800 K because the measured values put
# it only marginally stable below ~550 K, a range this assessment does not test.)
BREAKDOWNS = [("Ca3Al2O6", [(2, "CaO_solid"), (1, "CaAl2O4")], 1),
              ("CaAl2O4", [(1, "Ca3Al2O6"), (2, "CaAl4O7")], 5),
              ("CaAl4O7", [(4, "CaAl2O4"), (1, "CaAl12O19")], 5),
              ("CaAl12O19", [(1, "CaAl4O7"), (4, "Al2O3_corundum")], 1)]


def breakdown_dG(m, T):
    """{compound: G(products) - G(n compound), J}; > 0 means the compound is stable."""
    def G(f):
        g, _ = m.g_solid(f, T)
        return g * build_dat.solid_x_and_units(f)[1]
    return {f: sum(k * G(q) for k, q in prods) - n * G(f) for f, prods, n in BREAKDOWNS}


def model(pp):
    set_shifts(pp[2 * len(TERMS):I_HIB], ds_hib=pp[I_HIB])
    build_dat.CAO = build_dat.dbbuild.starter_component(
        "CaO", liq_beta=float(pp[I_HIB + 1]) if CAO_BETA else 0.0)
    path = Path(tempfile.gettempdir()) / f"_caal_assess_{os.getpid()}.dat"
    build_dat.build(excess(pp), out=path)
    return v1.Model(path)


def _hull(m, T, xs):
    pts = [(float(x), m.g_liq(float(x), T), "L") for x in xs]
    for name in build_dat.SOLIDS:
        g, x = m.g_solid(name, T)
        pts.append((x, g, name))
    pts.sort(key=lambda q: q[0])
    h = []
    for p in pts:
        while len(h) >= 2 and ((h[-1][0] - h[-2][0]) * (p[1] - h[-2][1])
                               - (h[-1][1] - h[-2][1]) * (p[0] - h[-2][0])) <= 1e-9:
            h.pop()
        h.append(p)
    return h


def liquidus_point(m, x, lo=1400.0, hi=2400.0, n=24):
    """(T, primary) at x: the lowest T where the liquid at x is on the lower hull."""
    x = round(float(x), 6)      # the grid is rounded; x must be one of its points exactly
    xs = np.unique(np.round(np.concatenate([np.linspace(0.02, 0.98, 49),
                                            x + np.linspace(-0.03, 0.03, 13)]), 6))
    xs = xs[(xs > 0) & (xs < 1)]

    def on_hull(T):
        return any(abs(q[0] - x) < 1e-9 and q[2] == "L" for q in _hull(m, T, xs))
    if on_hull(lo) or not on_hull(hi):
        return None, None
    for _ in range(n):
        mid = 0.5 * (lo + hi)
        lo, hi = (lo, mid) if on_hull(mid) else (mid, hi)
    h = _hull(m, lo, xs)
    for a, b in zip(h, h[1:]):
        if a[0] <= x <= b[0]:
            solids = [q[2] for q in (a, b) if q[2] != "L"]
            return hi, "+".join(solids) or None
    return hi, None


S_FUS = 25.0     # J/K per cation: turns a driving force into a liquidus offset in kelvin


def driving_forces(m, x, T, h=1e-4):
    """G of each solid above the liquid's tangent at (x, T), J per cation; < 0 means the solid
    is more stable than that liquid."""
    gl = m.g_liq(x, T)
    dg = (m.g_liq(x + h, T) - m.g_liq(x - h, T)) / (2 * h)
    out = {}
    for name in build_dat.SOLIDS:
        g, xs = m.g_solid(name, T)
        out[name] = g - (gl + dg * (xs - x))
    return out


def fusion_enthalpy(m, name, T, h=0.5):
    """H(liquid of the compound's composition) - H(compound) at T, J per formula."""
    _, x = m.g_solid(name, T)
    _, units = build_dat.solid_x_and_units(name)
    def H(g):
        return g(T) - T * (g(T + h) - g(T - h)) / (2 * h)
    return units * (H(lambda t: m.g_liq(x, t)) - H(lambda t: m.g_solid(name, t)[0]))


def residuals(pp, detail=False):
    m = model(pp)
    out, rows = [], []

    def add(tag, r, info):
        out.append(r)
        rows.append((tag, r, info))

    for r in DRY:
        if r["kind"] == "fusion":
            f = PHASE[r["reaction"].split("=")[0].strip()]
            T = T_MELT[f]
            dh = fusion_enthalpy(m, f, T) / 1000.0
            meas, sig = float(r["dH_kJ_per_mol"]), float(r["dH_sigma"])
            add(f"dH_fus {f}", (dh - meas) / sig, f"{dh:.0f}/{meas:.0f} kJ at {T:.0f} K")
            continue
        Tm, sig = float(r["T_C"]) + 273.15, float(r["T_sigma_K"])
        if CA2_PLUS and "CaAl4O7" in r["reaction"]:
            Tm += CA2_PLUS
        Tm += offset(pp, 0)
        x = v1.wt_to_x(float(r["CaO_wt"]))
        df = driving_forces(m, x, Tm)
        on = phases_of(r["reaction"])
        # both solids of the invariant sit on the liquid's tangent at the measured liquid
        for f in on:
            add(f"{r['kind']} {r['reaction']}: {f}", df[f] / (S_FUS * sig),
                f"dG {df[f]:+.0f} J/cation at {Tm:.0f} K")
        for name, d in df.items():
            if name not in on:
                add(f"   {name} above the liquid", min(d, 0.0) / (S_FUS * sig), f"dG {d:+.0f}")
    for r in ROWS:
        Tm = float(r["T_C_1909"]) + 273.15 + SCALE_1909 + offset(pp, 1)
        x, sig = x_of(r["Al2O3_wt"]), float(r["sigma_K"])
        # the observed primary phase sits on the liquid's tangent at the measured point; every
        # other solid sits above it (driving forces over a typical fusion entropy -> kelvin)
        df = driving_forces(m, x, Tm)
        add(f"liq {r['Al2O3_wt']} wt% {r['primary']}", df[r["primary"]] / (S_FUS * sig),
            f"dG {df[r['primary']]:+.0f} J/cation at {Tm:.0f} K")
        for name, d in df.items():
            if name != r["primary"]:        # a fixed-length residual: zero unless it is violated
                add(f"   {name} above the liquid", min(d, 0.0) / (S_FUS * sig), f"dG {d:+.0f}")
    for i, name in enumerate(NAMES):
        if name.startswith("b"):
            add(f"prior {name}", pp[i] / B_PRIOR, f"{pp[i]:.2f}")
    for (f, sig), v in zip(SHIFTS, pp[2 * len(TERMS):I_HIB]):
        if f == "CaAl4O7" and CA2_ENTROPY:
            add("prior CaAl4O7 S298 shift", v / CA2_DS_PRIOR, f"{v:.2f} J/K")
            continue
        add(f"prior {f} dHf shift", v / sig, f"{v:.0f} J per formula")
    add("prior hibonite dS_ox shift", pp[I_HIB] / DS_HIB_PRIOR, f"{pp[I_HIB]:.1f} J/K")
    if CAO_BETA:
        add("prior CaO(l) beta", pp[I_HIB + 1] / SIG_BETA, f"{pp[I_HIB + 1]:.2f} J/K")
    if OFFSETS:
        for k, (name, sig) in enumerate(OFFSET_PRIOR.items()):
            add(f"prior offset {name}", offset(pp, k) / sig, f"{offset(pp, k):+.1f} K")
    for T in (800.0, 1300.0, 1700.0):
        for f, dg in breakdown_dG(m, T).items():
            add(f"   {f} stable at {T:.0f} K", min(dg, 0.0) / 2000.0, f"dG {dg / 1000:+.1f} kJ")
    res = np.asarray(out, float)
    return (res, rows) if detail else res


def report(pp):
    res, rows = residuals(pp, detail=True)
    for tag, r, info in rows:
        if tag.startswith("   ") and r == 0.0:
            continue
        print(f"  {tag:40s} {info:44s} r={r:+6.2f}")
    print(f"  total cost = {0.5 * float(res @ res):.2f}   RMS residual = {np.sqrt(np.mean(res ** 2)):.2f}")


if __name__ == "__main__":
    p0 = [v1.STORED[0], v1.STORED[1], v1.STORED[2], 0.0, 0.0, 0.0, build_dat.CA2_DHF_SHIFT, 0.0, 0.0, 0.0, 0.0]
    for arg in sys.argv:
        if arg.startswith("--p0="):
            p0 = [float(v) for v in arg[5:].split(",")]
    if "--fit" in sys.argv:
        scale = np.array([5e4, 10.0] * len(TERMS) + [5000.0] * len(SHIFTS) + [10.0]
                         + ([10.0] if CAO_BETA else []) + ([10.0, 10.0] if OFFSETS else []))
        if CA2_ENTROPY:
            scale[2 * len(TERMS)] = 10.0
        n = [0]

        # solve in u = 1 + p/scale so a zero start still gets a real finite-difference step
        def fun(u):
            n[0] += 1
            r = residuals((u - 1.0) * scale)
            print(f"  eval {n[0]:3d} cost={0.5 * float(r @ r):.2f} p0="
                  + ",".join(f"{v:.6g}" for v in (u - 1.0) * scale), flush=True)
            return r
        u = least_squares(fun, 1.0 + np.asarray(p0) / scale, diff_step=0.05, max_nfev=60,
                          ftol=1e-4, xtol=1e-4).x
        p0 = list((u - 1.0) * scale)
    report(p0)
    print("\n  params:", dict(zip(NAMES + (["cao_liq_beta"] if CAO_BETA else [])
                                  + (["off_JM2001_K", "off_1909_K"] if OFFSETS else []),
                                  [round(float(v), 2) for v in p0])))
