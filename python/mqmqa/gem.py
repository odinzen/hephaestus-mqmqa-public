"""General equilibrium for any number of elements and phases (docs/GENERAL_EQUILIBRIUM.md)."""
from __future__ import annotations

import math
from dataclasses import dataclass

from ._abi import _ffi, _lib
from ._database import Database, _s


@dataclass
class PhaseSet:
    phase: str          # solution phase or compound name
    amount: float       # moles of atoms per mole of atoms of the system
    x: dict             # element -> mole fraction within the set


@dataclass
class Result:
    sets: list
    G: float            # J per mole of atoms of the system
    mu: dict            # element -> chemical potential (J/mol); absent ones are left out
    residual: float     # most negative driving force of any phase against mu, J per
                        # mole of atoms (~0 at an equilibrium)
    passes: int
    exact: bool = False  # finished by solving the equilibrium conditions exactly
    beyond_data: list = None  # (species, K where its data end, K used): energies taken above
                              # the end of a species' data, the last range carried on

    def phases(self):
        return sorted(s.phase for s in self.sets)


def equilibrium(db: Database, T: float, amounts: dict, suspend=(), grid=0, max_iter=0,
                P: float = 101325.0) -> Result:
    """Equilibrium of `db` at T (K) and P (Pa) for element amounts {element: moles};
    `suspend` names solution phases or compounds to hold out. P acts on the ideal gas
    phase of a ChemSage file; condensed phases carry no volume data."""
    els = [e for e, _ in db.elements]
    upper = {e.upper(): i for i, e in enumerate(els)}
    b = _ffi.new("double[]", len(els))
    for el, n in amounts.items():
        if el.upper() not in upper:
            raise KeyError(f"element {el} is not in the database")
        b[upper[el.upper()]] = float(n)
    names = list(db.phase_names)
    stoich = [_s(_lib.mqmqa_db_stoich_name(db._db, j)) for j in range(_lib.mqmqa_db_num_stoich(db._db))]
    mask = _ffi.new("int[]", len(names) + len(stoich))
    for name in suspend:
        if name in names:
            mask[names.index(name)] = 1
        elif name in stoich:
            mask[len(names) + stoich.index(name)] = 1
        else:
            raise KeyError(f"no phase or compound {name}")
    _lib.mqmqa_db_beyond_clear(db._db)
    P_before = _lib.mqmqa_db_pressure(db._db)
    if _lib.mqmqa_db_set_pressure(db._db, float(P)):
        raise ValueError(_s(_lib.mqmqa_db_error()))
    try:
        r = _lib.mqmqa_gem_equilibrium(db._db, float(T), b, mask, int(grid), int(max_iter))
    finally:
        _lib.mqmqa_db_set_pressure(db._db, P_before)
    if r == _ffi.NULL:
        raise RuntimeError(_s(_lib.mqmqa_db_error()) or "equilibrium failed")
    try:
        x = _ffi.new("double[]", len(els))
        sets = []
        for k in range(_lib.mqmqa_gem_num_sets(r)):
            tag = _lib.mqmqa_gem_set_phase(r, k)
            _lib.mqmqa_gem_set_x(r, k, x)
            sets.append(PhaseSet(names[tag] if tag >= 0 else stoich[-tag - 1],
                                 _lib.mqmqa_gem_set_amount(r, k),
                                 {els[e]: x[e] for e in range(len(els)) if x[e] > 0.0}))
        mu = _ffi.new("double[]", len(els))
        _lib.mqmqa_gem_mu(r, mu)
        return Result(sets, _lib.mqmqa_gem_G(r),
                      {els[e]: mu[e] for e in range(len(els)) if not math.isnan(mu[e])},
                      _lib.mqmqa_gem_residual(r), _lib.mqmqa_gem_passes(r), bool(_lib.mqmqa_gem_exact(r)),
                      db.beyond_data(elements=[el for el, n in amounts.items() if n > 0]))
    finally:
        _lib.mqmqa_gem_free(r)


@dataclass
class Minimum:
    df: float           # G - mu.x, J per mole of atoms (below zero: a state below the plane)
    G: float            # J per mole of atoms
    y: dict             # ion -> fraction on its sublattice


def driving_force(db: Database, phase, T: float, mu: dict, n: int = 4, elements=None) -> list:
    """Lowest points of G - mu.x for MQMQA phase `phase` (name or index) at T, the
    composition free, for chemical potentials mu {element: J/mol} (absent ones count as 0).
    At an equilibrium nothing lies below zero; a negative minimum is a state of the phase
    that would lower the Gibbs energy. Distinct minima, lowest first. With `elements`, the
    ions of any other element are taken out of the phase (a subsystem of the database)."""
    p = db._phase(db.phase_index(phase) if isinstance(phase, str) else phase)
    if db.phase_kind(p) != 0:
        raise ValueError(f"phase {phase!r} is not an MQMQA phase")
    els = [e for e, _ in db.elements]
    upper = {k.upper(): v for k, v in mu.items()}
    mu_c = _ffi.new("double[]", [float(upper.get(e.upper(), 0.0)) for e in els])
    names = [ion["name"] for ion in db.cations(p) + db.anions(p)]
    y = _ffi.new("double[]", n * len(names))
    g = _ffi.new("double[]", n)
    df = _ffi.new("double[]", n)
    keep = _ffi.NULL
    if elements is not None:
        present = {e.upper() for e in elements}
        keep = _ffi.new("int[]", [int(e.upper() in present) for e in els])
    k = _lib.mqmqa_driving_force_db(db._db, p, float(T), mu_c, keep, n, y, g, df)
    if k < 0:
        raise RuntimeError(_s(_lib.mqmqa_db_error()) or "driving force failed")
    return [Minimum(df[i], g[i], {names[j]: y[i * len(names) + j] for j in range(len(names))})
            for i in range(k)]
