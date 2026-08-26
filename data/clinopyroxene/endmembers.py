"""Diopside (CaMgSi2O6) and hedenbergite (CaFeSi2O6) endmember Gibbs energies.

Open source: Robie & Hemingway (1995), USGS Bulletin 2131 (public domain). Both minerals
are tabulated in the same high-temperature phase table, so the two endmembers sit on one
self-consistent scale. dHf(298), S298 and the Cp(T) table are read from that bulletin;
the five-term Robie-Hemingway Cp form

    Cp(T) = A1 + A2*T + A3*T^-2 + A4*T^-0.5 + A5*T^2   (J/mol/K)

is least-squares fitted here to the tabulated Cp values (max residual < 0.01 J/mol/K
over the whole crystal range; the basis is well conditioned, unlike a Gibbs-coefficient
fit). The Gibbs energy from the elements integrates to the term basis
(1, T, T*lnT, T^2, T^3, 1/T, T^0.5), matching cef.eval_gibbs. Standalone module (does not
import the olivine one) to keep the shared build_dat sys.modules collision out of the
test process. Self-test in __main__.
"""
import math

T0 = 298.15

# name -> Robie-Hemingway 1995 data (dHf in J/mol; S298, Cp coeffs in J/mol/K units).
# Cp coefficients are the least-squares fit to the Bull. 2131 high-T Cp table.
ENDMEMBERS = {
    "diopside": dict(  # CaMgSi2O6, USGS Bull. 2131 high-T phase table
        dHf=-3201500.0, S298=142.7,
        A1=470.3013, A2=-9.865880e-2, A3=2.4660e5, A4=-4824.0496, A5=2.8131e-5,
        Tmax=1600.0,
    ),
    "hedenbergite": dict(  # CaFeSi2O6, USGS Bull. 2131 high-T phase table
        dHf=-2839900.0, S298=174.2,
        A1=311.1611, A2=1.208617e-2, A3=-1.8337e6, A4=-2052.2114, A5=1.5365e-7,
        Tmax=1300.0,
    ),
}


def cp(name, T):
    d = ENDMEMBERS[name]
    return (d["A1"] + d["A2"] * T + d["A3"] * T ** -2
            + d["A4"] * T ** -0.5 + d["A5"] * T * T)


def gibbs_coeffs(name):
    """Term-basis coefficients [c0..c6] on (1, T, T*lnT, T^2, T^3, 1/T, T^0.5)."""
    d = ENDMEMBERS[name]
    A1, A2, A3, A4, A5 = d["A1"], d["A2"], d["A3"], d["A4"], d["A5"]
    dHf, S298 = d["dHf"], d["S298"]
    c0 = dHf - A1 * T0 - 0.5 * A2 * T0 ** 2 + A3 / T0 - 2 * A4 * T0 ** 0.5 - A5 * T0 ** 3 / 3
    c1 = (A1 - S298 + A1 * math.log(T0) + A2 * T0
          - 0.5 * A3 / T0 ** 2 - 2 * A4 / T0 ** 0.5 + 0.5 * A5 * T0 ** 2)
    return [c0, c1, -A1, -0.5 * A2, -A5 / 6.0, -0.5 * A3, 4.0 * A4]


def gibbs(name, T):
    c = gibbs_coeffs(name)
    return (c[0] + c[1] * T + c[2] * T * math.log(T) + c[3] * T * T
            + c[4] * T ** 3 + c[5] / T + c[6] * math.sqrt(T))


def _gibbs_direct(name, T):
    d = ENDMEMBERS[name]
    A1, A2, A3, A4, A5 = d["A1"], d["A2"], d["A3"], d["A4"], d["A5"]

    def H_int(t):
        return A1 * t + 0.5 * A2 * t * t - A3 / t + 2 * A4 * t ** 0.5 + A5 * t ** 3 / 3

    def S_int(t):
        return (A1 * math.log(t) + A2 * t - 0.5 * A3 * t ** -2
                - 2 * A4 * t ** -0.5 + 0.5 * A5 * t * t)

    H = d["dHf"] + H_int(T) - H_int(T0)
    S = d["S298"] + S_int(T) - S_int(T0)
    return H - T * S


if __name__ == "__main__":
    print("Cp(298.15) vs Robie-Hemingway table value:")
    for name, ref in (("diopside", 166.78), ("hedenbergite", 175.3)):
        print(f"  {name:13s} Cp298 = {cp(name, T0):8.3f}  ({ref})")
    worst = max(abs(gibbs(n, T) - _gibbs_direct(n, T))
                for n in ENDMEMBERS for T in (300.0, 800.0, 1200.0, 1500.0))
    print(f"Gibbs coeff vs direct H-T*S: worst |d| = {worst:.2e} J/mol "
          f"-> {'PASS' if worst < 1e-6 else 'FAIL'}")
