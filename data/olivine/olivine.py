"""Olivine (Mg,Fe)2SiO4 solid solution in the compound-energy formalism.

Model (the standard CALPHAD olivine model): sublattices (Mg,Fe)2 (SiO4)1. Mg and Fe
mix on a two-site metal sublattice; the orthosilicate group is fixed. The two endmembers
are forsterite (Mg2SiO4) and fayalite (Fe2SiO4). For a clean map onto pycalphad the SiO4
group is written as its constituent elements, (Mg,Fe)2(Si)1(O)4 - three sublattices, but
only the metal one mixes, so Si and O contribute no configurational entropy and the model
is identical to (Mg,Fe)2(SiO4)1. Per mole of atoms the divisor is 2 + 1 + 4 = 7.

Constituents on the metal sublattice are listed [Fe, Mg] (alphabetical) so a single site-
fraction vector is shared with pycalphad, which sorts sublattice constituents.

Excess mixing: Fe-Mg olivine shows a small positive, Fe-asymmetric deviation from ideality
with no measurable excess entropy (open calorimetry, see PROVENANCE.md). Wood & Kleppa
(1981) give the excess enthalpy as

    H_xs = 2 (1000 + 1000 X_Fe) X_Fe X_Mg    cal / mol-formula

which is the subregular (two-term Redlich-Kister) interaction, in the [Fe, Mg] order,

    L0 = 3000 cal = 12552 J/mol,  L1 = 1000 cal = 4184 J/mol,   T-independent.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "cef"))

import cef
import endmembers as em

CAL = 4.184  # thermochemical calorie -> joule
R = cef.R
N_ATOMS = 7  # atoms per Mg2SiO4 / Fe2SiO4 formula unit

# Wood & Kleppa 1981 subregular interaction, in the [Fe, Mg] constituent order.
L0 = 3000.0 * CAL   # 12552.0 J/mol
L1 = 1000.0 * CAL   # 4184.0 J/mol


def olivine_phase(L=(L0, L1)):
    """Build the CEF olivine phase. L is the Redlich-Kister list on the (Fe,Mg) pair."""
    return cef.CEFPhase(
        sublattices=[(2.0, ["FE", "MG"]), (1.0, ["SI"]), (4.0, ["O"])],
        endmembers={
            (0, 0, 0): lambda T: em.gibbs("fayalite", T),     # y_Fe = 1
            (1, 0, 0): lambda T: em.gibbs("forsterite", T),   # y_Mg = 1
        },
        interactions=[dict(sublattice=0, pair=(0, 1), others={1: 0, 2: 0},
                           L=[(Lv,) for Lv in L])],
    )


def site_fracs(x_fo):
    """Full site-fraction vector Y for cef.gibbs at forsterite mole fraction x_fo
    (y_Mg = x_fo). Order matches pycalphad: [Fe, Mg] on sublattice 0, then Si, then O."""
    return [[1.0 - x_fo, x_fo], [1.0], [1.0]]


def gibbs_per_formula(phase, x_fo, T):
    """Molar Gibbs energy per mole of Mg2SiO4/Fe2SiO4 formula unit."""
    return phase.gibbs(site_fracs(x_fo), T, per_mole_atoms=True) * N_ATOMS


def h_xs(x_fo, L=(L0, L1)):
    """Excess enthalpy of mixing per mole of formula unit (J/mol). With a T-independent
    L the excess Gibbs is purely enthalpic, so H_xs = G_xs = y_Fe y_Mg[L0 + L1(y_Fe-y_Mg)]."""
    y_mg, y_fe = x_fo, 1.0 - x_fo
    return y_fe * y_mg * sum(Lv * (y_fe - y_mg) ** v for v, Lv in enumerate(L))


def g_mix(phase, x_fo, T):
    """Gibbs energy of mixing per mole of formula unit: G(x) minus the endmember mixture
    x_fo*G_fo + (1-x_fo)*G_fa (the ideal-reference straight line)."""
    g = gibbs_per_formula(phase, x_fo, T)
    g_ref = x_fo * em.gibbs("forsterite", T) + (1.0 - x_fo) * em.gibbs("fayalite", T)
    return g - g_ref


def activities(x_fo, T, L=(L0, L1)):
    """Component activities (a_fo, a_fa) relative to the pure endmembers, and the
    activity coefficients. Ideal part is a_i = y_i^2 (two-site substitution); the excess
    part is the Redlich-Kister partial. a_fo = y_Mg^2 gamma_fo, a_fa = y_Fe^2 gamma_fa."""
    import math
    y_mg, y_fe = x_fo, 1.0 - x_fo

    def gxs(y):  # excess Gibbs as a function of y_Mg
        yf = 1.0 - y
        return yf * y * sum(Lv * (yf - y) ** v for v, Lv in enumerate(L))

    h = 1e-6
    dgxs = (gxs(y_mg + h) - gxs(y_mg - h)) / (2 * h)
    gx = gxs(y_mg)
    rt_ln_gamma_fo = gx + (1.0 - y_mg) * dgxs   # partial molar excess of fo
    rt_ln_gamma_fa = gx - y_mg * dgxs           # partial molar excess of fa
    gamma_fo = math.exp(rt_ln_gamma_fo / (R * T))
    gamma_fa = math.exp(rt_ln_gamma_fa / (R * T))
    a_fo = y_mg ** 2 * gamma_fo
    a_fa = y_fe ** 2 * gamma_fa
    return dict(a_fo=a_fo, a_fa=a_fa, gamma_fo=gamma_fo, gamma_fa=gamma_fa)


def d2gmix_dx2(x_fo, T, L=(L0, L1)):
    """Second derivative of G_mix wrt x_fo (per formula). Spinodal where this is zero."""
    def gm(y):
        yf = 1.0 - y
        g_conf = 2.0 * R * T * (
            (y * __import__("math").log(y) if y > 0 else 0.0)
            + (yf * __import__("math").log(yf) if yf > 0 else 0.0))
        g_xs = yf * y * sum(Lv * (yf - y) ** v for v, Lv in enumerate(L))
        return g_conf + g_xs
    h = 1e-5
    return (gm(x_fo + h) - 2 * gm(x_fo) + gm(x_fo - h)) / (h * h)


def consolute(L=(L0, L1), x_lo=0.01, x_hi=0.99, T_hi=1200.0):
    """Metastable-solvus critical (consolute) temperature and composition: the highest
    temperature at which the spinodal condition d2G_mix/dx2 = 0 has a solution, found by
    scanning x for the peak of the spinodal T(x). Returns (T_c, x_c)."""
    def spinodal_T(x):
        # d2G/dx2 = 2RT/(x(1-x)) + G_xs''(x) = 0  ->  T = -G_xs''(x) * x(1-x) / (2R)
        import math
        h = 1e-5

        def gxs(y):
            yf = 1.0 - y
            return yf * y * sum(Lv * (yf - y) ** v for v, Lv in enumerate(L))
        gxs2 = (gxs(x + h) - 2 * gxs(x) + gxs(x - h)) / (h * h)
        return -gxs2 * x * (1.0 - x) / (2.0 * R)

    best_T, best_x = -1.0, None
    n = 4000
    for i in range(1, n):
        x = x_lo + (x_hi - x_lo) * i / n
        T = spinodal_T(x)
        if T > best_T:
            best_T, best_x = T, x
    return best_T, best_x
