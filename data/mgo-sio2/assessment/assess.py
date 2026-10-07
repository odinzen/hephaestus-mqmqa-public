"""CALPHAD assessment of the MgO-SiO2 liquid: fit the liquid excess parameters to the
WHOLE weighted experimental dataset simultaneously (invariants + immiscibility binodal +
consolute + mixing enthalpy), instead of point-fitting a few landmarks.

Liquid excess in the verified equivalent-fraction basis: each term is L*Y_SiO2^q with
L = a + b*T (a = enthalpy omega, b = the entropy/temperature part eta), on the (Mg,Si,O,O)
quadruplet. A rich silica-side polynomial (q = 0,1,3,5,7) mirrors the published
Wu/Eriksson/Pelton form (const + linear ordering + high-power silica, each with its own
temperature dependence). Forsterite and enstatite are the shared olivine/opx endmembers
(data/olivine/endmembers.py, Robie-Hemingway); the enstatite high-T correction defined
there is co-assessed here, since R&H fit orthoenstatite only to 1000 K.

Run:  PYTHONPATH=python python assess.py [--fit] [--write]
"""
import os
import sys
import tempfile
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[2] / "python"))

import build_dat as bd
import mqmqa
import phase_diagram as pdg
import phase_hull as ph
import v05_fit as vf
from mqmqa import equilibrium as eq
import _activity as act
import dataset as ds

pdg.USE_SHARED_SOLIDS = True
COMP = pdg.COMPONENTS

# excess term powers q (each carries a + b*T). Index maps to the parameter vector as
# [a_q0, b_q0, a_q1, b_q1, ...]. Then 2 SOLID parameters (co-assessed, bounded):
#   [-2] SiO2 dCp_fus (J/mol/K, 0..20; liquid silica Cp above cristobalite)
#   [-1] enstatite high-T correction at 1830 K (J per Mg2Si2O6; endmembers.ENSTATITE_DG_1830)
# (p, q): Y_MgO^p Y_SiO2^q, silica powers only. An MgO-side term (2, 0) was tried 2026-09-30 and
# dropped: with Fe and Mg in one group it acts on Fe-Si pairs in the ternary too, and it put the
# FeO-MgO-SiO2 Fe-rich olivine liquidus 30-50 K low, without making forsterite congruent.
# (0, 2), 2026-10-01: in a binary any MgO-power term is a combination of silica powers 0-2, so
# this is the MgO-side freedom the stable liquidus needs, extrapolated into the ternaries like the
# other silica terms (not through the Fe+Mg group). Its temperature part has a loose prior so the
# data decide whether the MgO-rich melt is stabilized by entropy or by enthalpy.
TERMS = [(0, 0), (0, 1), (0, 3), (0, 5), (0, 7), (0, 2), (4, 0)]
# Trial terms for model-form experiments, e.g. MGO_SIO2_EXTRA_TERMS="4,0" (an MgO-power term needs
# silica power 4, which the list above lacks); empty by default.
TERMS += [tuple(int(v) for v in t.split(",")) for t in os.environ.get("MGO_SIO2_EXTRA_TERMS", "").split(";") if t]
# Terms that also carry an excess heat capacity (build_dat.excess_coeffs), e.g.
# MGO_SIO2_CP_TERMS="0,7": a + b*T mixing terms cannot give the flat measured top of the two-liquid
# dome (2026-10-05). Each stored with a heat capacity, plus any named here; its value follows the term's
# a and b in the parameter vector.
CP_TERMS = [(p, q) for p, q, *_, dcp in bd.assessed_terms() if dcp]
CP_TERMS += [tuple(int(v) for v in t.split(",")) for t in os.environ.get("MGO_SIO2_CP_TERMS", "").split(";") if t]
WIDTH = [3 if t in CP_TERMS else 2 for t in TERMS]
OFFSET = [int(v) for v in np.cumsum([0] + WIDTH[:-1])]
B_PRIOR_TERM = {(0, 2): 40.0}
QPOW = [q for _, q in TERMS]
NLIQ = sum(WIDTH)
B_PRIOR = 15.0          # J/mol/K, on each excess term's temperature part
# J/mol/K, on an excess term's heat capacity. 40 on (0, 7) gives the liquid about 2 J/mol/K of excess
# heat capacity near x 0.85 (100 gives 5.5 there and 7.5 at x 0.7 on (0, 5); probed on fit M2, 2026-10-05)
CP_PRIOR = 40.0
# after the liquid: MgO(l) heat capacity above the crystal's, SiO2 dCp_fus, enstatite high-T correction
# after the liquid: the Mg-Si ordering composition as an offset from 1/3 (see build_dat.MGSI_SRO_X),
# then the three below
LOWER = [-np.inf] * NLIQ + [-0.05, 0.0, 0.0, 0.0]
UPPER = [np.inf] * NLIQ + [0.03, 60.0, 1e-6, 40000.0]      # dCp_fus pinned: SiO2(l) is shared by every file
# liquid MgO Cp 78 +- 15 J/mol/K near Tm from first-principles MD (de Koker & Stixrude 2009), less the
# crystal's Cp at Tm from the periclase fit: the prior on MGO_LIQ_DCP. (Until 2026-10-02 a free
# below-Tm slope here went to 8.7 J/K, a fusion enthalpy near 50 kJ no independent source supports.)
_MGO = bd.OXIDES["MgO"]
DCP_PRIOR = (78.0 - (_MGO["a"] + _MGO["b"] * _MGO["Tm"] + _MGO["c"] / _MGO["Tm"] ** 2), 15.0)


