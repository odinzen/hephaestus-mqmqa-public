"""Forsterite (Mg2SiO4) and fayalite (Fe2SiO4) endmember Gibbs energies.

Open source: Robie & Hemingway (1995), "Thermodynamic Properties of Minerals and
Related Substances at 298.15 K and 1 Bar Pressure and at Higher Temperatures",
U.S. Geological Survey Bulletin 2131 (public domain). Both minerals are tabulated in
the same ortho-silicate section, so the two endmembers sit on one self-consistent scale.

Heat capacity is the Robie-Hemingway five-term form (J/mol/K)

    Cp(T) = A1 + A2*T + A3*T^-2 + A4*T^-0.5 + A5*T^2

integrated to a standard-state Gibbs energy from the elements

    G(T) = dHf(298) + INT_298^T Cp dT  -  T * ( S298 + INT_298^T Cp/T dT ).

Integrating that Cp form lands G on the term basis
    (1, T, T*lnT, T^2, T^3, 1/T, T^0.5),
matching cef.eval_gibbs (the T^0.5 coefficient is 4*A4, nonzero only for forsterite).
The coefficient derivation is checked in this module against a direct H - T*S evaluation
and against the Robie-Hemingway tabulated Cp(298); see the __main__ self-test.
"""
import math

T0 = 298.15
CAL = 4.184  # thermochemical calorie -> joule

# name -> Robie-Hemingway 1995 data. dHf in J/mol, S298 and Cp coeffs in J/mol/K units.
#   dHf   : enthalpy of formation from the elements at 298.15 K (Bull. 2131 phase table)
#   S298  : third-law entropy at 298.15 K
#   A1..A5: the five Cp coefficients (A4 is the T^-0.5 term; 0 when absent)
#   Tmax  : upper limit of the Cp fit (K); the crystal range in Bull. 2131
ENDMEMBERS = {
    "forsterite": dict(  # Mg2SiO4, USGS Bull. 2131 p.60 (Cp) / p.298 (phase table)
        dHf=-2173000.0, S298=94.11,
        A1=87.36, A2=8.717e-2, A3=-3.699e6, A4=843.6, A5=-2.237e-5,
        Tmax=1800.0,
    ),
    "fayalite": dict(  # Fe2SiO4, USGS Bull. 2131 p.60 (Cp) / p.332 (phase table)
        dHf=-1478200.0, S298=151.00,
        A1=176.02, A2=-8.808e-3, A3=-3.889e6, A4=0.0, A5=2.471e-5,
        Tmax=1490.0,  # fayalite melts incongruently at 1490 K
    ),
    # Orthopyroxene endmembers (per MgSiO3 / FeSiO3 formula unit), same bulletin.
    "enstatite": dict(  # MgSiO3, USGS Bull. 2131 p.61 (Cp) / p.334 (phase table)
        dHf=-1545600.0, S298=66.27,
        A1=350.7, A2=-1.472e-1, A3=1.769e6, A4=-4296.0, A5=5.826e-5,
        Tmax=1000.0,  # R&H fit to 1000 K
        # Above 800 K, where the two agree to 0.1 J/K: the drop-calorimetry orthoenstatite Cp of
        # Thieblot, Tequi & Richet 1999 (Am. Mineral. 84, 848, Table 3, Eq. 3; protoenstatite
        # within 3%). The R&H A5*T^2 term, extrapolated, gave 176 J/K at 1830 K against 133
        # measured, and put orthopyroxene back above the liquid near 3100 K (2026-10-02).
        HT=dict(T=800.0, A1=201.585, A2=-11.933e-3, A3=0.46073e5, A4=-2011.5, A5=0.0),
    ),
    "ferrosilite": dict(  # FeSiO3, USGS Bull. 2131 p.60 (Cp) / p.332 (phase table)
        dHf=-1195200.0, S298=94.60,
        A1=124.3, A2=1.454e-2, A3=-3.378e6, A4=0.0, A5=0.0,
        Tmax=800.0,  # orthoferrosilite (metastable at 1 atm); R&H fit to 800 K
    ),
}


# Enstatite high-T correction: a second Gibbs interval on Mg2Si2O6 above the ortho ->
# proto-enstatite transition, dG = ENSTATITE_HT_B * (T - ENSTATITE_T_BREAK) J per formula.
# The R&H orthoenstatite Cp is fit only to 1000 K. The value is assessed with the MgO-SiO2
# liquid (data/mgo-sio2/assessment) against the enstatite peritectic and eutectic; this
# is the one definition the orthopyroxene databases and that binary all read. Zero below
# the break, so the measured olivine/opx Fe-Mg exchange at <= 1273 K is untouched.
ENSTATITE_T_BREAK = 1360.0
ENSTATITE_DG_1830 = 4044.0          # J per Mg2Si2O6 at 1830 K (MgO-SiO2 assessment, 2026-10-02 fit D)
ENSTATITE_HT_B = ENSTATITE_DG_1830 / (1830.0 - ENSTATITE_T_BREAK)


def enstatite_ht(T):
    """The correction in J per MgSiO3 (half the Mg2Si2O6 value)."""
    return 0.5 * ENSTATITE_HT_B * (T - ENSTATITE_T_BREAK) if T > ENSTATITE_T_BREAK else 0.0


def _cp_terms(d):
    return d["A1"], d["A2"], d["A3"], d["A4"], d["A5"]


