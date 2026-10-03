"""Two-site orthopyroxene (Mg,Fe)[M1] (Mg,Fe)[M2] Si2O6: Fe-Mg order between M1 and M2.

Fe prefers the distorted M2 site, so at fixed Fe/(Fe+Mg) the phase lowers its energy by
putting Fe there; a one-site model cannot, which is why it could not hold both the
ferrosilite = fayalite + quartz equilibrium (Bohlen et al. 1980) and the near-unit
olivine/orthopyroxene Fe-Mg exchange (Nafziger & Muan 1967) at once. The engine takes the
phase at internal equilibrium (mqmqa_ph_cef_line_gibbs), as pycalphad does.

Per M2Si2O6, sublattices M1 (1 site) and M2 (1 site), Y = Fe fraction on each:

    G(Mg:Mg) = 2 enstatite, with the assessed high-T correction (data/olivine/endmembers.py)
    G(Fe:Fe) = 2 ferrosilite + 2 [FS_DHF_SHIFT + FS_HT_B (T - FS_T_BREAK) above the break]
    G(Fe:Mg) + G(Mg:Fe) = G(Mg:Mg) + G(Fe:Fe) + RECIP        (reciprocal energy)
    G(Fe:Mg) - G(Mg:Fe) = EXCH_H - T EXCH_S                   (Fe(M2) + Mg(M1) -> Fe(M1) + Mg(M2))
    site interactions W_M1, W_M2 (regular, T-independent)

The parameters are assessed in data/olivine-opx/assessment against site occupancies,
olivine/orthopyroxene tie-lines, the ferrosilite breakdown and calorimetry.
"""
import importlib.util
import math
from pathlib import Path

from scipy.optimize import minimize_scalar

_s = importlib.util.spec_from_file_location("opx_ol_em", Path(__file__).resolve().parents[1]
                                            / "olivine" / "endmembers.py")
em = importlib.util.module_from_spec(_s)
_s.loader.exec_module(em)

R = 8.3145

# assessed 2026-09-30 (assessment/assess.py; total cost 45.3, RMS 1.32)
EXCH_H = 10951.3685   # J per M2Si2O6
EXCH_S = 2.4556       # J/K per M2Si2O6
RECIP = -6053.1987    # J per M2Si2O6
W_M1 = 6582.9276      # J per mole of M1 sites
W_M2 = 5216.3515      # J per mole of M2 sites
FS_DHF_SHIFT = 2411.7589   # J per FeSiO3, inside the R&H +-3 kJ
FS_T_BREAK = 800.0    # end of the Robie-Hemingway ferrosilite Cp fit
FS_HT_B = 6.4613      # J/K per FeSiO3 above the break

ENDMEMBERS = ("FE:FE", "FE:MG", "MG:FE", "MG:MG")     # M1:M2, constituents name-sorted


def _pieces(terms, steps):
    """Piecewise coefficients [(T_upper, c7), ...] of a weighted sum of piecewise functions,
    terms [(weight, [(T_upper, c7), ...])], plus steps (T_break, dA, dB) that add dA + dB*T
    above each break (continuous when dA = -dB*T_break)."""
    breaks = sorted({t for _, ivs in terms for t, _ in ivs[:-1]} | {t for t, _, _ in steps if t > 0.0})
    out = []
    for i, t_up in enumerate(breaks + [6000.0]):
        t_lo = breaks[i - 1] if i else 0.0
        c = [0.0] * 7
        for w, ivs in terms:
            ci = next((cc for t, cc in ivs if t_lo < t), ivs[-1][1])
            c = [a + w * b for a, b in zip(c, ci)]
        for tb, dA, dB in steps:
            if tb <= t_lo:
                c[0] += dA
                c[1] += dB
        out.append((t_up, c))
    return out


def _mm_ff():
    en = em.intervals("enstatite")
    fs = [(t, list(c)) for t, c in em.intervals("ferrosilite")]
    for _, c in fs:
        c[0] += FS_DHF_SHIFT
    s_mm = [(em.ENSTATITE_T_BREAK, -em.ENSTATITE_HT_B * em.ENSTATITE_T_BREAK, em.ENSTATITE_HT_B)]
    s_ff = [(FS_T_BREAK, -2.0 * FS_HT_B * FS_T_BREAK, 2.0 * FS_HT_B)] if FS_HT_B else []
    return en, s_mm, fs, s_ff


def intervals(name):
    """Gibbs intervals [(T_upper, [c0..c6])] of one endmember on the basis (1, T, TlnT,
    T^2, T^3, 1/T, T^0.5), per M2Si2O6."""
    en, s_mm, fs, s_ff = _mm_ff()
    if name == "MG:MG":
        return _pieces([(2.0, en)], s_mm)
    if name == "FE:FE":
        return _pieces([(2.0, fs)], s_ff)
    sign = 1.0 if name == "FE:MG" else -1.0
    half = [(t, 0.5 * a, 0.5 * b) for t, a, b in s_mm + s_ff]
    half.append((0.0, 0.5 * (RECIP + sign * EXCH_H), -0.5 * sign * EXCH_S))
    return _pieces([(1.0, en), (1.0, fs)], half)