def set_enstatite(dg_1830):
    pdg.em.ENSTATITE_DG_1830 = dg_1830
    pdg.em.ENSTATITE_HT_B = dg_1830 / (1830.0 - pdg.em.ENSTATITE_T_BREAK)


def z_mixed(pp):
    return bd.mgsi_mixed_z(1.0 / 3.0 + pp[NLIQ]) or False


def term_params(pp):
    """(p, q, a, b, dcp) of each liquid term in parameter vector pp."""
    return [(pw, q, pp[o], pp[o + 1], pp[o + 2] if w == 3 else 0.0)
            for (pw, q), o, w in zip(TERMS, OFFSET, WIDTH)]


def liquid_excess(pp, li=(1, 2, 3, 3)):
    """The liquid's Q terms for pp on quadruplet li (MgO cation first), as build_dat writes them.
    Every file the fits build (binary, CaO-MgO-SiO2 face, FeO-MgO-SiO2) takes its terms from here."""
    return [dict(code="Q", li=list(li), exp=[pw, q, 0, 0], coeffs=bd.excess_coeffs(a, b, dcp))
            for pw, q, a, b, dcp in term_params(pp)]


def assessed_liquid():
    """The stored liquid (build_dat.ASSESSED_EXCESS) as the first NLIQ parameters; a term in
    TERMS that is not stored starts at zero."""
    stored = {(p, q): (a, b, dcp) for p, q, a, b, dcp in bd.assessed_terms()}
    out = []
    for t, w in zip(TERMS, WIDTH):
        out += list(stored.get(t, (0.0, 0.0, 0.0))[:w])
    return out


def build_db(pp):
    excess = liquid_excess(pp)
    dcp_fus, ens_dg = pp[-2], pp[-1]
    set_enstatite(ens_dg)
    import os
    # scratch copy per process (parallel fits), outside the repository
    path = Path(tempfile.gettempdir()) / f"_mgo-sio2_assess_{os.getpid()}.dat"
    path.write_text(bd.build(excess, version="assess", dcp_fus_sio2=dcp_fus, mgo_liq_dcp=pp[-3],
                             z_mixed=z_mixed(pp)), encoding="ascii")
    db = mqmqa.Database.read(str(path))
    return db, db.phase_index("MGO-SIO2-LIQUID"), excess


def cristobalite_liquidus_T(db, p, xL, lo=1750.0, hi=2600.0):
    """T at which cristobalite (x=1) sits on the common tangent to the liquid at xL -
    i.e. the cristobalite liquidus at composition xL. Targeting this at high silica
    (~0.98 -> ~1970 K) directly fights the too-high cristobalite preemption."""
    h = 3e-4
    def f(T):
        inp = eq.build_inputs(db, p, float(T), components=COMP)
        gL = pdg.liquid_gibbs_per_formula_unit(inp, xL, float(T))
        gLp = pdg.liquid_gibbs_per_formula_unit(inp, xL + h, float(T))
        gLm = pdg.liquid_gibbs_per_formula_unit(inp, xL - h, float(T))
        slope = (gLp - gLm) / (2 * h)
        tangent_at_1 = gL + (1.0 - xL) * slope           # extrapolate tangent to x=1
        gC = pdg.solid_gibbs_per_formula_unit("SiO2(cristobalite)", float(T))[0]
        return gC - tangent_at_1                           # <0: cristobalite below -> stable
    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:
        return None
    for _ in range(45):
        m = 0.5 * (lo + hi)
        lo, hi = (m, hi) if f(lo) * f(m) > 0 else (lo, m)
    return 0.5 * (lo + hi)


