"""Validate the C ChemSage `.dat` reader end to end.

Two levels of check:

1. Structure: elements, the SUBQ phase's cations/anions (names, charges, chemical
   groups), and the stoichiometric compounds, against pycalphad's own parse.
2. Energy, with no pycalphad at runtime: every input the three energy routines
   need (pair Gibbs energies, coordination numbers, excess coefficients, zeta,
   the quadruplet enumeration) is taken from the C reader, and the resulting
   reference / ideal-mixing / excess energies are compared to pycalphad's model.
   pycalphad is only the oracle. Cases span SUBQ and SUBG, a reciprocal
   multi-anion slag and single-anion salts, and multi-charge cations.
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

pytest.importorskip("pycalphad")
from pycalphad import Database, variables as v
from pycalphad.models.model_mqmqa import ModelMQMQA

import mqmqa

DBDIR = Path("C:/Users/busta/Code/pycalphad/pycalphad/tests/databases")
SHISHIN = DBDIR / "Shishin_Fe-Sb-O-S_slag.dat"
T = 1873.0

# (file, phase, components). Chosen to span: SUBQ reciprocal slag; SUBG binary
# salt with Q and G excess; SUBG salt with two cation charges.
ENERGY_CASES = [
    (SHISHIN, "SLAG-LIQ", ["FE", "SB", "S", "O", "VA"]),
    (DBDIR / "MQMQA-tern-tests.dat", "L_SUBG_2", ["CU", "NI", "VA"]),
    (DBDIR / "KF-NIF2_switched.dat", "LIQUID2", ["NI", "K", "F"]),
]


def _element(name):
    """Leading element symbol of a species name, e.g. FE2+ -> FE, O -> O."""
    return re.match(r"[A-Z]+", name).group(0)


# --- structure ---

def test_structure_matches_pycalphad():
    db = mqmqa.Database.read(SHISHIN)
    dbf = Database(str(SHISHIN))

    got = {n: m for n, m in db.elements}
    assert set(got) == set(dbf.elements)
    for el, ref in dbf.refstates.items():
        assert abs(got[el] - ref["mass"]) < 1e-9

    p = db.phase_index("SLAG-LIQ")
    assert p >= 0 and db.is_subq(p) == 1

    hints = dbf.phases["SLAG-LIQ"].model_hints["mqmqa"]
    for c in db.cations(p):
        matches = [sp for sp in hints["chemical_groups"]["cations"]
                   if _element(c["name"]) in sp.constituents and abs(sp.charge) == c["charge"]]
        assert len(matches) == 1, c
        assert hints["chemical_groups"]["cations"][matches[0]] == c["group"]
    for a in db.anions(p):
        matches = [sp for sp in hints["chemical_groups"]["anions"]
                   if _element(a["name"]) in sp.constituents and abs(sp.charge) == a["charge"]]
        assert len(matches) == 1, a
        assert hints["chemical_groups"]["anions"][matches[0]] == a["group"]

    py_stoich = {ph for ph in dbf.phases if ph != "SLAG-LIQ"}
    assert set(db.stoich) == py_stoich


# --- energy, sourced entirely from the C reader ---

def _energies_from_reader(path, phase):
    db = mqmqa.Database.read(path)
    p = db.phase_index(phase)
    cats, ans = db.cations(p), db.anions(p)
    n_cat, n_an = len(cats), len(ans)
    q_cat = [c["charge"] for c in cats]
    q_an = [a["charge"] for a in ans]

    quad_ca, quad_cb, quad_ax, quad_ay = mqmqa.enumerate_quadruplets(n_cat, n_an)
    quads = list(zip(quad_ca, quad_cb, quad_ax, quad_ay))
    mz = db.mqmz(p)

    def Z(is_cat, sp, A, B, X, Y):
        return mqmqa.coordination(is_cat, sp, A, B, X, Y, n_cat, n_an, q_cat, q_an,
                                  mz["A"], mz["B"], mz["X"], mz["Y"], mz["Z"])

    Za = [Z(1, A, A, B, X, Y) for A, B, X, Y in quads]
    Zb = [Z(1, B, A, B, X, Y) for A, B, X, Y in quads]
    Zx = [Z(0, X, A, B, X, Y) for A, B, X, Y in quads]
    Zy = [Z(0, Y, A, B, X, Y) for A, B, X, Y in quads]

    def key(A, B, X, Y):
        return (min(A, B), max(A, B), min(X, Y), max(X, Y))

    Xkey = {key(*q): 0.03 + 0.005 * i for i, q in enumerate(quads)}
    Xarr = [Xkey[key(*q)] for q in quads]

    pr = db.pairs(p, T)
    Ztab = []
    for pc in pr["cat"]:
        for A, B, X, Y in quads:
            Ztab.append(Z(1, pc, A, B, X, Y) if pc in (A, B) else 1.0)
    ref = mqmqa.reference_energy(quad_ca, quad_cb, quad_ax, quad_ay, Xarr,
                                 pr["cat"], pr["an"], pr["G"], pr["stoich"], Ztab)

    zeta = [0.0] * (n_cat * n_an)
    for c, a, z in zip(pr["cat"], pr["an"], pr["zeta"]):
        zeta[c * n_an + a] = z
    ideal = mqmqa.ideal_mixing_energy(T, n_cat, n_an,
                                      quad_ca, quad_cb, quad_ax, quad_ay, Xarr,
                                      Za, Zb, Zx, Zy, zeta, db.is_subq(p))

    mx = db.mqmx(p, T)
    # excess is validated only where the C routine implements the code: Q (any
    # exponents) and G with zero exponents; cation or anion mixing (mix 0/1).
    supported = all(
        mix in (0, 1) and code in (0, 1) and not (code == 1 and (pe or qe))
        for mix, code, pe, qe in zip(mx["mix"], mx["code"], mx["p"], mx["q"])
    )
    exc = None
    if supported:
        exc = mqmqa.excess_energy(n_cat, n_an, quad_ca, quad_cb, quad_ax, quad_ay, Xarr,
                                  Za, Zb, Zx, Zy,
                                  mx["mix"], mx["code"], mx["A"], mx["B"], mx["X"], mx["Y"],
                                  mx["p"], mx["q"], mx["L"])
    reader_cat = [(_element(c["name"]), c["charge"]) for c in cats]
    reader_an = [(_element(a["name"]), a["charge"]) for a in ans]
    return db, p, Xkey, reader_cat, reader_an, (ref, ideal, exc)


def _sp_element_charge(sp):
    el = next(iter(sp.constituents)) if sp.constituents else sp.name
    return (el, abs(sp.charge))


def _energies_from_pycalphad(path, phase, comps, Xkey, reader_cat, reader_an):
    dbf = Database(str(path))
    mod = ModelMQMQA(dbf, comps, phase)
    cations = list(mod.cations)
    anions = list(mod.anions)

    # pycalphad does not necessarily order constituents by file order, so map each
    # pycalphad species onto the C sublattice index by (element, charge). The
    # index-tuple keys then refer to the same physical quadruplet on both sides.
    ci = {c: reader_cat.index(_sp_element_charge(c)) for c in cations}
    ai = {a: reader_an.index(_sp_element_charge(a)) for a in anions}

    def key(A, B, X, Y):
        a, b, x, y = ci[A], ci[B], ai[X], ai[Y]
        return (min(a, b), max(a, b), min(x, y), max(x, y))

    subs = {v.T: T}
    subs.update({mod._X_ijkl(*q): Xkey[key(*q)] for q in mod._quadruplets})
    ref = float(mod.reference_energy(dbf).subs(subs))
    ideal = float(mod.ideal_mixing_energy(dbf).subs(subs))
    exc = float(mod.excess_mixing_energy(dbf).subs(subs))
    return ref, ideal, exc


@pytest.mark.parametrize("path,phase,comps", ENERGY_CASES)
def test_energy_terms_from_reader_match_pycalphad(path, phase, comps):
    db, p, Xkey, rcat, ran, (ref_c, ideal_c, exc_c) = _energies_from_reader(path, phase)
    ref_py, ideal_py, exc_py = _energies_from_pycalphad(path, phase, comps, Xkey, rcat, ran)
    assert abs(ref_c - ref_py) <= 1e-6 * max(1.0, abs(ref_py)), (ref_c, ref_py)
    assert abs(ideal_c - ideal_py) <= 1e-6 * max(1.0, abs(ideal_py)), (ideal_c, ideal_py)
    if exc_c is not None:
        assert abs(exc_c - exc_py) <= 1e-6 * max(1.0, abs(exc_py)), (exc_c, exc_py)


if __name__ == "__main__":
    for path, phase, comps in ENERGY_CASES:
        db, p, Xkey, rcat, ran, (ref_c, ideal_c, exc_c) = _energies_from_reader(path, phase)
        ref_py, ideal_py, exc_py = _energies_from_pycalphad(path, phase, comps, Xkey, rcat, ran)
        tag = f"{path.stem}/{phase}"
        print(f"{tag:32s} ref d={abs(ref_c-ref_py):.1e} ideal d={abs(ideal_c-ideal_py):.1e}"
              + (f" exc d={abs(exc_c-exc_py):.1e}" if exc_c is not None else " exc n/a"))