def _eval(c, T):
    return (c[0] + c[1] * T + c[2] * T * math.log(T) + c[3] * T * T + c[4] * T ** 3
            + c[5] / T + c[6] * math.sqrt(T))


def g_end(name, T):
    for t_up, c in intervals(name):
        if T < t_up:
            return _eval(c, T)
    return _eval(intervals(name)[-1][1], T)


def _xlnx(x):
    return x * math.log(x) if x > 0.0 else 0.0


def gibbs(y1, y2, T, ge=None):
    """G per M2Si2O6 at Fe fractions y1 (M1) and y2 (M2)."""
    ge = ge or {n: g_end(n, T) for n in ENDMEMBERS}
    g = (y1 * y2 * ge["FE:FE"] + y1 * (1 - y2) * ge["FE:MG"]
         + (1 - y1) * y2 * ge["MG:FE"] + (1 - y1) * (1 - y2) * ge["MG:MG"])
    g += R * T * (_xlnx(y1) + _xlnx(1 - y1) + _xlnx(y2) + _xlnx(1 - y2))
    return g + W_M1 * y1 * (1 - y1) + W_M2 * y2 * (1 - y2)


def equilibrium(x, T):
    """(G, y1, y2) per M2Si2O6 at bulk Fe/(Fe+Mg) = x, minimized over the site split."""
    ge = {n: g_end(n, T) for n in ENDMEMBERS}
    lo, hi = max(0.0, 2 * x - 1), min(1.0, 2 * x)
    if hi - lo < 1e-14:
        return gibbs(lo, 2 * x - lo, T, ge), lo, 2 * x - lo
    r = minimize_scalar(lambda u: gibbs(u, 2 * x - u, T, ge), bounds=(lo, hi),
                        method="bounded", options={"xatol": 1e-12})
    return r.fun, r.x, 2 * x - r.x


def excess_groups():
    """Site interactions as SUBL excess groups (linear constituent indices, [L0]): M1 is
    FE, MG = 1, 2; M2 is FE, MG = 3, 4; Si 5; O 6. Each site's W is listed once per
    occupant of the other site, so it does not depend on that occupant."""
    return [([1, 2, 4, 5, 6], [W_M1]), ([1, 2, 3, 5, 6], [W_M1]),
            ([2, 3, 4, 5, 6], [W_M2]), ([1, 3, 4, 5, 6], [W_M2])]


def subl_block(elements, name="ORTHOPYROXENE"):
    """The phase as ChemSage SUBL lines for a file whose element order is `elements`
    (symbols, upper case, must include FE, MG, SI, O)."""
    fmt = lambda v: f"{v:.10E}"
    count = {"FE:FE": {"FE": 2}, "FE:MG": {"FE": 1, "MG": 1}, "MG:FE": {"FE": 1, "MG": 1},
             "MG:MG": {"MG": 2}}
    L = [f" {name}", " SUBL"]
    for n in ENDMEMBERS:
        ivs = intervals(n)
        eq_type = 4 if any(c[6] for _, c in ivs) else 1
        st = [float(count[n].get(e, 0)) + (2.0 if e == "SI" else 6.0 if e == "O" else 0.0)
              for e in elements]
        L.append(" " + {"FE:FE": "FE2SI2O6", "FE:MG": "FEMGSI2O6", "MG:FE": "MGFESI2O6",
                        "MG:MG": "MG2SI2O6"}[n])
        L.append(f"   {eq_type}   {len(ivs)}   " + "   ".join(f"{v:.1f}" for v in st))
        for t_up, c in ivs:
            L.append(f"   {t_up:.4f}   " + "   ".join(fmt(v) for v in c[:6]))
            if eq_type == 4:
                L.append(f"   1   {fmt(c[6])}   {fmt(0.5)}")
    L.append("   4")
    L.append("   " + "   ".join(f"{r:.6f}" for r in (1.0, 1.0, 2.0, 6.0)))
    L.append("   2   2   1   1")
    for con in (["FE", "MG"], ["FE", "MG"], ["SI"], ["O"]):
        L.append("   " + "   ".join(con))
    for row in ([1, 1, 2, 2], [1, 2, 1, 2], [1, 1, 1, 1], [1, 1, 1, 1]):
        L.append("   " + "   ".join(str(i) for i in row))
    for idx, Ls in excess_groups():
        L.append("   " + "   ".join(str(i) for i in [len(idx)] + idx))
        L.append(f"   {len(Ls)}")
        for Lv in Ls:
            L.append("   " + "   ".join(fmt(v) for v in (Lv, 0, 0, 0, 0, 0)))
    L.append("   0")
    return L