def monotectic_T(db, p, lo=1850.0, hi=2150.0):
    """Temperature at which cristobalite touches the two-liquid common tangent (silica + L1
    + L2), or None with no gap at lo; outside the bracket, the nearer edge."""
    def f(T):
        gap = vf.gap(db, p, T)
        if gap is None:
            return None
        x1, x2 = gap
        inp = eq.build_inputs(db, p, T, components=COMP)
        g = lambda x: pdg.liquid_gibbs_per_formula_unit(inp, x, T)
        chord = (g(x2) - g(x1)) / (x2 - x1)
        return (pdg.solid_gibbs_per_formula_unit("SiO2(cristobalite)", T)[0]
                - (g(x2) + (1.0 - x2) * chord))
    flo = f(lo)
    if flo is None:
        return None
    fhi = f(hi)
    while fhi is None and hi > lo + 25.0:
        hi -= 25.0
        fhi = f(hi)
    if fhi is None or flo * fhi > 0:
        return lo if (fhi is None or flo > 0) else hi
    for _ in range(40):
        m = 0.5 * (lo + hi)
        lo, hi = (m, hi) if f(lo) * f(m) > 0 else (lo, m)
    return 0.5 * (lo + hi)


def fusion_enthalpy(db, p, solid, T, dT=5.0):
    """H(liquid) - H(solid) at T for one formula of the compound (J), the liquid at the
    compound's composition; H = G - T dG/dT, by central difference."""
    n_mgo, n_sio2 = pdg.SOLIDS[solid][:2]
    x = n_sio2 / (n_mgo + n_sio2)

    def dg(TT):
        inp = eq.build_inputs(db, p, TT, components=COMP)
        return pdg.liquid_gibbs_per_formula_unit(inp, x, TT) - pdg.solid_gibbs_per_formula_unit(solid, TT)[0]
    return (n_mgo + n_sio2) * (dg(T) - T * (dg(T + dT) - dg(T - dT)) / (2 * dT))


def dh_mix(db, p, x, T=2100.0, dT=40.0):
    g = lambda TT: act.delta_g_mix(eq.build_inputs(db, p, TT, components=COMP), x)
    return (g(T) - T * (g(T + dT) - g(T - dT)) / (2 * dT)) / 1000.0


def consolute(db, p, lo=1990.0, hi=3200.0, step=35.0):
    Tclose, xc, last = None, None, vf.gap(db, p, lo)
    T = lo
    while T <= hi:
        g = vf.gap(db, p, T)
        if g is None:
            Tclose, xc = T, (0.5 * (last[0] + last[1]) if last else None)
            break
        last = g
        T += step
    return Tclose, xc


def _hull(db, p, T, xs):
    inp = eq.build_inputs(db, p, T, components=COMP)
    pts = [(float(x), pdg.liquid_gibbs_per_formula_unit(inp, float(x), T), "L") for x in xs]
    for name in pdg.SOLIDS:
        g, xc = pdg.solid_gibbs_per_formula_unit(name, T)
        pts.append((xc, g, name))
    return ph.lower_hull(pts)


def liquidus_point(db, p, x, lo=1600.0, hi=2400.0, n=26):
    """(T, primary solid) at composition x: the lowest T at which the liquid at x is on the
    lower hull of the liquid and every solid, so a metastable liquidus cannot score."""
    xs = np.unique(np.round(np.concatenate([np.linspace(0.02, 0.985, 50),
                                            x + np.linspace(-0.03, 0.03, 13)]), 6))
    def on_hull(T):
        return any(abs(q[0] - x) < 1e-9 and q[2] == "L" for q in _hull(db, p, T, xs))
    if on_hull(lo) or not on_hull(hi):
        return None, None
    for _ in range(n):
        m = 0.5 * (lo + hi)
        lo, hi = (lo, m) if on_hull(m) else (m, hi)
    left, right = ph.hull_bracket(_hull(db, p, lo, xs), x)
    solids = [q[2] for q in (left, right) if q[2] != "L"]
    # The sampled hull only finds the primary phase: with the liquid on a 0.005 grid it read the
    # steep periclase liquidus 16 K low at x 0.265 (2026-10-02). The temperature comes from the
    # exact saturation of that phase.
    # A tangent at a composition inside the two-liquid gap is metastable (x 0.588 sits in it at
    # the monotectic), so the refined value stands only where the liquid at x is on its own hull.
    sat = [t for t in (saturation_T(db, p, s, x, hi - 80.0, hi + 80.0) for s in solids)
           if t and _liquid_on_own_hull(db, p, x, t)]
    T = max(sat) if sat else hi
    return T, (solids[0] if len(solids) == 1 else "+".join(solids) or None)


