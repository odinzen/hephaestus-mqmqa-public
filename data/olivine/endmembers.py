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
        Tmax=1000.0,  # R&H fit to 1000 K; smoothly extrapolated in the subsolidus range
    ),
    "ferrosilite": dict(  # FeSiO3, USGS Bull. 2131 p.60 (Cp) / p.332 (phase table)
        dHf=-1195200.0, S298=94.60,
        A1=124.3, A2=1.454e-2, A3=-3.378e6, A4=0.0, A5=0.0,
        Tmax=800.0,  # orthoferrosilite (metastable at 1 atm); R&H fit to 800 K
    ),
}


def cp(name, T):
    """Robie-Hemingway heat capacity Cp(T) in J/mol/K."""
    d = ENDMEMBERS[name]
    return (d["A1"] + d["A2"] * T + d["A3"] * T ** -2
            + d["A4"] * T ** -0.5 + d["A5"] * T * T)


def gibbs_coeffs(name):
    """Term-basis coefficients [c0, c1, c2, c3, c4, c5, c6] of the endmember Gibbs
    energy from the elements, on the basis (1, T, T*lnT, T^2, T^3, 1/T, T^0.5). Feed
    straight into cef.eval_gibbs, and into a TDB PARAMETER (c6 is the T^0.5 term)."""
    d = ENDMEMBERS[name]
    A1, A2, A3, A4, A5 = d["A1"], d["A2"], d["A3"], d["A4"], d["A5"]
    dHf, S298 = d["dHf"], d["S298"]
    c0 = dHf - A1 * T0 - 0.5 * A2 * T0 ** 2 + A3 / T0 - 2 * A4 * T0 ** 0.5 - A5 * T0 ** 3 / 3
    c1 = (A1 - S298 + A1 * math.log(T0) + A2 * T0
          - 0.5 * A3 / T0 ** 2 - 2 * A4 / T0 ** 0.5 + 0.5 * A5 * T0 ** 2)
    c2 = -A1
    c3 = -0.5 * A2
    c4 = -A5 / 6.0
    c5 = -0.5 * A3
    c6 = 4.0 * A4
    return [c0, c1, c2, c3, c4, c5, c6]


def gibbs(name, T):
    """Endmember Gibbs energy from the term-basis coefficients (per mole of formula)."""
    c = gibbs_coeffs(name)
    return (c[0] + c[1] * T + c[2] * T * math.log(T) + c[3] * T * T
            + c[4] * T ** 3 + c[5] / T + c[6] * math.sqrt(T))


def _gibbs_direct(name, T):
    """Reference implementation: G = dHf + INT Cp dT - T*(S298 + INT Cp/T dT), by
    direct integration of the five-term Cp. Used only to check gibbs_coeffs."""
    d = ENDMEMBERS[name]
    A1, A2, A3, A4, A5 = d["A1"], d["A2"], d["A3"], d["A4"], d["A5"]

    def H_int(t):  # INT Cp dT
        return A1 * t + 0.5 * A2 * t * t - A3 / t + 2 * A4 * t ** 0.5 + A5 * t ** 3 / 3

    def S_int(t):  # INT Cp/T dT
        return (A1 * math.log(t) + A2 * t - 0.5 * A3 * t ** -2
                - 2 * A4 * t ** -0.5 + 0.5 * A5 * t * t)

    H = d["dHf"] + H_int(T) - H_int(T0)
    S = d["S298"] + S_int(T) - S_int(T0)
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
        for T in (300.0, 800.0, 1200.0, 1500.0):
            d = abs(gibbs(name, T) - _gibbs_direct(name, T))
            worst = max(worst, d)
    print(f"  worst |d| = {worst:.2e} J/mol  -> {'PASS' if worst < 1e-6 else 'FAIL'}")
    # 3) show the coefficients that go into the CEF model and the TDB.
    print("\nTerm-basis Gibbs coefficients [1, T, TlnT, T^2, T^3, 1/T, T^0.5]:")
    for name in ENDMEMBERS:
        print(f"  {name:11s} {[float(f'{c:.6g}') for c in gibbs_coeffs(name)]}")
