"""G-code (Chi) excess terms in reciprocal salts vs pycalphad.

Where both sublattices mix, the Chi variables of a SUBQ phase also count the
quadruplets that pair the fixed ion with another ion of its sublattice, each with
weight 1.0 as pycalphad evaluates them (the published equation writes 0.5); a SUBG
phase leaves them out. Synthetic Na-K-Mg / Cl-F-Br salts written as uTDB and converted
to .dat (and to SUBG) cover cation- and anion-side terms, several exponent pairs, and
chemical groups on either sublattice. The group interpolation of a Q term, or of a
term with an additional cation, stays refused there.
"""
import math
import os
import re
import sys
import warnings

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))
import roundtrip_util as U  # noqa: E402
import test_chemical_groups as G  # noqa: E402
from mqmqa import Database  # noqa: E402
from mqmqa import equilibrium as eq  # noqa: E402
from mqmqa._abi import c_equilibrate  # noqa: E402

pytest.importorskip("pycalphad")

EXPONENTS = [(1, 0), (0, 1), (1, 1), (2, 1), (1, 3)]


def _subg(path):
    """The SUBQ salt as a SUBG phase: one zeta for the phase instead of one per pair."""
    text = path.read_text()
    subg = text.replace("   1.3774438\n", "").replace(" SUBQ\n", " SUBG\n   1.3774438\n")
    assert subg.count("1.3774438") == 1 and " SUBG\n" in subg
    out = path.with_name(path.stem + "_subg.dat")
    out.write_text(subg)
    return out


def _salt(tmp_path, soln, cats, ans, cgrp, agrp, terms):
    path = G._as_dat(tmp_path, "salt", cats, ans, cgrp, agrp, terms)
    return path if soln == "SUBQ" else _subg(path)


def _oracle(path, db, p):
    """pycalphad's excess of phase L as a function of (T, quadruplet fractions), the
    model built once."""
    from pycalphad import Database as PDatabase, variables as v
    from pycalphad.models.model_mqmqa import ModelMQMQA
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pdb = PDatabase(str(path))
        mod = ModelMQMQA(pdb, [e for e, _ in db.elements] + ["VA"], "L")
        expr = mod.excess_mixing_energy(pdb)

    def ec(sp):
        return (next(iter(sp.constituents)) if sp.constituents else sp.name), abs(sp.charge)
    rc = [(re.match(r"[A-Z]+", c["name"]).group(0), c["charge"]) for c in db.cations(p)]
    ra = [(re.match(r"[A-Z]+", a["name"]).group(0), a["charge"]) for a in db.anions(p)]
    ci = {c: rc.index(ec(c)) for c in mod.cations}
    ai = {a: ra.index(ec(a)) for a in mod.anions}
    sites = {}
    for A, B, X, Y in mod._quadruplets:
        a, b, x, y = ci[A], ci[B], ai[X], ai[Y]
        sites[mod._X_ijkl(A, B, X, Y)] = (min(a, b), max(a, b), min(x, y), max(x, y))

    def excess(T, Xkey):
        subs = {v.T: T}
        subs.update({s: Xkey[q] for s, q in sites.items()})
        return float(expr.subs(subs))
    return excess


def _random_X(rng, quads):
    w = rng.uniform(0.2, 1.0, len(quads))
    return dict(zip(quads, w / w.sum()))


def _compare(path):
    """Worst relative deviation of the engine's excess from pycalphad's."""
    db = Database.read(str(path))
    p = db.phase_index("L")
    assert db.excess_unsupported(p) is None
    theirs = _oracle(path, db, p)
    rng = np.random.default_rng(7)
    quads = G._quads(db, p)
    worst = 0.0
    for T in (1273.37, 1873.37):
        for _ in range(3):
            Xkey = _random_X(rng, quads)
            ours, ref = G._excess(db, p, T, Xkey), theirs(T, Xkey)
            d = U.rel(ours, ref)
            assert d < U.ORACLE_TOL, (T, ours, ref)
            worst = max(worst, d)
    return worst


@pytest.mark.parametrize("pq", EXPONENTS, ids=lambda pq: f"p{pq[0]}q{pq[1]}")
@pytest.mark.parametrize("side", ["cation", "anion"])
def test_single_term_matches_pycalphad(tmp_path, side, pq):
    term = ("G", "NA", "K", "CL", "CL") if side == "cation" else ("G", "NA", "NA", "CL", "F")
    path = _salt(tmp_path, "SUBQ", ["NA", "K"], ["CL", "F"], [1, 1], [1, 1],
                 [term + pq + (0, None, -9000)])
    print(f"\n{side} p,q = {pq}: worst relative deviation {_compare(path):.3g}")