def eutectic_pe_fo(db, p, lo=0.12, hi=0.33, n=16):
    """(T, x) of the periclase-forsterite eutectic: where the two saturation curves cross on
    the MgO side of forsterite, with the liquid stable there. (None, None) if they do not."""
    def gap(x):
        return (saturation_T(db, p, "MgO(periclase)", x, 1500.0, 3300.0, clamp=True)
                - saturation_T(db, p, "M2S(forsterite)", x, 1500.0, 3300.0, clamp=True))
    if gap(lo) <= 0 or gap(hi) >= 0:
        return None, None
    for _ in range(n):
        m = 0.5 * (lo + hi)
        lo, hi = (m, hi) if gap(m) > 0 else (lo, m)
    x = 0.5 * (lo + hi)
    T = saturation_T(db, p, "M2S(forsterite)", x, 1500.0, 3300.0)
    return (T, x) if T and _liquid_on_own_hull(db, p, x, T) else (None, None)


def _liquid_on_own_hull(db, p, x, T):
    x = round(x, 6)                                         # the grid is rounded too
    xs = np.unique(np.round(np.append(np.linspace(0.002, 0.998, 499), x), 6))
    inp = eq.build_inputs(db, p, T, components=COMP)
    pts = [(float(v), pdg.liquid_gibbs_per_formula_unit(inp, float(v), T), "L") for v in xs]
    return any(abs(q[0] - x) < 1e-9 for q in ph.lower_hull(pts))


def saturation_T(db, p, solid, x, lo, hi, h=1e-4, clamp=False):
    """T at which `solid` touches the tangent to the liquid at x. Not bracketed: None, or
    with clamp the end of the window it lies beyond."""
    def above_tangent(T):
        inp = eq.build_inputs(db, p, T, components=COMP)
        g = lambda v: pdg.liquid_gibbs_per_formula_unit(inp, v, T)
        gs, xs = pdg.solid_gibbs_per_formula_unit(solid, T)
        return gs - (g(x) + (g(x + h) - g(x - h)) / (2 * h) * (xs - x))
    f_lo, f_hi = above_tangent(lo), above_tangent(hi)
    if f_lo * f_hi > 0:
        return (hi if f_hi < 0 else lo) if clamp else None
    for _ in range(30):
        m = 0.5 * (lo + hi)
        f_m = above_tangent(m)
        lo, f_lo, hi = (m, f_m, hi) if f_m * f_lo > 0 else (lo, f_lo, m)
    return 0.5 * (lo + hi)


def eutectic_x(db, p, T, n1, n2):
    """Liquid composition on the two-solid chord at the eutectic T."""
    g1, x1 = pdg.solid_gibbs_per_formula_unit(n1, T)
    g2, x2 = pdg.solid_gibbs_per_formula_unit(n2, T)
    xs = np.linspace(min(x1, x2) + 0.005, max(x1, x2) - 0.005, 400)
    inp = eq.build_inputs(db, p, T, components=COMP)
    gl = np.array([pdg.liquid_gibbs_per_formula_unit(inp, float(x), T) for x in xs])
    return float(xs[np.argmin(gl - (g1 + (g2 - g1) * (xs - x1) / (x2 - x1)))])


def peritectic_x(db, p, T):
    """Liquid the forsterite tangent touches at the enstatite peritectic T."""
    gf, xf = pdg.solid_gibbs_per_formula_unit("M2S(forsterite)", T)
    xs = np.linspace(0.45, 0.62, 350)
    inp = eq.build_inputs(db, p, T, components=COMP)
    gl = np.array([pdg.liquid_gibbs_per_formula_unit(inp, float(x), T) for x in xs])
    return float(xs[np.argmin((gl - gf) / (xs - xf))])


