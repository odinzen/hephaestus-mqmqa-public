"""Build an open MQMQA slag database (ChemSage SUBQ .dat) from a declarative system spec.

This is the "measured data -> fitted parameters -> loadable .dat" workflow for someone who
has literature data but no built database. You describe the system - its oxide components
(each with published endmember thermodynamics and a provenance note) and the fitted binary
liquid-excess parameters - and this emits a valid single-anion SUBQ .dat that the browser app
and pycalphad both load.

Scope and boundaries:
  - Single common anion (oxygen). Oxide slags of divalent/tetravalent cations (FeO, MgO, CaO,
    MnO, SiO2, ...). Reciprocal / multi-anion (oxyfluoride, sulfide) systems are out of scope.
  - Literature-only. Endmembers come from open compilations (JANAF, CODATA, Robie-Hemingway);
    excess parameters are the USER's own fit to open measured data. Nothing here bundles an
    external TDB's optimized parameters.
  - Free self-assessment is capped at FOUR components. Five and up is the premium tier - the
    real multicomponent industrial systems - and raises PremiumFeatureError pointing to support.

The N-cation liquid is assembled Muggianu-style from the binary excesses (a ternary/higher
excess is zero unless the user supplies one), exactly as the shipped FeO-MgO-SiO2 database is
built from its two binaries. The endmember Gibbs assembly and the .dat layout are the same as
data/*/build_dat.py, generalized to any cation set.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

R = 8.3145            # CALPHAD gas constant (the engine's value, load-bearing)
T0 = 298.15           # K, reference temperature for dHf and S298
Z_PER_CHARGE = 1.3774438 / 2.0   # charge-proportional coordination (FactSage oxide convention)
MAX_FREE_COMPONENTS = 4          # free self-assessment cap; 5+ is premium

# Atomic masses (g/mol) for the elements this tool supports as cations, plus oxygen.
ATOMIC_MASS = {
    "O": 15.9994, "Mg": 24.305, "Al": 26.982, "Si": 28.085, "Ca": 40.078,
    "Ti": 47.867, "Cr": 51.996, "Mn": 54.938, "Fe": 55.845, "Na": 22.990, "K": 39.098,
    "Li": 6.94, "Cl": 35.453,
}

SUPPORT_EMAIL = "info@odinzen.io"


class PremiumFeatureError(Exception):
    """Raised when a spec exceeds the free component cap (self-assess is free to 4 components)."""


@dataclass
class Component:
    """One oxide component: its stoichiometry, charge, endmember thermodynamics, and source.

    The endmember pure-liquid Gibbs energy is assembled as
        G_liq(T) = G_solid(T) + dHfus*(1 - T/Tm)
        G_solid(T) = dHf(298) + [H(T)-H(298)] - T*[S(298) + INT Cp/T dT]
    with the solid heat capacity in Haas-Fisher form Cp = a + b*T + c*T^-2.

    liq_beta (optional) adds a below-Tm liquid recalibration dG = beta*(T - Tm), continuous at
    Tm and zero above it - the standard supercooled-liquid / liquidus adjustment (e.g. the
    FeO-SiO2 v0.3 FeO(l) treatment). Leave it 0 unless a liquidus fit demands it.
    """
    name: str                 # oxide formula, e.g. "FeO", "SiO2"
    cation: str               # cation element symbol, e.g. "Fe", "Si"
    charge: float             # cation charge (+2, +4)
    n_cation: float           # cations per formula unit (1 for FeO/SiO2)
    n_oxygen: float           # oxygens per formula unit (1 for FeO, 2 for SiO2)
    dHf: float                # standard enthalpy of formation at 298 K (J/mol)
    S298: float               # standard entropy at 298 K (J/mol/K)
    a: float                  # Haas-Fisher solid Cp coefficients (Cp = a + b*T + c*T^-2)
    b: float
    c: float
    Tm: float                 # melting point (K)
    dHfus: float              # enthalpy of fusion (J/mol)
    source: str               # provenance: citation + locator for every number above
    liq_beta: float = 0.0     # optional below-Tm liquid recalibration slope (J/mol/K)
    z_cat: float = 0.0        # explicit cation coordination; 0 = charge * z_per_charge


@dataclass
class ExcessTerm:
    """One MQMX excess term L * chi_A^p * chi_B^q on the binary's (A,B,O,O) quadruplet.

    code is 'Q' (quadruplet-fraction basis, the usual choice) or 'G'. L = a + b*T (enthalpy a,
    entropy b). p acts on the first component of the binary, q on the second.

    add_cat/r express a TERNARY dependence (Poschmann Eq. 25-26, the FactSage
    additional-mixing-constituent mechanism): the term is further multiplied by the
    third cation's pair-fraction factor with exponent r. pycalphad evaluates this;
    the C engine's support status is checked at read time - do not ship a file
    carrying add_cat until the engine evaluates it.
    """
    a: float                  # L enthalpy part (J/mol)
    b: float = 0.0            # L entropy/temperature part (J/mol/K)
    p: int = 0                # exponent on the first binary component
    q: int = 0                # exponent on the second binary component
    code: str = "Q"
    add_cat: str = ""         # component NAME of the additional (ternary) cation, or ""
    r: int = 0                # exponent of the additional constituent (exponents slot 3)


@dataclass
class BinaryExcess:
    """The fitted liquid-excess parameters for one binary sub-system (first, second).

    Order matters: p/q in each term act on (first, second) respectively, so keep the same order
    the fit used. terms is the list of ExcessTerm; source is the provenance of the fit/data.
    """
    first: str                # component name, e.g. "Mg" oxide side... use the oxide name
    second: str
    terms: list
    source: str = ""


@dataclass
class SystemSpec:
    """A complete slag system: 2..4 oxide components + the binary excesses between them.

    Raises PremiumFeatureError at construction if more than four components are given.
    """
    name: str
    components: list           # list[Component]
    binaries: list = field(default_factory=list)   # list[BinaryExcess]
    version: str = "v0.1"
    provenance: str = ""

    def __post_init__(self):
        n = len(self.components)
        if n < 2:
            raise ValueError("a slag system needs at least two components")
        if n > MAX_FREE_COMPONENTS:
            raise PremiumFeatureError(
                f"{n}-component self-assessment is a premium feature. Free database-building "
                f"covers up to {MAX_FREE_COMPONENTS} components (one past FactSage's free tier); "
                f"five and up - the real multicomponent industrial systems - are Odinzen's "
                f"premium tier. Email {SUPPORT_EMAIL}.")
        names = [c.name for c in self.components]
        if len(set(names)) != n:
            raise ValueError(f"duplicate component names: {names}")

    def component(self, name: str) -> Component:
        for c in self.components:
            if c.name == name:
                return c
        raise KeyError(f"no component named {name!r} in {[c.name for c in self.components]}")


# --------------------------------------------------------------------------- Gibbs assembly
def solid_gibbs_coeffs(dHf, S298, a, b, c):
    """Six ChemSage coefficients [A,B,C,D,E,F] of the SOLID Gibbs energy on the term basis
    (1, T, T*lnT, T^2, T^3, 1/T), for Cp = a + b*T + c*T^-2."""
    A = dHf - a * T0 - 0.5 * b * T0 * T0 + c / T0
    B = a - S298 + a * math.log(T0) + b * T0 - 0.5 * c / (T0 * T0)
    C = -a
    D = -0.5 * b
    E = 0.0
    F = -0.5 * c
    return [A, B, C, D, E, F]


def liquid_gibbs_coeffs(comp: Component):
    """Solid coefficients plus the fusion contribution dHfus*(1 - T/Tm)."""
    A, B, C, D, E, F = solid_gibbs_coeffs(comp.dHf, comp.S298, comp.a, comp.b, comp.c)
    A += comp.dHfus
    B += -comp.dHfus / comp.Tm
    return [A, B, C, D, E, F]


def _below_tm_intervals(base, Tm, beta):
    """Two Gibbs intervals: base + beta*(T-Tm) below Tm (continuous, zero at/above Tm)."""
    if not beta:
        return [(6000.0, base)]
    corr = list(base)
    corr[0] += -Tm * beta
    corr[1] += beta
    return [(Tm, corr), (6000.0, base)]


# ------------------------------------------------------------------------------ .dat writer
def _fmt(x):
    return f"{x:.12E}"


def write_dat(spec: SystemSpec, anion_sym="O", anion_charge=2.0, z_per_charge=None,
              family="oxide-slag") -> str:
    """Serialize the system to a ChemSage SUBQ .dat string (single anion, liquid only).

    The anion defaults to oxide (O, charge 2); pass e.g. anion_sym="Cl", anion_charge=1.0
    for a common-anion chloride salt. Component.n_oxygen then counts anions per formula.
    z_per_charge sets the coordination convention: the module default (charge-proportional,
    the oxide-slag convention validated against pycalphad) unless overridden - monovalent
    salts use z_per_charge=6.0, the published MQM salt convention.
    family only labels the header comment ("open <family> database"); pass "molten-salt"
    for the chloride systems.
    """
    comps = spec.components
    n_cat = len(comps)
    cations = [c.cation for c in comps]
    elements = cations + [anion_sym]
    masses = [ATOMIC_MASS[e] for e in elements]

    L = []
    ap = L.append
    prov = spec.provenance or "user-supplied literature data"
    ap(f" System {spec.name}  open {family} database {spec.version} (provenance: {prov})")
    ap(f"    {len(elements)}    1    {n_cat}    0")          # n_el, n_soln, n_cat, n_stoich
    ap(" " + "                       ".join(elements))
    ap("   " + "              ".join(f"{m:.9f}" for m in masses))
    ap("    6   1   2   3   4   5   6")                       # Gibbs term basis
    ap("    6   1   2   3   4   5   6")                       # excess term basis

    phase = f"{spec.name}-liquid"
    ap(f" {phase}")
    ap(" SUBQ")
    ap(f"   {n_cat}   {n_cat}")                               # n_pairs, n_quads (MQMZ rows)
    for c in comps:
        stoich_el = [(c.n_cation if el == c.cation else (c.n_oxygen if el == anion_sym else 0.0))
                     for el in elements]
        base = liquid_gibbs_coeffs(c)
        intervals = _below_tm_intervals(base, c.Tm, c.liq_beta)
        ap(f" {c.name}")
        ap(f"   1   {len(intervals)}   " + "   ".join(f"{s:.1f}" for s in stoich_el))
        for t_max, coeffs in intervals:
            ap(f"  {t_max:.4f}   " + "   ".join(_fmt(v) for v in coeffs))
        ap("  " + "   ".join(f"{v:.5f}" for v in [c.n_cation, c.n_oxygen, 0.0, 0.0, 0.0]))
        ap("  1.3774438")

    an_idx = n_cat + 1                                        # anion numbered after the cations
    ap(f"   {n_cat}   1")                                     # n_cat, n_an
    ap(" " + "                     ".join(f"{c.cation}+{int(c.charge)}" for c in comps))
    ap(f" {anion_sym}")
    ap("  " + "      ".join(f"{c.charge:.5f}" for c in comps))   # cation charges
    ap("   " + "   ".join("1" for _ in comps))                  # cation groups
    ap(f"  {anion_charge:.5f}")                                # anion charge magnitude
    ap("   1")                                                 # anion group
    ap("   " + "   ".join(str(i) for i in range(1, n_cat + 1)))  # pair cation indices
    ap("   " + "   ".join("1" for _ in comps))                  # pair anion indices
    zpc = Z_PER_CHARGE if z_per_charge is None else z_per_charge
    for i, c in enumerate(comps, start=1):
        z_cat = getattr(c, "z_cat", 0.0) or c.charge * zpc
        # pure-pair charge neutrality (Pelton eq 23): q_cat/Z_cat = q_an/Z_an
        z_an = z_cat * anion_charge / c.charge
        ap(f"   {i}   {i}   {an_idx}   {an_idx}   "
           f"{z_cat:.7f}   {z_cat:.7f}   {z_an:.7f}   {z_an:.7f}")

    # excess (Muggianu from the binaries); a ternary/higher term is zero unless supplied.
    idx = {c.name: i for i, c in enumerate(comps, start=1)}
    excess_lines = []
    for be in spec.binaries:
        ia, ib = idx[be.first], idx[be.second]
        for t in be.terms:
            add_cat = idx[t.add_cat] if getattr(t, "add_cat", "") else 0
            r = getattr(t, "r", 0)
            excess_lines.append("   1")
            excess_lines.append(f" {t.code}   {ia}   {ib}   {an_idx}   {an_idx}   "
                                f"{t.p}   {t.q}   {r}   0")
            excess_lines.append("  " + "   ".join("0.00000000" for _ in range(6)))
            excess_lines.append("  " + "   ".join("0.00000000" for _ in range(6)))
            excess_lines.append(f"   {add_cat}   0   " + "   ".join(_fmt(v) for v in
                                [t.a, t.b, 0.0, 0.0, 0.0, 0.0]))
    excess_lines.append("   0")
    L.extend(excess_lines)
    return "\n".join(L) + "\n"


# --------------------------------------------------------------- open starter oxide library
# Well-sourced open endmembers, ready to drop into a Component. Every number traces to an open
# compilation (see the per-oxide `source`). Users add their own the same way.
def _oxide(name, cation, charge, n_cation, n_oxygen, dHf, S298, a, b, c, Tm, dHfus, source):
    return Component(name=name, cation=cation, charge=charge, n_cation=n_cation,
                     n_oxygen=n_oxygen, dHf=dHf, S298=S298, a=a, b=b, c=c, Tm=Tm,
                     dHfus=dHfus, source=source)


STARTER_OXIDES = {
    "SiO2": _oxide("SiO2", "Si", 4.0, 1.0, 2.0, -908400.0, 43.4, 72.75, 1.300e-3, -4.132e6,
                   1996.0, 9581.0,
                   "Robie & Hemingway 1995 (USGS Bull. 2131) + NIST-JANAF (Chase 1998)"),
    "MgO": _oxide("MgO", "Mg", 2.0, 1.0, 1.0, -601500.0, 26.95, 48.2425, 3.906019e-3, -1.1082e6,
                  3098.0, 77000.0,
                  "CODATA (dHf,S298) + NIST-JANAF periclase Cp/fusion (Chase 1998)"),
    "FeO": _oxide("FeO", "Fe", 2.0, 1.0, 1.0, -272044.0, 60.752, 50.66300, 8.711283e-3,
                  -3.13381e5, 1650.0, 24058.0,
                  "NIST-JANAF FeO(cr) (Chase 1998); Haas-Fisher fit to 6 points 298-1500 K"),
    "CaO": _oxide("CaO", "Ca", 2.0, 1.0, 1.0, -635100.0, 38.1, 51.85, 2.444e-3, -9.340e5,
                  2845.0, 79500.0,
                  "dHf/S298 CODATA; Tm CRC Handbook (2845 K); dHfus JANAF/MgO-analog estimate"),
}


def starter_component(name: str, **overrides) -> Component:
    """A copy of a starter-library oxide, with optional field overrides (e.g. liq_beta)."""
    if name not in STARTER_OXIDES:
        raise KeyError(f"{name!r} not in the starter library {sorted(STARTER_OXIDES)}; "
                       f"supply your own Component with sourced endmember data")
    base = STARTER_OXIDES[name]
    return Component(**{**base.__dict__, **overrides})


# ------------------------------------------------------- fit a binary excess to activity data
# The "engine as its own optimizer" path: fit the binary liquid excess to measured component
# activities (as done for FeO-SiO2 v0.3, CaO-SiO2 v0.2). Uses the exact 1-D quadruplet solve for
# a 2-cation/1-anion liquid (the general SLSQP solver is too noisy for finite-difference chemical
# potentials), ported from data/*/_activity.py and generalized to any oxide pair.
@dataclass
class ActivityPoint:
    """One measured component activity in the binary liquid.

    x_second: bulk mole fraction of the SECOND component (the binary's `second`).
    activity: measured activity (liquid-oxide reference, a -> 1 for the pure component).
    of: which component the activity is for - "first" or "second".
    T: temperature (K).  source: provenance (paper + figure/table).
    """
    x_second: float
    activity: float
    of: str
    T: float
    source: str = ""


def _binary_activity_solver(inp, atoms_first, atoms_second):
    """Return functions (gm, activities) for a 2-cation/1-anion liquid described by `inp`.

    Quad order for two cations A,B and one anion O is Q0=(A,A,O,O), Q1=(A,B,O,O), Q2=(B,B,O,O);
    the cation moles are linear in the three quad fractions, so mass balance pins two of them to
    the mixed fraction X1 and GM is a clean 1-D minimum. gm(x) is per mole of atoms at second-
    component mole fraction x; activities(x,T) returns (a_first, a_second) on the liquid ref."""
    import numpy as np
    from scipy.optimize import minimize_scalar
    from mqmqa import equilibrium as eq

    Za, Zb = inp["Za"], inp["Zb"]
    c0 = 1.0 / Za[0] + 1.0 / Zb[0]
    a1 = 1.0 / Za[1]
    c2 = 1.0 / Za[2] + 1.0 / Zb[2]
    b1 = 1.0 / Zb[1]

    def quad_fracs(x, X1):
        num = x * c0 * (1.0 - X1) + X1 * (x * a1 - (1.0 - x) * b1)
        den = (1.0 - x) * c2 + x * c0
        X2 = num / den
        return np.array([1.0 - X1 - X2, X1, X2])

    def x1_hi(x):
        lo, hi = 0.0, 1.0
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            X = quad_fracs(x, mid)
            lo, hi = (mid, hi) if (X[0] >= 0 and X[2] >= 0) else (lo, mid)
        return max(lo - 1e-9, 1e-12)

    def gm(x):
        x = min(max(x, 1e-9), 1.0 - 1e-9)
        def obj(X1):
            X = np.clip(quad_fracs(x, X1), 1e-300, None)
            return eq.gibbs_per_quad(inp, X) / sum(eq.element_moles(inp, X).values())
        return minimize_scalar(obj, bounds=(0.0, x1_hi(x)), method="bounded",
                               options={"xatol": 1e-12}).fun

    def g_total(n1, n2):
        return gm(n2 / (n1 + n2)) * (atoms_first * n1 + atoms_second * n2)

    def g_pure(which):
        return gm(1.0 - 1e-9) * atoms_second if which == "second" else gm(1e-9) * atoms_first

    def activities(x, T, h=2e-4):
        n1, n2 = 1.0 - x, x
        mu2 = (g_total(n1, n2 + h) - g_total(n1, n2 - h)) / (2.0 * h)
        mu1 = (g_total(n1 + h, n2) - g_total(n1 - h, n2)) / (2.0 * h)
        a1_ = math.exp((mu1 - g_pure("first")) / (R * T))
        a2_ = math.exp((mu2 - g_pure("second")) / (R * T))
        return a1_, a2_

    return gm, activities


def fit_binary_excess(first: Component, second: Component, points, powers=((0, 0),),
                      fit_entropy=True, x0=None, source="", scratch_dir=None) -> BinaryExcess:
    """Fit the binary liquid excess to measured activities (engine as optimizer).

    `powers` are the (p, q) exponents of the excess terms to fit (default one symmetric term).
    Each term contributes an enthalpy `a` and, if `fit_entropy`, a temperature part `b*T`. Returns
    the fitted BinaryExcess. Reproduces the published assessment path (e.g. FeO-SiO2 v0.3).
    `scratch_dir` relocates the fit's inner rebuild files for callers that must keep scratch
    in-tree; default is the OS temp dir.
    """
    import numpy as np
    from scipy.optimize import least_squares
    import mqmqa
    from mqmqa import equilibrium as eq

    powers = list(powers)
    nfit = len(powers) * (2 if fit_entropy else 1)
    atoms1 = first.n_cation + first.n_oxygen
    atoms2 = second.n_cation + second.n_oxygen
    tmp = _scratch_path(f"{first.cation}{second.cation}_fit", scratch_dir)

    def terms_from(vec):
        terms = []
        for i, (p, q) in enumerate(powers):
            if fit_entropy:
                a, b = vec[2 * i], vec[2 * i + 1]
            else:
                a, b = vec[i], 0.0
            terms.append(ExcessTerm(a=a, b=b, p=p, q=q))
        return terms

    def residual(vec):
        spec = SystemSpec(f"{first.name}-{second.name}", [first, second],
                          [BinaryExcess(first.name, second.name, terms_from(vec))])
        tmp.write_text(write_dat(spec), encoding="ascii")
        d = mqmqa.Database.read(str(tmp))
        p = d.phase_index(f"{first.name.upper()}-{second.name.upper()}-LIQUID")
        inp = eq.build_inputs(d, p, 1500.0, components=[first.cation, second.cation, "O"])
        res = []
        for pt in points:
            inp_T = eq.build_inputs(d, p, pt.T, components=[first.cation, second.cation, "O"])
            _, activities = _binary_activity_solver(inp_T, atoms1, atoms2)
            a1, a2 = activities(pt.x_second, pt.T)
            model = a1 if pt.of == "first" else a2
            res.append(math.log(model) - math.log(pt.activity))
        return np.asarray(res, float)

    if x0 is None:
        x0 = []
        for _ in powers:
            x0 += [-40000.0, 15.0] if fit_entropy else [-40000.0]
    sol = least_squares(residual, x0, xtol=1e-12, ftol=1e-12)
    rms = float(np.sqrt(np.mean(sol.fun ** 2)))
    be = BinaryExcess(first.name, second.name, terms_from(sol.x),
                      source=source or f"fitted to {len(points)} measured activities (RMS ln a={rms:.3f})")
    be.rms_ln_a = rms
    return be


def evaluate_binary_activities(spec: SystemSpec, points, dat_path=None, scratch_dir=None):
    """Model activities (pure-liquid reference) of a two-component spec at each point.

    Evaluates through the same write -> read -> solve path a user runs; passing the emitted
    file via `dat_path` therefore validates the artifact on disk, not the in-memory fit.
    Returns [(a_first, a_second), ...] ordered like `points` (only x_second and T are read).
    """
    import mqmqa

    from mqmqa import equilibrium as eq

    if len(spec.components) != 2:
        raise ValueError("activity evaluation needs a two-component spec")
    first, second = spec.components
    if dat_path is None:
        dat_path = _scratch_path(f"{first.cation}{second.cation}_eval", scratch_dir)
        Path(dat_path).write_text(write_dat(spec), encoding="ascii")
    d = mqmqa.Database.read(str(dat_path))
    p = d.phase_index(f"{spec.name.upper()}-LIQUID")
    if p < 0:
        raise ValueError(f"phase {spec.name.upper()}-LIQUID not found in {dat_path}")
    atoms1 = first.n_cation + first.n_oxygen
    atoms2 = second.n_cation + second.n_oxygen
    out = []
    for pt in points:
        inp = eq.build_inputs(d, p, pt.T, components=[first.cation, second.cation, "O"])
        _, activities = _binary_activity_solver(inp, atoms1, atoms2)
        out.append(activities(pt.x_second, pt.T))
    return out


def _scratch_path(tag, scratch_dir=None):
    """A temp .dat path for the fit's inner rebuilds. OS temp dir unless the caller
    supplies one (some consumers must keep every scratch file in their own tree)."""
    import os
    import tempfile
    base = Path(scratch_dir) if scratch_dir else Path(tempfile.gettempdir())
    return base / f"_dbbuild_{tag}_{os.getpid()}.dat"
