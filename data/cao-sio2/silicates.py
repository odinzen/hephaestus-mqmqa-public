"""Calcium silicate solids on Robie & Hemingway (1995, USGS Bull. 2131) measured data.

One definition shared by the CaO-SiO2 phase model, the CaO-Al2O3-SiO2 file and the
CaO-FeO-MgO-SiO2 file, the way data/olivine/endmembers.py serves the Fe and Mg silicates.
The tables (rh1995_ca_silicates.csv) give S and H - H298 to 1800 K (rankinite to 1400 K);
each compound's Gibbs energy from the elements is fitted to them as

    G(T) = dHf + INT Cp dT - T (S298 + INT Cp/T dT),   Cp = a + b T + c/T^2

with dHf and S298 left free (effective constants, as for SiO2 in dbbuild), rows at and
above 1000 K weighted three times since the liquidus lives there. Above the tables the
functions extrapolate (C2S to 2403 K, C3S to 2423 K, rankinite to 1737 K); this form keeps
Cp rising slowly there, where a T^-0.5 term fits the tables no better and turns rankinite's
Cp down past 1400 K. The residuals are within 60 J of the tables, 15 J above 1000 K.

Ca2SiO4 is fitted to the R&H rows below 1710 K only. Their one alpha row (1800 K) is not
consistent with the alpha' rows and the 1710 K transition: no positive Cp joins them, and
it sits about 2 kJ above Barin (1995) in G. Alpha instead starts from the fitted alpha' at
1710 K plus the measured transition, 14.1 kJ (Coughlin & O'Brien 1957, J. Phys. Chem. 61,
767, via Abdul et al. 2023 Table 9; Barin 14.19 kJ at 1712 K), with Barin's constant
alpha Cp of 205.016 J/mol/K (the value R&H also print at 1800 K), so G is continuous.

Run it to print the fit residuals against the tables.
"""
import csv
import math
from pathlib import Path

import numpy as np

T0 = 298.15
HERE = Path(__file__).resolve().parent
T_ALPHA_C2S = 1710.0


def read_table(path):
    """{formula: [(T, G from the elements, S), ...]} from an R&H extract in this CSV layout."""
    out = {}
    with open(path, newline="") as fh:
        for r in csv.DictReader(line for line in fh if not line.startswith("#")):
            T = float(r["T_K"])
            G = float(r["dfH298_kJ"]) * 1e3 + T * float(r["HT_minus_H298_over_T"]) - T * float(r["S"])
            out.setdefault(r["formula"], []).append((T, G, float(r["S"])))
    return out


TABLES = read_table(HERE / "rh1995_ca_silicates.csv")


def _basis(T):
    """G = dHf*1 + S298*(-T) + a*fa + b*fb + c*fc + d*fd for the Cp form above."""
    lt = math.log(T / T0)
    fa = (T - T0) - T * lt
    fb = 0.5 * (T * T - T0 * T0) - T * (T - T0)
    fc = -(1.0 / T - 1.0 / T0) + 0.5 * T * (1.0 / (T * T) - 1.0 / (T0 * T0))
    fd = 2.0 * (math.sqrt(T) - math.sqrt(T0)) + 2.0 * T * (1.0 / math.sqrt(T) - 1.0 / math.sqrt(T0))
    return [1.0, -T, fa, fb, fc, fd]


def fit(rows):
    """Coefficients of the Cp form above fitted to table rows, the rows at 1000 K and up
    weighted three times."""
    A = np.array([_basis(T)[:5] for T, _, _ in rows])
    y = np.array([G for _, G, _ in rows])
    w = np.array([3.0 if T >= 1000.0 else 1.0 for T, _, _ in rows])
    p = np.linalg.lstsq(A * w[:, None], y * w, rcond=None)[0]
    return dict(zip(("dHf", "S298", "a", "b", "c"), (float(v) for v in p)), d=0.0)


DH_ALPHA_C2S = 14100.0      # alpha' -> alpha, J/mol
CP_ALPHA_C2S = 205.016      # J/mol/K


def _alpha_c2s(low):
    T, h = T_ALPHA_C2S, 1e-3
    S = -(gibbs_cf(low, T + h) - gibbs_cf(low, T - h)) / (2 * h) + DH_ALPHA_C2S / T
    H = gibbs_cf(low, T) + T * S
    cp = CP_ALPHA_C2S
    return dict(dHf=H - cp * (T - T0), S298=S - cp * math.log(T / T0), a=cp, b=0.0, c=0.0, d=0.0)


def gibbs_cf(cf, T):
    return sum(k * f for k, f in zip((cf["dHf"], cf["S298"], cf["a"], cf["b"], cf["c"], cf["d"]),
                                      _basis(T)))


_C2S_LOW = fit([r for r in TABLES["Ca2SiO4"] if r[0] < T_ALPHA_C2S])

# formula -> [(T_upper, coefficient dict), ...]; the last interval extrapolates
INTERVALS = {
    "CaSiO3": [(6000.0, fit(TABLES["CaSiO3"]))],
    "Ca2SiO4": [(T_ALPHA_C2S, _C2S_LOW), (6000.0, _alpha_c2s(_C2S_LOW))],
    "Ca3SiO5": [(6000.0, fit(TABLES["Ca3SiO5"]))],
    "Ca3Si2O7": [(6000.0, fit(TABLES["Ca3Si2O7"]))],
}


# Rankinite's R&H enthalpy of formation carries +-10 kJ (Bull. 2131 p. 32), and with it the
# compound breaks down to C2S + CS near 1690 K although it melts at 1737 K (Abdul et al.
# 2023, DSC). A constant shift in dHf, assessed with the CaO-SiO2 liquid
# (data/cao-sio2/assessment), bounded by that uncertainty.
RANKINITE_DHF_SHIFT = -1768.066


def intervals(formula):
    """INTERVALS[formula] with the assessed corrections applied (what builders write)."""
    if formula != "Ca3Si2O7":
        return INTERVALS[formula]
    return [(t, dict(cf, dHf=cf["dHf"] + RANKINITE_DHF_SHIFT)) for t, cf in INTERVALS[formula]]


def gibbs(formula, T):
    """Gibbs energy from the elements, J per mole of formula."""
    ivs = intervals(formula)
    for t_up, cf in ivs:
        if T < t_up:
            return gibbs_cf(cf, T)
    return gibbs_cf(ivs[-1][1], T)


if __name__ == "__main__":
    for f, rows in TABLES.items():
        errs = [(T, gibbs_cf(dict(INTERVALS[f][0][1]), T) - G) for T, G, _ in rows if f != "Ca2SiO4" or T < T_ALPHA_C2S]
        hi = max(abs(e) for T, e in errs if T >= 1000.0)
        print(f"  {f:9s} max |G - table| {max(abs(e) for _, e in errs):6.1f} J, "
              f"at >= 1000 K {hi:6.1f} J")
    lo, hi = INTERVALS["Ca2SiO4"][0][1], INTERVALS["Ca2SiO4"][1][1]
    print(f"  Ca2SiO4 G step at 1710 K {gibbs_cf(hi, 1710.0) - gibbs_cf(lo, 1710.0):+.2e} J; "
          f"alpha vs R&H 1800 K row {gibbs('Ca2SiO4', 1800.0) - TABLES['Ca2SiO4'][-1][1]:+.0f} J, "
          f"vs Barin G(1800 K) -2816159 J {gibbs('Ca2SiO4', 1800.0) + 2816159.0:+.0f} J")
    for f in INTERVALS:
        print(f"  {f:9s} G(2000 K) = {gibbs(f, 2000.0):.1f}")