def cp(name, T):
    """Heat capacity Cp(T) in J/mol/K (Robie-Hemingway, or the measured high-T segment)."""
    d = ENDMEMBERS[name]
    if "HT" in d and T > d["HT"]["T"]:
        d = d["HT"]
    A1, A2, A3, A4, A5 = _cp_terms(d)
    return A1 + A2 * T + A3 * T ** -2 + A4 * T ** -0.5 + A5 * T * T


def _H_int(A, t):  # INT Cp dT
    A1, A2, A3, A4, A5 = A
    return A1 * t + 0.5 * A2 * t * t - A3 / t + 2 * A4 * t ** 0.5 + A5 * t ** 3 / 3


def _S_int(A, t):  # INT Cp/T dT
    A1, A2, A3, A4, A5 = A
    return A1 * math.log(t) + A2 * t - 0.5 * A3 * t ** -2 - 2 * A4 * t ** -0.5 + 0.5 * A5 * t * t


def _coeffs(A, H_ref, S_ref, T_ref):
    """Term-basis coefficients of G for Cp terms A, given H and S at T_ref."""
    A1, A2, A3, A4, A5 = A
    c0 = H_ref - A1 * T_ref - 0.5 * A2 * T_ref ** 2 + A3 / T_ref - 2 * A4 * T_ref ** 0.5 - A5 * T_ref ** 3 / 3
    c1 = (A1 - S_ref + A1 * math.log(T_ref) + A2 * T_ref
          - 0.5 * A3 / T_ref ** 2 - 2 * A4 / T_ref ** 0.5 + 0.5 * A5 * T_ref ** 2)
    return [c0, c1, -A1, -0.5 * A2, -A5 / 6.0, -0.5 * A3, 4.0 * A4]


def intervals(name):
    """Gibbs intervals [(T_upper, [c0..c6])] on the basis (1, T, T*lnT, T^2, T^3, 1/T, T^0.5),
    per mole of formula. H and S are continuous where a measured high-T Cp takes over."""
    d = ENDMEMBERS[name]
    A = _cp_terms(d)
    low = _coeffs(A, d["dHf"], d["S298"], T0)
    if "HT" not in d:
        return [(6000.0, low)]
    t = d["HT"]["T"]
    H = d["dHf"] + _H_int(A, t) - _H_int(A, T0)
    S = d["S298"] + _S_int(A, t) - _S_int(A, T0)
    return [(t, low), (6000.0, _coeffs(_cp_terms(d["HT"]), H, S, t))]


def gibbs_coeffs(name):
    """Term-basis coefficients [c0, c1, c2, c3, c4, c5, c6] of a single-interval endmember
    Gibbs energy from the elements, on the basis (1, T, T*lnT, T^2, T^3, 1/T, T^0.5). Feed
    straight into cef.eval_gibbs, and into a TDB PARAMETER (c6 is the T^0.5 term)."""
    ivs = intervals(name)
    if len(ivs) > 1:
        raise ValueError(f"{name} has {len(ivs)} Gibbs intervals; use intervals()")
    return ivs[0][1]


def eval_coeffs(c, T):
    return (c[0] + c[1] * T + c[2] * T * math.log(T) + c[3] * T * T
            + c[4] * T ** 3 + c[5] / T + c[6] * math.sqrt(T))


def gibbs(name, T):
    """Endmember Gibbs energy from the term-basis coefficients (per mole of formula)."""
    ivs = intervals(name)
    return eval_coeffs(next((c for t, c in ivs if T < t), ivs[-1][1]), T)


def _gibbs_direct(name, T):
    """Reference implementation: G = dHf + INT Cp dT - T*(S298 + INT Cp/T dT), by
    direct integration of the Cp segments. Used only to check intervals()."""
    d = ENDMEMBERS[name]
    A = _cp_terms(d)
    t_sw = d["HT"]["T"] if "HT" in d else math.inf
    t = min(T, t_sw)
    H = d["dHf"] + _H_int(A, t) - _H_int(A, T0)
    S = d["S298"] + _S_int(A, t) - _S_int(A, T0)
    if T > t_sw:
        B = _cp_terms(d["HT"])
        H += _H_int(B, T) - _H_int(B, t_sw)
        S += _S_int(B, T) - _S_int(B, t_sw)
    return H - T * S


if __name__ == "__main__":
    # 1) Cp(298) must reproduce the Robie-Hemingway tabulated values.
    print("Cp(298.15) check (Robie-Hemingway table value in parentheses):")
    for name, ref in (("forsterite", 118.61), ("fayalite", 131.84),
                      ("enstatite", 83.09), ("ferrosilite", 90.63)):
        print(f"  {name:11s} Cp298 = {cp(name, T0):8.3f}  ({ref})")
    # 2) the term-basis coefficients must match the direct H - T*S integration.
    print("\nGibbs coefficient derivation vs direct H-T*S integration:")
    worst = 0.0
    for name in ENDMEMBERS:
        for T in (300.0, 799.0, 801.0, 1200.0, 1500.0, 2200.0):
            d = abs(gibbs(name, T) - _gibbs_direct(name, T))
            worst = max(worst, d)
    print(f"  worst |d| = {worst:.2e} J/mol  -> {'PASS' if worst < 1e-6 else 'FAIL'}")
    # 3) show the coefficients that go into the CEF model and the TDB.
    print("\nTerm-basis Gibbs coefficients [1, T, TlnT, T^2, T^3, 1/T, T^0.5] per interval:")
    for name in ENDMEMBERS:
        for t_up, c in intervals(name):
            print(f"  {name:11s} <{t_up:5.0f} K {[float(f'{v:.6g}') for v in c]}")