FOUR = [("G", "K", "NA", "F", "F", 2, 1, 0, None, -6000),    # species in reverse order
        ("G", "NA", "K", "CL", "CL", 1, 2, 0, None, 4000),
        ("G", "K", "K", "F", "CL", 1, 1, 0, None, -5000),
        ("G", "NA", "NA", "CL", "F", 3, 1, 0, None, 2500),
        ("Q", "NA", "K", "CL", "CL", 1, 1, 0, None, -3000)]
TERMS32 = [("G", "NA", "K", "CL", "CL", 1, 1, 0, None, -9000),
           ("G", "K", "MG", "F", "F", 2, 1, 0, None, -4000),
           ("G", "MG", "MG", "CL", "F", 1, 2, 0, None, -6000)]
TERMS23 = [("G", "K", "K", "F", "CL", 1, 1, 0, None, -8000),
           ("G", "NA", "NA", "CL", "BR", 2, 1, 0, None, -3000),
           ("G", "NA", "K", "BR", "BR", 1, 2, 0, None, -5000)]
TERMS33 = TERMS32 + [("G", "NA", "NA", "F", "BR", 1, 3, 0, None, -2000),
                     ("G", "NA", "MG", "BR", "BR", 3, 1, 0, None, 1500)]


@pytest.mark.parametrize("soln", ["SUBQ", "SUBG"])
def test_every_term_on_both_sides_matches_pycalphad(tmp_path, soln):
    path = _salt(tmp_path, soln, ["NA", "K"], ["CL", "F"], [1, 1], [1, 1], FOUR)
    print(f"\n{soln} four terms: worst relative deviation {_compare(path):.3g}")


@pytest.mark.parametrize("soln", ["SUBQ", "SUBG"])
@pytest.mark.parametrize("groups", G.ASSIGNMENTS)
def test_cation_groups_match_pycalphad(tmp_path, groups, soln):
    path = _salt(tmp_path, soln, ["NA", "K", "MG"], ["CL", "F"], list(groups), [1, 1], TERMS32)
    print(f"\n{soln} cation groups {groups}: worst relative deviation {_compare(path):.3g}")


@pytest.mark.parametrize("soln", ["SUBQ", "SUBG"])
@pytest.mark.parametrize("groups", G.ASSIGNMENTS)
def test_anion_groups_match_pycalphad(tmp_path, groups, soln):
    path = _salt(tmp_path, soln, ["NA", "K"], ["F", "CL", "BR"], [1, 1], list(groups), TERMS23)
    print(f"\n{soln} anion groups {groups}: worst relative deviation {_compare(path):.3g}")


@pytest.mark.parametrize("soln", ["SUBQ", "SUBG"])
@pytest.mark.parametrize("cg,ag", [("111", "111"), ("121", "112"), ("123", "121"), ("122", "123")])
def test_groups_on_both_sublattices_match_pycalphad(tmp_path, cg, ag, soln):
    path = _salt(tmp_path, soln, ["NA", "K", "MG"], ["CL", "F", "BR"], list(cg), list(ag),
                 TERMS33)
    print(f"\n{soln} groups {cg}/{ag}: worst relative deviation {_compare(path):.3g}")


def _chi(Xkey, i, j, f, m, cation_side, w):
    """chi_i, chi_j of a 2x2 salt with the reciprocal quadruplets at weight w (species
    indices; f the fixed ion, m the other ion of its sublattice)."""
    def x(a, b):
        a, b = min(a, b), max(a, b)
        fm = (min(f, m), max(f, m))
        if cation_side:
            return Xkey[(a, b, f, f)] + w * Xkey[(a, b) + fm]
        return Xkey[(f, f, a, b)] + w * Xkey[fm + (a, b)]
    den = x(i, i) + x(i, j) + x(j, j)
    return x(i, i) / den, x(j, j) / den


