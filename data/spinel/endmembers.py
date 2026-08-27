"""Spinel MgAl2O4 and hercynite FeAl2O4 endmember Gibbs energies.

Assembled the project's way, from open reference data:
 - MgAl2O4 formation enthalpy from the binary oxides, Navrotsky & Kleppa 1968 (oxide-melt
   solution calorimetry, dHf_ox = -36.4845 kJ/mol), plus MgO and Al2O3 from CODATA/the
   shipped builders: dHf(MgAl2O4) = dHf(MgO) + dHf(Al2O3) + dHf_ox.
 - FeAl2O4 (hercynite) dHf, S298 from the TKV evaluation (-1982.38 kJ, 106.27 J/K).
 - MgAl2O4 S298 = 80.63 J/K (measured third-law value).
 - Cp(T) of both by Neumann-Kopp from the shipped oxide Cp models (MgO/FeO + Al2O3), the
   Maier-Kelley form Cp = a + b*T + c*T^-2. (NK reproduces the TKV FeAl2O4 Cp298 to ~5 J/K.)

Standalone module (its own gibbs_coeffs) to keep the shared build_dat sys.modules collision
out of the test process; self-test in __main__.
"""
import math

T0 = 298.15

# Neumann-Kopp Cp = component-oxide Cp sums (from data/mgo-sio2, feo-sio2, cao-al2o3 builders)
_MGO = dict(a=48.2425, b=0.003906019, c=-1108200.0)
_FEO = dict(a=50.663, b=0.008711283, c=-313381.0)
_AL2O3 = dict(a=115.0182, b=0.01179888, c=-3506190.0)

ENDMEMBERS = {
    "spinel": dict(  # MgAl2O4
        dHf=-601500.0 + -1675692.0 + -36484.5, S298=80.63,
        a=_MGO["a"] + _AL2O3["a"], b=_MGO["b"] + _AL2O3["b"], c=_MGO["c"] + _AL2O3["c"]),
    "hercynite": dict(  # FeAl2O4
        dHf=-1982380.0, S298=106.27,
        a=_FEO["a"] + _AL2O3["a"], b=_FEO["b"] + _AL2O3["b"], c=_FEO["c"] + _AL2O3["c"]),
}


def cp(name, T):
    d = ENDMEMBERS[name]
    return d["a"] + d["b"] * T + d["c"] * T ** -2


def gibbs_coeffs(name):
    """Term-basis coefficients [c0..c6] on (1, T, T*lnT, T^2, T^3, 1/T, T^0.5); the T^3 and
    T^0.5 terms are zero for a three-term Maier-Kelley Cp."""
    d = ENDMEMBERS[name]
    a, b, c, dHf, S = d["a"], d["b"], d["c"], d["dHf"], d["S298"]
    c0 = dHf - a * T0 - 0.5 * b * T0 ** 2 + c / T0
    c1 = a - S + a * math.log(T0) + b * T0 - 0.5 * c / T0 ** 2
    return [c0, c1, -a, -0.5 * b, 0.0, -0.5 * c, 0.0]


def gibbs(name, T):
    c = gibbs_coeffs(name)
    return c[0] + c[1] * T + c[2] * T * math.log(T) + c[3] * T * T + c[5] / T


def _gibbs_direct(name, T):
    d = ENDMEMBERS[name]
    a, b, c = d["a"], d["b"], d["c"]
    H = lambda t: a * t + 0.5 * b * t * t - c / t
    Sf = lambda t: a * math.log(t) + b * t - 0.5 * c * t ** -2
    return d["dHf"] + H(T) - H(T0) - T * (d["S298"] + Sf(T) - Sf(T0))


if __name__ == "__main__":
    print("Cp(298):", {n: round(cp(n, T0), 2) for n in ENDMEMBERS},
          "(TKV FeAl2O4 123.55)")
    print("dHf kJ:", {n: round(ENDMEMBERS[n]["dHf"] / 1000, 1) for n in ENDMEMBERS})
    worst = max(abs(gibbs(n, T) - _gibbs_direct(n, T))
                for n in ENDMEMBERS for T in (400.0, 900.0, 1500.0, 2000.0))
    print(f"gibbs coeff vs direct: {worst:.2e} J -> {'PASS' if worst < 1e-6 else 'FAIL'}")
