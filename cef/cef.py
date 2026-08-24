"""Compound-Energy Formalism (CEF / sublattice-model) Gibbs energy.

The standard CALPHAD solid-solution model: a phase has one or more sublattices, each
with a site multiplicity a_s and a set of constituents mixing on it. The molar Gibbs
energy per mole of formula units (sum of site multiplicities) is

    G = Sum_endmembers  ( Prod_s y_{i_s}^s ) * G_endmember(T)          (reference)
      + R T Sum_s a_s Sum_i y_i^s ln y_i^s                            (ideal config)
      + Sum_interactions  ( Prod_{other s} y ) * y_i y_j Sum_v L_v (y_i - y_j)^v  (excess, RK)

This is a clean-room implementation of the published formalism (Hillert; Sundman &
Agren; Lukas-Fries-Sundman), validated to machine precision against pycalphad's Model.GM.
A Python prototype first (get the physics right), then ported to C alongside the MQMQA
energy and wired into the ChemSage-.dat reader (SUBL blocks).

Parameter Gibbs coefficients use the SGTE/TDB term basis a + b*T + c*T*lnT + d*T^2 +
e*T^3 + f*T^-1 + g*T^0.5 (extend as databases require). The T^0.5 term appears when a
mineral heat capacity carries a T^-0.5 term (the Robie-Hemingway / Berman-Brown silicate
Cp form), as forsterite does. An endmember value may also be given as a callable G(T)
for a Gibbs function that does not fit the fixed term basis.
"""
import math

R = 8.3145  # CALPHAD gas constant (matches pycalphad v.R and the MQMQA engine)


def eval_gibbs(coeffs, T):
    """Gibbs energy from term-basis coefficients a + b*T + c*T*lnT + d*T^2 + e*T^3 +
    f/T + g*T^0.5 (missing trailing terms = 0), or from a callable evaluated at T."""
    if callable(coeffs):
        return coeffs(T)
    c = list(coeffs) + [0.0] * (7 - len(coeffs))
    return (c[0] + c[1] * T + c[2] * T * math.log(T)
            + c[3] * T * T + c[4] * T ** 3 + c[5] / T + c[6] * math.sqrt(T))


class CEFPhase:
    """A sublattice phase.

    sublattices : list of (site_multiplicity, [constituent names]) per sublattice.
    endmembers  : dict {(constituent-index per sublattice): Gibbs coeffs}.
    interactions: list of dicts, each
        {sublattice: s, pair: (i, j), others: {s2: k, ...}, L: [coeffs_v0, coeffs_v1, ...]}
        (others pins the endmember constituent on every OTHER sublattice; for a single
         mixing sublattice it is empty).
    """

    def __init__(self, sublattices, endmembers, interactions=None):
        self.subl = sublattices
        self.endmembers = endmembers
        self.interactions = interactions or []

    def gibbs(self, Y, T, per_mole_atoms=True):
        """Molar Gibbs energy at site fractions Y (Y[s] = list of site fractions on
        sublattice s, summing to 1) and temperature T. By default per mole of atoms
        (G_formula / sum of site multiplicities), matching pycalphad's GM and the MQMQA
        engine; set per_mole_atoms=False for per formula unit."""
        G = 0.0
        # reference: sum over endmembers of (product of site fractions) * G_endmember
        for idx, coeffs in self.endmembers.items():
            prod = 1.0
            for s, i in enumerate(idx):
                prod *= Y[s][i]
            G += prod * eval_gibbs(coeffs, T)
        # ideal configurational entropy, per sublattice weighted by site multiplicity
        for s, (a_s, _) in enumerate(self.subl):
            for y in Y[s]:
                if y > 0.0:
                    G += R * T * a_s * y * math.log(y)
        # excess: Redlich-Kister interactions
        for it in self.interactions:
            s = it["sublattice"]
            i, j = it["pair"]
            yi, yj = Y[s][i], Y[s][j]
            other = 1.0
            for s2, k in it.get("others", {}).items():
                other *= Y[s2][k]
            rk = sum(eval_gibbs(Lv, T) * (yi - yj) ** v
                     for v, Lv in enumerate(it["L"]))
            G += other * yi * yj * rk
        if per_mole_atoms:
            G /= sum(a_s for a_s, _ in self.subl)
        return G