def residuals(pp, detail=False):
    db, p, _ = build_db(pp)
    r = vf.all_invariants(db, p)
    out, rows = [], []

    def add(tag, res, info=""):
        out.append(res)
        rows.append((tag, res, info))

    # invariant temperatures
    inv_map = {"periclase-forsterite eutectic": "peri_forst_eut",
               "forsterite congruent": "forsterite",
               "enstatite peritectic": "enst_peri",
               "enstatite-cristobalite eutectic": "encr_eut"}
    # The MgO side is scored on the stable hull: the liquidus at the measured eutectic liquid and
    # at forsterite. The pairwise invariants vf.all_invariants gives there let the periclase field
    # run past forsterite unseen (2026-10-01: periclase first up to x 0.35, liquidus 2794 K at the
    # eutectic composition, measured 2123 K).
    # The measured periclase-forsterite eutectic (T, x) is scored as the stable liquidus at its x
    # and the composition where the two saturation curves cross. The liquidus reading is the
    # guard: when the periclase field runs toward forsterite it misses by hundreds of K, where the
    # eutectic T alone moved little (2026-10-04: the three-way fits sat 460 K high there at 3 sigma
    # cost). The crossing x keeps a fit from matching the liquidus with the eutectic misplaced.
    # MGO_SIO2_PE_SIGMA_SCALE widens both sigmas of this one 1914 point, for testing how much the
    # fit leans on it (default 1, the stored assessment).
    d = dict(ds.INVARIANTS[0])
    scale = float(os.environ.get("MGO_SIO2_PE_SIGMA_SCALE", "1"))
    d["sigT"], d["sigx"] = d["sigT"] * scale, d["sigx"] * scale
    T, prim = liquidus_point(db, p, round(d["x"], 6), 1600.0, 3200.0)
    ok = prim is not None and all(s in d["solids"] for s in prim.split("+"))
    add(f"T[{d['name']}] (stable liquidus)", ((T - d["T"]) / d["sigT"]) if T else vf.PENALTY,
        f"{T:.0f}/{d['T']:.0f} {prim}{'' if ok else ' (want ' + '/'.join(d['solids']) + ')'}" if T else "none")
    Te, xe = eutectic_pe_fo(db, p)
    add(f"x[{d['name']}]", ((xe - d["x"]) / d["sigx"]) if Te else vf.PENALTY,
        f"{xe:.3f}/{d['x']:.3f} at {Te:.0f} K" if Te else "none (periclase field past forsterite?)")
    for d in ds.INVARIANTS[1:2]:
        T, prim = liquidus_point(db, p, round(d["x"], 6), 1600.0, 3200.0)
        ok = prim is not None and all(s in d["solids"] for s in prim.split("+"))
        add(f"T[{d['name']}] (stable liquidus)", ((T - d["T"]) / d["sigT"]) if T else vf.PENALTY,
            f"{T:.0f}/{d['T']:.0f} {prim}{'' if ok else ' (want ' + '/'.join(d['solids']) + ')'}"
            if T else "none")
    for d in ds.INVARIANTS[2:]:
        v = r[inv_map[d["name"]]]
        add(f"T[{d['name']}]", ((v - d["T"]) / d["sigT"]) if v else vf.PENALTY,
            f"{v:.0f}/{d['T']:.0f}" if v else "none")

    # silica-side invariant liquid compositions
    for d, key, fx in [(ds.INVARIANTS[3], "encr_eut",
                        lambda T: eutectic_x(db, p, T, "MS(enstatite)", "SiO2(cristobalite)")),
                       (ds.INVARIANTS[2], "enst_peri", lambda T: peritectic_x(db, p, T))]:
        T = r[key]
        xv = fx(T) if T else None
        add(f"x[{d['name']}]", ((xv - d["x"]) / d["sigx"]) if xv else vf.PENALTY,
            f"{xv:.3f}/{d['x']:.3f}" if xv else "none")

    # liquidus between the invariants
    for d in ds.LIQUIDUS:
        T, prim = liquidus_point(db, p, d["x"])
        ok = prim == d["phase"]
        add(f"liq@x{d['x']:.3f}", ((T - d["T"]) / d["sig"]) if T else vf.PENALTY,
            f"{T:.0f}/{d['T']:.0f} {prim}{'' if ok else ' (want ' + d['phase'] + ')'}" if T else "none")

    # immiscibility binodal conjugates (isolated binodal at each measured T)
    for d in ds.BINODAL:
        g = vf.gap(db, p, d["T"])
        if g:
            add(f"bin_lo@{int(d['T'])}", (g[0] - d["x_lo"]) / d["sig"], f"{g[0]:.2f}/{d['x_lo']:.2f}")
            add(f"bin_hi@{int(d['T'])}", (g[1] - d["x_hi"]) / d["sig"], f"{g[1]:.2f}/{d['x_hi']:.2f}")
        else:
            add(f"bin@{int(d['T'])}", vf.PENALTY, "none"); add(f"bin2@{int(d['T'])}", vf.PENALTY, "none")

    # consolute (dome height + critical composition)
    Tc, xc = consolute(db, p)
    for d in ds.CONSOLUTE:
        if Tc:
            add("consolute_T", (Tc - d["T"]) / d["sigT"], f"{Tc}/{d['T']:.0f}")
        else:
            # still open at 3200 K: charge the scan's top plus the width left there, so the
            # fit feels which way closes it (a flat penalty it would ignore)
            g = vf.gap(db, p, 3200.0)
            w = (g[1] - g[0]) if g else 0.0
            add("consolute_T", (3200.0 - d["T"]) / d["sigT"] + w / 0.05, f"open at 3200 K, width {w:.2f}")
        add("consolute_x", ((xc - d["x_c"]) / d["sigx"]) if (Tc and xc) else 0.0,
            f"{xc:.2f}/{d['x_c']:.2f}" if xc else "-")

    # cristobalite liquidus at high silica = the preemption constraint. At the monotectic
    # cristobalite coexists with the silica-rich liquid (~0.985) at ~1968 K; our models put
    # this ~340 K too high (dome preempts). Target it directly.
    # (a liquidus read at x = 0.90 would sit inside the model's gap, so the monotectic
    # itself is scored below instead)
    for xL, Ttgt, sig in [(0.985, 1975.0, 40.0)]:
        Tc = cristobalite_liquidus_T(db, p, xL)
        add(f"crist_liq@x{xL:.2f}", ((Tc - Ttgt) / sig) if Tc else vf.PENALTY,
            f"{Tc:.0f}/{Ttgt:.0f}" if Tc else "none")
    Tm = monotectic_T(db, p)
    add("monotectic T (silica + L1 + L2)", ((Tm - vf.T_MONO) / 10.0) if Tm else vf.PENALTY,
        f"{Tm:.0f}/{vf.T_MONO:.0f}" if Tm else "none")

    # the temperature parts stay modest: a large b on a high silica power keeps the two-liquid
    # field open to 3200 K (2026-09-30), which no measurement supports
    for pw, q, _, b, dcp in term_params(pp):
        add(f"prior b(p={pw},q={q})", b / B_PRIOR_TERM.get((pw, q), B_PRIOR), f"{b:.1f}/0")
        if (pw, q) in CP_TERMS:
            add(f"prior dCp(p={pw},q={q})", dcp / CP_PRIOR, f"{dcp:.1f}/0 J/K")

    add("prior MgO(l) dCp", (pp[-3] - DCP_PRIOR[0]) / DCP_PRIOR[1], f"{pp[-3]:.1f}/{DCP_PRIOR[0]:.1f} J/K")

    # mixing enthalpy
    for d in ds.DH_MIX:
        add(f"dHmix@x{d['x']:.2f}", (dh_mix(db, p, d["x"]) - d["value"]) / d["sig"],
            f"{dh_mix(db,p,d['x']):.1f}/{d['value']:.1f}")

    # compound fusion enthalpies, at the measured melting point
    for d in ds.FUSION:
        h = fusion_enthalpy(db, p, d["solid"], d["T"]) / 1000.0
        add(f"dHfus[{d['solid']}]", (h - d["dH"]) / d["sig"], f"{h:.1f}/{d['dH']:.1f} kJ")

    return (np.asarray(out, float), rows) if detail else np.asarray(out, float)