@pytest.mark.parametrize("side", ["cation", "anion"])
def test_comparison_catches_a_wrong_weight(tmp_path, side):
    """The published weight 0.5, or leaving the reciprocal terms out, misses pycalphad
    by far more than the tolerance, so the comparisons above would catch either. A
    single term's excess is proportional to chi_i^p chi_j^q, so rescaling the engine's
    value gives the energy each weight would produce."""
    p, q = 2, 1
    term = ("G", "NA", "K", "CL", "CL") if side == "cation" else ("G", "NA", "NA", "CL", "F")
    path = _salt(tmp_path, "SUBQ", ["NA", "K"], ["CL", "F"], [1, 1], [1, 1],
                 [term + (p, q, 0, None, -9000)])
    db = Database.read(str(path))
    ph = db.phase_index("L")
    assert [c["name"] for c in db.cations(ph)] == ["NA+1", "K+1"]
    assert [a["name"] for a in db.anions(ph)] == ["CL-1", "F-1"]
    na, k, cl, f = 0, 1, 0, 1
    ijfm = (na, k, cl, f) if side == "cation" else (cl, f, na, k)
    theirs = _oracle(path, db, ph)
    rng = np.random.default_rng(3)
    for _ in range(4):
        Xkey = _random_X(rng, G._quads(db, ph))
        ours, ref = G._excess(db, ph, 1500.0, Xkey), theirs(1500.0, Xkey)
        assert U.rel(ours, ref) < U.ORACLE_TOL

        def with_weight(w):
            ci, cj = _chi(Xkey, *ijfm, side == "cation", w)
            ci1, cj1 = _chi(Xkey, *ijfm, side == "cation", 1.0)
            return ours * (ci ** p * cj ** q) / (ci1 ** p * cj1 ** q)
        assert U.rel(with_weight(1.0), ref) < U.ORACLE_TOL
        for w in (0.5, 0.0):
            assert U.rel(with_weight(w), ref) > 1e6 * U.ORACLE_TOL, w


def test_subq_and_subg_differ_where_the_reciprocal_terms_count(tmp_path):
    """The two solution types give different Chi in a reciprocal phase, so the SUBG
    matches above are not the SUBQ terms being ignored."""
    terms = [("G", "NA", "K", "CL", "CL", 2, 1, 0, None, -9000)]
    sq = Database.read(str(_salt(tmp_path, "SUBQ", ["NA", "K"], ["CL", "F"], [1, 1], [1, 1],
                                 terms)))
    sg = Database.read(str(_subg(tmp_path / "salt.dat")))
    p, pg = sq.phase_index("L"), sg.phase_index("L")
    Xkey = _random_X(np.random.default_rng(5), G._quads(sq, p))
    a, b = G._excess(sq, p, 1500.0, Xkey), G._excess(sg, pg, 1500.0, Xkey)
    assert math.isfinite(a) and math.isfinite(b) and abs(a - b) > 1e-3 * abs(b)


def test_reciprocal_equilibrium_matches_pycalphad(tmp_path):
    """The C minimizer (the browser's path) carries the solution type through to the
    excess: its GM is the directly validated energy at its own X, and matches
    pycalphad's equilibrium on a SUBQ reciprocal salt."""
    from pycalphad import Database as PDatabase, equilibrium, variables as v
    terms = [("G", "NA", "K", "CL", "CL", 1, 2, 0, None, -30000),
             ("G", "K", "K", "CL", "F", 2, 1, 0, None, -25000),
             ("G", "NA", "NA", "CL", "F", 1, 1, 0, None, 20000)]
    path = _salt(tmp_path, "SUBQ", ["NA", "K"], ["CL", "F"], [1, 1], [1, 1], terms)
    db = Database.read(str(path))
    T = 1273.0
    inp = eq.build_inputs(db, db.phase_index("L"), T)
    assert inp["soln_type"] == 1
    res = c_equilibrate(inp, {"NA": 0.3, "K": 0.2, "CL": 0.35, "F": 0.15})
    assert res["comp_error"] < 1e-9
    direct = eq.gibbs_per_quad(inp, res["X"]) / sum(eq.element_moles(inp, res["X"]).values())
    assert U.rel(res["GM"], direct) < U.REL_TOL, (res["GM"], direct)
    out = equilibrium(PDatabase(str(path)), ["NA", "K", "CL", "F", "VA"], ["L"],
                      {v.T: T, v.P: 1e5, v.N: 1, v.X("K"): 0.2, v.X("CL"): 0.35,
                       v.X("F"): 0.15})
    gm_py = float(out.GM.values.squeeze())
    assert abs(res["GM"] - gm_py) <= 1e-4 * max(1.0, abs(gm_py)), (res["GM"], gm_py)


# ---- still refused, loudly ----

def test_q_groups_in_reciprocal_phase_refused(tmp_path):
    path = _salt(tmp_path, "SUBQ", ["NA", "K", "MG"], ["CL", "F"], [1, 2, 1], [1, 1],
                 [("Q", "NA", "K", "CL", "CL", 1, 1, 0, None, -9000)])
    G._refused(Database.read(str(path)), "L",
               r"Q excess term .* more than one anion; mixed chemical groups are not supported")


def test_g_groups_with_additional_cation_in_reciprocal_phase_refused(tmp_path):
    path = _salt(tmp_path, "SUBQ", ["NA", "K", "MG"], ["CL", "F"], [1, 2, 1], [1, 1],
                 [("G", "NA", "K", "CL", "CL", 1, 1, 1, "MG", -9000)])
    G._refused(Database.read(str(path)), "L",
               r"G excess term .* more than one anion; mixed chemical groups are not supported")