def _init_worker():
    vf.RES = vf.FAST


def _res_fast(pp):
    return residuals(np.asarray(pp, float))


def fit(p0, workers=13):
    """Levenberg-style least squares with the forward-difference Jacobian computed in
    parallel, one process per parameter. Each step is 3% of the parameter's typical size,
    not of its value, so a parameter starting at zero still moves."""
    from multiprocessing import Pool
    _init_worker()
    typ = []
    for w in WIDTH:
        typ += [2e4, 10.0, 10.0][:w]
    typ += [0.005, 10.0, 10.0, 2000.0]
    typ = np.array(typ)
    lo, hi = np.array(LOWER, float), np.array(UPPER, float)
    n = [0]
    with Pool(workers, initializer=_init_worker) as pool:
        cache = {}

        def fun(x):
            key = tuple(np.round(x, 9))
            if key not in cache:
                cache[key] = _res_fast(x)
                n[0] += 1
                r = cache[key]
                print(f"  eval {n[0]:3d}  cost={0.5 * float(r @ r):8.3f}  p0="
                      + ",".join(f"{v:.6g}" for v in x), flush=True)
            return cache[key]

        def jac(x):
            h = 0.03 * np.maximum(np.abs(x), typ)
            h = np.where(x + h > hi, -h, h)
            pts = [x + np.eye(len(x))[i] * h[i] for i in range(len(x))]
            cols = pool.map(_res_fast, pts)
            f0 = fun(x)
            return np.column_stack([(c - f0) / hi_ for c, hi_ in zip(cols, h)])

        sol = least_squares(fun, np.asarray(p0, float), jac=jac, x_scale=typ,
                            bounds=(lo, hi), max_nfev=40, ftol=1e-4, xtol=1e-4)
    return sol.x


def report(pp, write=False):
    vf.RES = vf.FINE
    res, rows = residuals(pp, detail=True)
    print("\n  per-datum residuals (model/target):")
    for tag, rr, info in rows:
        print(f"    {tag:26s} {info:14s}  r={rr:+6.2f}")
    print(f"  Mg-Si ordering peaks at x_SiO2 = {1.0 / 3.0 + pp[NLIQ]:.4f}")
    print(f"\n  total cost = {0.5*float(res@res):.3f}   RMS residual = {np.sqrt(np.mean(res**2)):.2f}")
    for pw, q, a, b, dcp in term_params(pp):
        if (pw, q) in CP_TERMS:
            print(f"  excess heat capacity on (p={pw}, q={q}): {dcp:.2f} J/mol/K (a, b at {bd.XS_CP_T0:.0f} K)")
    if write:
        _, _, excess = build_db(pp)
        (HERE.parent / "MgO-SiO2-liquid.dat").write_text(
            bd.build(excess, version="assess", dcp_fus_sio2=pp[-2], mgo_liq_dcp=pp[-3],
                     z_mixed=z_mixed(pp)), encoding="ascii")
        print("  wrote MgO-SiO2-liquid.dat; enstatite correction to record in "
              f"data/olivine/endmembers.py: ENSTATITE_DG_1830 = {pp[-1]:.1f}")


if __name__ == "__main__":
    # Assessed 2026-09-29 on the shared Robie-Hemingway forsterite/enstatite and the corrected
    # SiO2, after the phase model stopped applying the quartz correction to pure cristobalite
    # (which had made it 2.3 kJ too stable): total cost 30.5, RMS 1.75. --fit re-runs from it.
    # The liquid lives in build_dat.ASSESSED_EXCESS and the enstatite correction in
    # data/olivine/endmembers.py; the SiO2 dCp_fus assessed to zero.
    ASSESSED = assessed_liquid() + [bd.MGSI_SRO_X - 1.0 / 3.0, bd.MGO_LIQ_DCP, 0.0, pdg.em.ENSTATITE_DG_1830]
    for arg in sys.argv:
        if arg.startswith("--p0="):
            ASSESSED = [float(v) for v in arg[5:].split(",")]
    # --dcp=X holds MGO_LIQ_DCP at X: the ternary liquidus at 1500-1700 K depends on it far more
    # than the binary data above 1816 K do (2026-10-02)
    for arg in sys.argv:
        if arg.startswith("--dcp="):
            ASSESSED[-3] = float(arg[6:])
            LOWER[-3], UPPER[-3] = ASSESSED[-3], ASSESSED[-3] + 1e-6
    workers = next((int(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--workers=")), 13)
    pp = fit(ASSESSED, workers) if "--fit" in sys.argv else ASSESSED
    report(pp, write=("--write" in sys.argv))
    print("\n  params:", [round(float(x), 1) for x in pp])
    print("  params_full:", ",".join(repr(float(x)) for x in pp))
