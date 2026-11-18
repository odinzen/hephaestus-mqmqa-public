"""General equilibrium solver: cases with a known answer, and pycalphad on shipped databases."""
import math
import sys
from pathlib import Path

import pytest
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

import mqmqa
from mqmqa import gem
from mqmqa._abi import _ffi, _lib

R = 8.31451

HEADER = """ELEMENT VA VACUUM 0 0 0 !
ELEMENT A BLANK 10 0 0 !
ELEMENT B BLANK 10 0 0 !
"""


def _db(body):
    return mqmqa.Database.read_string(HEADER + body)


def test_two_compounds_and_the_lever_rule():
    db = _db("""PHASE AB2 % 2 1 2 !
CONSTITUENT AB2 :A:B: !
PARAMETER G(AB2,A:B;0) 298.15 -30000; 6000 N !
PHASE A3B % 2 3 1 !
CONSTITUENT A3B :A:B: !
PARAMETER G(A3B,A:B;0) 298.15 -32000; 6000 N !
""")
    r = gem.equilibrium(db, 800.0, {"A": 0.5, "B": 0.5})
    assert r.phases() == ["A3B", "AB2"]
    # x_B = 0.5 between x_B = 1/4 (A3B) and 2/3 (AB2): fractions by the lever rule
    f_ab2 = (0.5 - 0.25) / (2 / 3 - 0.25)
    amt = {s.phase: s.amount for s in r.sets}
    assert amt["AB2"] == pytest.approx(f_ab2, abs=1e-9)
    g_ab2, g_a3b = -30000 / 3, -32000 / 4
    assert r.G == pytest.approx(f_ab2 * g_ab2 + (1 - f_ab2) * g_a3b, abs=1e-6)


def test_ideal_solution_has_ideal_chemical_potentials():
    db = _db("""PHASE LIQ % 1 1 !
CONSTITUENT LIQ :A,B: !
PARAMETER G(LIQ,A;0) 298.15 0; 6000 N !
PARAMETER G(LIQ,B;0) 298.15 0; 6000 N !
""")
    T, xb = 1000.0, 0.3
    r = gem.equilibrium(db, T, {"A": 1 - xb, "B": xb})
    assert r.phases() == ["LIQ"]
    Rdb = db.gas_constant
    assert r.mu["B"] == pytest.approx(Rdb * T * math.log(xb), abs=0.01)
    assert r.mu["A"] == pytest.approx(Rdb * T * math.log(1 - xb), abs=0.01)


def test_symmetric_miscibility_gap_matches_the_binodal():
    T, L = 1000.0, 3.0 * R * 1000.0
    db = _db(f"""PHASE LIQ % 1 1 !
CONSTITUENT LIQ :A,B: !
PARAMETER G(LIQ,A;0) 298.15 0; 6000 N !
PARAMETER G(LIQ,B;0) 298.15 0; 6000 N !
PARAMETER G(LIQ,A,B;0) 298.15 {L}; 6000 N !
""")
    # symmetric regular solution: ln(x/(1-x)) = (L/RT)(2x-1)
    x_b = brentq(lambda x: math.log(x / (1 - x)) - (L / (R * T)) * (2 * x - 1), 1e-6, 0.49)
    r = gem.equilibrium(db, T, {"A": 0.5, "B": 0.5})
    xs = sorted(s.x.get("B", 0.0) for s in r.sets)
    assert len(r.sets) == 2 and r.phases() == ["LIQ", "LIQ"]
    assert xs[0] == pytest.approx(x_b, abs=1e-4)
    assert xs[1] == pytest.approx(1 - x_b, abs=1e-4)


def test_composition_out_of_reach_fails_loudly():
    db = _db("""PHASE AB % 2 1 1 !
CONSTITUENT AB :A:B: !
PARAMETER G(AB,A:B;0) 298.15 -1000; 6000 N !
""")
    with pytest.raises(RuntimeError, match="reaches"):
        gem.equilibrium(db, 800.0, {"A": 0.7, "B": 0.3})


pycalphad = pytest.importorskip("pycalphad")
from pycalphad import Database, equilibrium, variables as v  # noqa: E402

ALZN = ROOT / "data" / "al-zn" / "AlZn.tdb"


@pytest.mark.parametrize("T,xzn", [(700, 0.2), (500, 0.3), (400, 0.6), (650, 0.9), (900, 0.5)])
def test_alzn_matches_pycalphad(T, xzn):
    db = mqmqa.Database.read(ALZN)
    r = gem.equilibrium(db, T, {"AL": 1 - xzn, "ZN": xzn})
    pdb = Database(str(ALZN))
    eq = equilibrium(pdb, ["AL", "ZN", "VA"], list(pdb.phases),
                     {v.T: T, v.P: 101325, v.N: 1, v.X("ZN"): xzn})
    assert r.phases() == sorted(set(p for p in eq.Phase.values.ravel() if p))
    assert r.G == pytest.approx(float(eq.GM.squeeze()), abs=1e-3)


FMS = ROOT / "data" / "feo-mgo-sio2" / "FeO-MgO-SiO2-combined.dat"


@pytest.mark.parametrize("T,cat", [
    (1873, {"FE": .3, "MG": .2, "SI": .5}),     # liquid
    (1673, {"FE": .4, "MG": .3, "SI": .3}),     # liquid + olivine
    (1473, {"FE": .2, "MG": .5, "SI": .3}),     # magnesiowustite + olivine
    (1573, {"FE": .1, "MG": .2, "SI": .7}),     # cristobalite + orthopyroxene
])
def test_feo_mgo_sio2_matches_pycalphad(T, cat):
    amt = dict(cat)
    amt["O"] = cat["FE"] + cat["MG"] + 2 * cat["SI"]
    tot = sum(amt.values())
    r = gem.equilibrium(mqmqa.Database.read(FMS), T, amt)
    pdb = Database(str(FMS))
    conds = {v.T: T, v.P: 101325, v.N: 1}
    conds.update({v.X(el): n / tot for el, n in amt.items() if el != "FE"})
    eq = equilibrium(pdb, sorted(amt), list(pdb.phases), conds)
    assert r.phases() == sorted(set(p for p in eq.Phase.values.ravel() if p))
    assert r.G == pytest.approx(float(eq.GM.squeeze()), abs=0.01)
    assert r.residual > -0.05


def _figure_node(i, j):
    """cation fractions at node (i, j) of the Figure 4a grid, 150 steps per side"""
    fe, si = (i / 150 + 1e-4) / 1.0003, (j / 150 + 1e-4) / 1.0003
    return {"FE": fe, "MG": 1.0 - fe - si, "SI": si}


@pytest.mark.parametrize("T,node", [
    (2110, (0, 50)),       # forsterite with 1e-4 Fe, melting at 2080 K here
    (1482, (100, 50)),     # fayalite with 1e-4 Mg, at 1475 K
])
def test_congruent_melt_with_a_trace_is_all_liquid(T, node):
    # liquid and olivine share the bulk composition and only the liquid carries the trace,
    # which left its potential free and the solver above the all-liquid state by 20-77 J/mol
    cat = _figure_node(*node)
    amt = dict(cat)
    amt["O"] = cat["FE"] + cat["MG"] + 2 * cat["SI"]
    db = mqmqa.Database.read(FMS)
    r = gem.equilibrium(db, T, amt)
    liq = gem.equilibrium(db, T, amt, suspend=["OLIVINE", "ORTHOPYROXENE", "MAGNESIOWUSTITE"])
    assert r.phases() == ["FEO-MGO-SIO2-LIQUID"]
    assert r.exact
    assert r.G == pytest.approx(liq.G, abs=1e-3)


def test_default_grid_retries_when_it_does_not_finish():
    # silica-rich liquid of FeO-MgO-SiO2 next to its gap: grid 6 alone stops 1.9 J/mol high
    amt = _figure_node(0, 147)
    amt["O"] = amt["FE"] + amt["MG"] + 2 * amt["SI"]
    db = mqmqa.Database.read(FMS)
    solids = ["OLIVINE", "ORTHOPYROXENE", "MAGNESIOWUSTITE"]
    six = gem.equilibrium(db, 1974.0, amt, suspend=solids, grid=6)
    r = gem.equilibrium(db, 1974.0, amt, suspend=solids)
    assert not six.exact
    assert r.exact
    assert r.G < six.G - 1.0


CFMS =ROOT / "data" / "cao-feo-mgo-sio2" / "CaO-FeO-MgO-SiO2-combined.dat"


@pytest.mark.parametrize("T,cat", [
    (1873, {"CA": .25, "FE": .05, "MG": .2, "SI": .5}),
    (1673, {"CA": .3, "FE": .05, "MG": .15, "SI": .5}),
])
def test_four_oxide_finds_the_liquid_pycalphad_misses(T, cat):
    """At these points pycalphad's all-phase equilibrium (default settings) returns solids
    whose Gibbs energy lies above its own liquid-only result; the liquid is stable."""
    amt = dict(cat)
    amt["O"] = cat["CA"] + cat["FE"] + cat["MG"] + 2 * cat["SI"]
    tot = sum(amt.values())
    r = gem.equilibrium(mqmqa.Database.read(CFMS), T, amt)
    pdb = Database(str(CFMS))
    liq = next(p for p in pdb.phases if "LIQUID" in p)
    conds = {v.T: T, v.P: 101325, v.N: 1}
    conds.update({v.X(el): n / tot for el, n in amt.items() if el != "CA"})
    g_liq = float(equilibrium(pdb, sorted(amt), [liq], conds).GM.squeeze())
    assert r.phases() == [liq]            # one set: no leftover columns reported
    assert r.G == pytest.approx(g_liq, abs=0.05)
    assert r.residual > -0.05


def test_four_oxide_lp_does_not_reenter_a_basic_column():
    """Here drift in the basis inverse once gave a basic column a reduced cost just past
    the tolerance; the simplex re-entered it in its own place until the pivot cap."""
    cat = {"CA": .5, "FE": .05, "MG": .1, "SI": .35}
    amt = dict(cat)
    amt["O"] = cat["CA"] + cat["FE"] + cat["MG"] + 2 * cat["SI"]
    tot = sum(amt.values())
    r = gem.equilibrium(mqmqa.Database.read(CFMS), 1773, amt)
    pdb = Database(str(CFMS))
    conds = {v.T: 1773, v.P: 101325, v.N: 1}
    conds.update({v.X(el): n / tot for el, n in amt.items() if el != "CA"})
    eq = equilibrium(pdb, sorted(amt), list(pdb.phases), conds)
    assert r.phases() == sorted(set(p for p in eq.Phase.values.ravel() if p))
    assert r.G == pytest.approx(float(eq.GM.squeeze()), abs=0.01)


def _cfms_amounts(cat):
    amt = dict(cat)
    amt["O"] = cat["CA"] + cat["FE"] + cat["MG"] + 2 * cat["SI"]
    return amt


def _liquid_gibbs(db, T, amt):
    """The engine's fixed-composition liquid solve, J per mole of atoms."""
    els = [e for e, _ in db.elements]
    liq = next(i for i, n in enumerate(db.phase_names) if "LIQUID" in n)
    t = _ffi.new("double[]", [amt.get(e, 0.0) for e in els])
    return _lib.mqmqa_equilibrate_db(db._db, liq, T, t, _ffi.NULL, _ffi.NULL)


def test_liquid_driving_force_vanishes_at_its_own_equilibrium():
    """At a one-liquid equilibrium the liquid touches the plane of the chemical potentials at
    the bulk composition and nowhere lies below it."""
    cat = {"CA": .3, "FE": .05, "MG": .15, "SI": .5}
    db = mqmqa.Database.read(CFMS)
    r = gem.equilibrium(db, 1673, _cfms_amounts(cat))
    liq = next(n for n in db.phase_names if "LIQUID" in n)
    low = gem.driving_force(db, liq, 1673, r.mu)[0]
    assert abs(low.df) < 1e-3
    for ion, frac in low.y.items():
        el = ion.rstrip("+-0123456789").upper()
        if el in cat:
            assert frac == pytest.approx(cat[el], abs=1e-4)


def test_chemical_potentials_are_the_liquid_tangent():
    """The reported potentials are the slopes of the liquid's own energy. Exchanging a little
    of one cation for another changes n.G by the difference of their potentials (oxygen
    following by charge). Fitted to differences of the nested solve, they were off by kJ."""
    cat = {"CA": .3, "FE": .05, "MG": .15, "SI": .5}
    db = mqmqa.Database.read(CFMS)
    T = 1673.0
    r = gem.equilibrium(db, T, _cfms_amounts(cat))
    oxy = {"CA": 1, "FE": 1, "MG": 1, "SI": 2}
    for a, b in [("CA", "MG"), ("FE", "MG"), ("SI", "MG")]:
        h = 1e-4
        n_g = []
        for sgn in (1, -1):
            c = dict(cat)
            c[a] += sgn * h
            c[b] -= sgn * h
            amt = _cfms_amounts(c)
            n_g.append(_liquid_gibbs(db, T, amt) * sum(amt.values()))
        slope = (n_g[0] - n_g[1]) / (2 * h)
        exchange = r.mu[a] - r.mu[b] + (oxy[a] - oxy[b]) * r.mu.get("O", 0.0)
        assert slope == pytest.approx(exchange, abs=1.0)
    assert r.G == pytest.approx(sum(r.mu.get(e, 0.0) * n for e, n in _cfms_amounts(cat).items())
                                / sum(_cfms_amounts(cat).values()), abs=1e-3)


def test_four_oxide_assemblage_below_pycalphad_is_real():
    """pycalphad's all-phase equilibrium (default settings) returns olivine + wollastonite
    here. Liquid + olivine + clinopyroxene is 56 J/mol lower, and pycalphad's own energies of
    those three sets, each computed at the composition the engine reports, add up to the
    engine's total."""
    cat = {"CA": .2, "FE": .05, "MG": .35, "SI": .4}
    T = 1573
    amt = _cfms_amounts(cat)
    tot = sum(amt.values())
    r = gem.equilibrium(mqmqa.Database.read(CFMS), T, amt)
    pdb = Database(str(CFMS))
    conds = {v.T: T, v.P: 101325, v.N: 1}
    conds.update({v.X(el): n / tot for el, n in amt.items() if el != "CA"})
    g_pyc = float(equilibrium(pdb, sorted(amt), list(pdb.phases), conds).GM.squeeze())
    assert r.G < g_pyc - 50.0
    total = 0.0
    for s in r.sets:
        comps = sorted(set(s.x) | {"O"})
        c = {v.T: T, v.P: 101325, v.N: 1}
        c.update({v.X(e): s.x.get(e, 0.0) for e in comps[1:]})
        total += s.amount * float(equilibrium(pdb, comps, [s.phase], c).GM.squeeze())
    assert total == pytest.approx(r.G, abs=0.01)
    for el, n in amt.items():
        assert sum(s.amount * s.x.get(el, 0.0) for s in r.sets) == pytest.approx(n / tot, abs=1e-9)


def test_liquid_drives_out_the_assemblage_pycalphad_reports():
    """Holding out the liquid and clinopyroxene leaves pycalphad's olivine + wollastonite;
    against its potentials the liquid lies hundreds of J/mol below the plane."""
    cat = {"CA": .2, "FE": .05, "MG": .35, "SI": .4}
    db = mqmqa.Database.read(CFMS)
    liq = next(n for n in db.phase_names if "LIQUID" in n)
    amt = _cfms_amounts(cat)
    full = gem.equilibrium(db, 1573, amt)
    held = gem.equilibrium(db, 1573, amt, suspend=[liq, "CLINOPYROXENE"])
    assert held.phases() == ["OLIVINE", "WOLLASTONITE"]
    assert held.G - full.G == pytest.approx(56.37, abs=0.01)
    assert gem.driving_force(db, liq, 1573, held.mu)[0].df < -500.0
    assert gem.driving_force(db, liq, 1573, full.mu)[0].df > -0.01


def test_tangent_rows_hold_at_the_equilibrium_potentials():
    """Each row the potential fit takes from the liquid, dG/dX_q - dG/dX_q0 against the
    element amounts of the two quadruplets, holds for the equilibrium potentials: the
    exact energy gradient at the liquid's internal equilibrium."""
    cat = {"CA": .3, "FE": .05, "MG": .15, "SI": .5}
    db = mqmqa.Database.read(CFMS)
    T = 1673.0
    amt = _cfms_amounts(cat)
    r = gem.equilibrium(db, T, amt)
    els = [e for e, _ in db.elements]
    liq = next(i for i, n in enumerate(db.phase_names) if "LIQUID" in n)
    nq, ne = 10, len(els)
    A = _ffi.new("double[]", nq * ne)
    b = _ffi.new("double[]", nq)
    tgt = _ffi.new("double[]", [amt.get(e, 0.0) for e in els])
    rows = _lib.mqmqa_tangent_rows_db(db._db, liq, T, tgt, _ffi.NULL, nq, A, b)
    assert rows >= 3
    for w in range(rows):
        lhs = sum(A[w * ne + e] * r.mu.get(els[e], 0.0) for e in range(ne))
        assert lhs == pytest.approx(b[w], abs=0.5)


@pytest.mark.parametrize("T,cat", [
    (1773, {"FE": .3, "MG": .2, "SI": .5}),
    (1973, {"FE": .05, "MG": .55, "SI": .4}),
])
def test_liquid_restricted_to_a_subsystem_matches_pycalphad(T, cat):
    """CaO left out of the four-oxide liquid: the restricted solve equals pycalphad's own
    subsystem liquid. The full phase with CaO at exactly zero comes out 1-2.6 kJ/mol high."""
    db = mqmqa.Database.read(CFMS)
    els = [e for e, _ in db.elements]
    liq = next(i for i, n in enumerate(db.phase_names) if "LIQUID" in n)
    amt = dict(cat, O=cat["FE"] + cat["MG"] + 2 * cat["SI"])
    tot = sum(amt.values())
    tgt = _ffi.new("double[]", [amt.get(e, 0.0) for e in els])
    keep = _ffi.new("int[]", [int(e != "CA") for e in els])
    g = _lib.mqmqa_equilibrate_sub_db(db._db, liq, float(T), tgt, keep)
    pdb = Database(str(CFMS))
    conds = {v.T: T, v.P: 101325, v.N: 1}
    conds.update({v.X(el): n / tot for el, n in amt.items() if el != "FE"})
    eq = equilibrium(pdb, sorted(amt), [db.phase_names[liq]], conds)
    assert sum(1 for p in eq.Phase.values.ravel() if p) == 1      # one liquid, not the gap
    assert g == pytest.approx(float(eq.GM.squeeze()), abs=0.01)


@pytest.mark.parametrize("T,cat", [
    (1873, {"FE": .1, "MG": .3, "SI": .6}),        # liquid + cristobalite
    (1973, {"FE": .05, "MG": .55, "SI": .4}),      # liquid + olivine
])
def test_subsystem_of_a_larger_database_matches_pycalphad(T, cat):
    """A CaO-free slag computed from the four-oxide database: its liquid takes part with
    the CaO ions taken out, rather than being left out of the calculation."""
    amt = dict(cat, O=cat["FE"] + cat["MG"] + 2 * cat["SI"])
    tot = sum(amt.values())
    r = gem.equilibrium(mqmqa.Database.read(CFMS), T, amt)
    pdb = Database(str(CFMS))
    conds = {v.T: T, v.P: 101325, v.N: 1}
    conds.update({v.X(el): n / tot for el, n in amt.items() if el != "FE"})
    eq = equilibrium(pdb, sorted(amt), list(pdb.phases), conds)
    assert r.phases() == sorted(set(p for p in eq.Phase.values.ravel() if p))
    assert r.G == pytest.approx(float(eq.GM.squeeze()), abs=0.01)
    assert r.residual > -0.05


@pytest.mark.parametrize("T,cat", [
    (1973, {"FE": .05, "MG": .55, "SI": .4}),
    (1673, {"FE": .4, "MG": .3, "SI": .3}),
])
def test_four_oxide_database_without_cao_is_the_three_oxide_one(T, cat):
    """The CaO-FeO-MgO-SiO2 file, computed with no CaO, gives what the FeO-MgO-SiO2 file
    gives: the shipped databases agree on their common subsystem."""
    amt = dict(cat, O=cat["FE"] + cat["MG"] + 2 * cat["SI"])
    r4 = gem.equilibrium(mqmqa.Database.read(CFMS), T, amt)
    r3 = gem.equilibrium(mqmqa.Database.read(FMS), T, amt)
    strip = lambda name: "LIQUID" if "LIQUID" in name else name
    assert sorted(strip(p) for p in r4.phases()) == sorted(strip(p) for p in r3.phases())
    assert r4.G == pytest.approx(r3.G, abs=0.01)


def test_silica_rich_second_liquid_is_found():
    """Near the silica corner the stable state is two liquids, one of them at 98.5% Si on the
    cation sublattice. That minimum is pinned against a corner of the quadruplet space; with
    only centre, corner-push and random-walk starts the search missed it and reported liquid +
    cristobalite 24 J/mol higher."""
    cat = {"CA": 0.95 * 4 / 60, "FE": 0.05, "MG": 0.95 - 0.95 * 54 / 60, "SI": 0.95 * 50 / 60}
    amt = dict(cat, O=cat["CA"] + cat["FE"] + cat["MG"] + 2 * cat["SI"])
    tot = sum(amt.values())
    T = 1990.15
    db = mqmqa.Database.read(CFMS)
    r = gem.equilibrium(db, T, amt)
    liq = next(n for n in db.phase_names if "LIQUID" in n)
    pdb = Database(str(CFMS))
    conds = {v.T: T, v.P: 101325, v.N: 1}
    conds.update({v.X(el): n / tot for el, n in amt.items() if el != "O"})
    eq = equilibrium(pdb, sorted(amt), [liq], conds)
    assert sum(1 for p in eq.Phase.values.ravel() if p) == 2
    assert r.phases() == [liq, liq]
    assert r.G == pytest.approx(float(eq.GM.squeeze()), abs=0.01)
    assert max(s.x["SI"] / (1 - s.x["O"]) for s in r.sets) > 0.98


@pytest.mark.parametrize("path,c,T", [
    (FMS, {"MG": .45, "SI": .55}, 2073.0),
    (FMS, {"FE": .6, "SI": .4}, 1673.0),
    (CFMS, {"CA": .4, "MG": .1, "SI": .5}, 1873.0),
])
def test_liquid_with_an_element_at_zero_matches_pycalphad(path, c, T):
    """The single-liquid solve with an element of the phase at exactly zero (a section's
    edge) takes that element's ions out; with them in it was 1.0-2.6 kJ/mol high."""
    db = mqmqa.Database.read(path)
    els = [e for e, _ in db.elements]
    liq = next(i for i, n in enumerate(db.phase_names) if "LIQUID" in n)
    amt = dict(c, O=sum(x * (2 if k == "SI" else 1) for k, x in c.items()))
    tot = sum(amt.values())
    t = _ffi.new("double[]", [amt.get(e, 0.0) for e in els])
    g = _lib.mqmqa_equilibrate_db(db._db, liq, T, t, _ffi.NULL, _ffi.NULL)
    pdb = Database(str(path))
    first = sorted(amt)[0]
    conds = {v.T: T, v.P: 101325, v.N: 1}
    conds.update({v.X(e): n / tot for e, n in amt.items() if e != first})
    eq = equilibrium(pdb, sorted(amt), [db.phase_names[liq]], conds)
    assert sum(1 for p in eq.Phase.values.ravel() if p) == 1
    assert g == pytest.approx(float(eq.GM.squeeze()), abs=0.01)


def test_passes_resume_when_the_certificate_finds_a_lower_state():
    """A strongly bound AB gas at 1e-5 atm, Cs:I-like: the passes once stopped with the gas
    35 J/mol above its own minimum because a pass found nothing below its plane, while the
    final certificate, searching from the end state, found a point 53 J below. What the
    certificate finds now goes back in and the passes resume. Checked against a direct
    minimization of the gas at the bulk composition."""
    import numpy as np
    from scipy.optimize import minimize

    def rec(name, stoich, g):
        st = "    ".join(f"{s:.1f}" for s in stoich)
        return f" {name}\n   4  1    {st}\n  6000.0000   {g:.4f}   0.0   0.0   0.0   0.0\n 0.0\n 1 0.0 0.00\n"

    sp = [("A", [1, 0], -60000.0), ("A2", [2, 0], -180000.0), ("B", [0, 1], -85000.0),
          ("B2", [0, 2], -155000.0), ("AB", [1, 1], -405000.0), ("A2B2", [2, 2], -860000.0)]
    text = (" System A-B\n    2    1    6    0\n A                        B\n    10.0    10.0\n"
            "   6   1   2   3   4   5   6\n   6   1   2   3   4   5   6\n GAS\n IDMX\n"
            + "".join(rec(n, s, g) for n, s, g in sp))
    db = mqmqa.Database.read_string(text)
    T, P = 873.15, 1e-5 * 101325.0
    r = gem.equilibrium(db, T, {"A": 1.0, "B": 1.0}, P=P)
    assert r.residual > -1e-3

    na = np.array([s[1][0] for s in sp], float)
    nb = np.array([s[1][1] for s in sp], float)

    def y_of(z):
        y = np.exp(z - z.max())
        return y / y.sum()

    _lib.mqmqa_db_set_pressure(db._db, P)
    try:
        # a start in each species' corner, and random ones
        starts = [8.0 * np.eye(6)[k] for k in range(6)] + [np.random.default_rng(s).normal(0, 4, 6) for s in range(10)]
        best = min((minimize(lambda z: db.cef_gibbs(0, list(y_of(z)), T), z0,
                             method="SLSQP", options={"maxiter": 500, "ftol": 1e-13},
                             constraints=[{"type": "eq", "fun": lambda z: y_of(z) @ na - y_of(z) @ nb}])
                    for z0 in starts), key=lambda res: res.fun if res.success else math.inf)
    finally:
        _lib.mqmqa_db_set_pressure(db._db, 101325.0)
    assert r.G == pytest.approx(best.fun, abs=0.01)


def test_gas_potentials_are_exact_for_a_strongly_bound_gas():
    """The same gas: nearly all AB, with 1e-6 of A and B atoms. A composition error of 3e-8 in
    the sampled gas moved mu(A) - mu(B) by tens of J/mol; the exact finish solves the gas's own
    conditions (each species' potential on the plane, the bulk met) and lands on the direct
    solution of the ideal gas, y_j = exp((a_j . mu - g_j)/RT) summing to one at A:B = 1:1."""
    import numpy as np
    from scipy.optimize import fsolve

    def rec(name, stoich, g):
        st = "    ".join(f"{s:.1f}" for s in stoich)
        return f" {name}\n   4  1    {st}\n  6000.0000   {g:.4f}   0.0   0.0   0.0   0.0\n 0.0\n 1 0.0 0.00\n"

    sp = [("A", [1, 0], -60000.0), ("A2", [2, 0], -180000.0), ("B", [0, 1], -85000.0),
          ("B2", [0, 2], -155000.0), ("AB", [1, 1], -405000.0), ("A2B2", [2, 2], -860000.0)]
    text = (" System A-B\n    2    1    6    0\n A                        B\n    10.0    10.0\n"
            "   6   1   2   3   4   5   6\n   6   1   2   3   4   5   6\n GAS\n IDMX\n"
            + "".join(rec(n, s, g) for n, s, g in sp))
    db = mqmqa.Database.read_string(text)
    T, P = 873.15, 1e-5 * 101325.0
    r = gem.equilibrium(db, T, {"A": 1.0, "B": 1.0}, P=P)

    na = np.array([s[1][0] for s in sp], float)
    nb = np.array([s[1][1] for s in sp], float)
    _lib.mqmqa_db_set_pressure(db._db, P)
    try:
        g0 = np.array([db.cef_gibbs(0, list(np.eye(6)[k]), T, per_mole_atoms=False) for k in range(6)])
    finally:
        _lib.mqmqa_db_set_pressure(db._db, 101325.0)
    RT = _lib.mqmqa_db_R_own(db._db) * T

    def y(m):
        return np.exp((na * m[0] + nb * m[1] - g0) / RT)

    def eqs(m):
        return [math.log(y(m).sum()), math.log((y(m) @ na) / (y(m) @ nb))]

    mu = fsolve(eqs, [-2.1e5, -2.1e5], xtol=1e-12)
    assert max(abs(v) for v in eqs(mu)) < 1e-12
    assert y(mu)[0] < 1e-5                       # the regime where sampling alone went wrong
    assert r.mu["A"] == pytest.approx(mu[0], abs=0.01)
    assert r.mu["B"] == pytest.approx(mu[1], abs=0.01)
    assert r.residual > -1e-6


def test_gas_of_many_species_is_sampled_at_every_corner():
    """A 30-species gas whose stable species, B2, is listed second, against a compound AB that
    is 20 kJ worse than B2 gas plus solid A. The grid of that gas has over a million points;
    listing it in order and stopping at the cap kept only compositions of the last species, so
    the gas was never tried and AB came out (Thermochimica TestThermo55: H2 at 1000 atm in a
    29-species gas). The answer here follows from solid A alone fixing mu(A) and the ideal gas
    closing on sum y_j = 1, y_j = exp((a_j mu_A + b_j mu_B - g_j)/RT)."""
    def rec(name, stoich, g):
        st = "    ".join(f"{s:.1f}" for s in stoich)
        return f" {name}\n   4  1    {st}\n  6000.0000   {g:.4f}   0.0   0.0   0.0   0.0\n 0.0\n 1 0.0 0.00\n"

    gas = [("A", (1, 0), 100000.0), ("B2", (0, 2), -300000.0)]
    gas += [(f"A{a}B{b}", (a, b), 200000.0 * (a + b)) for a in range(1, 5) for b in range(1, 8)]
    assert len(gas) == 30
    text = (" System A-B\n    2    1   30    2\n A                        B\n    10.0    10.0\n"
            "   6   1   2   3   4   5   6\n   6   1   2   3   4   5   6\n GAS\n IDMX\n"
            + "".join(rec(n, s, g) for n, s, g in gas)
            + rec("A_S", (1, 0), -20000.0) + rec("AB_S", (1, 1), -150000.0))
    db = mqmqa.Database.read_string(text)
    T = 1000.0
    r = gem.equilibrium(db, T, {"A": 1.0, "B": 1.0}, P=1.0e5)   # 1 bar, the records' reference

    RT = _lib.mqmqa_db_R_own(db._db) * T
    mu_a = -20000.0
    mu_b = brentq(lambda m: math.log(sum(math.exp((a * mu_a + b * m - g) / RT) for _, (a, b), g in gas)),
                  -3e5, 0.0, xtol=1e-9)
    assert r.phases() == ["A_S", "GAS"]
    assert r.G * 2.0 == pytest.approx(mu_a + mu_b, abs=1e-6)
    assert r.residual > -1e-6


CLALNA = ROOT.parent / "thermochimica-ref" / "data" / "ClAlNa.dat"
if not CLALNA.exists():
    CLALNA = Path.home() / "Code" / "thermochimica-ref" / "data" / "ClAlNa.dat"


@pytest.mark.skipif(not CLALNA.exists(), reason="needs Thermochimica's data folder (ClAlNa.dat)")
def test_a_failed_certificate_is_refused_not_returned():
    """NaCl at exactly 1:1 and 1200 K, above its melting point: the solve stayed on the solid
    while the certificate found the liquid 1463 J/mol below it, and the solid was returned as
    the answer. A failed certificate now refuses the result; below the melting point the solid
    is still found, with a clean certificate."""
    db = mqmqa.Database.read(str(CLALNA))
    r = gem.equilibrium(db, 1050.0, {"Na": 1.0, "Cl": 1.0})
    assert r.phases() == ["NACL_S1(S)"] and r.residual > -1e-6
    try:
        r = gem.equilibrium(db, 1200.0, {"Na": 1.0, "Cl": 1.0})
    except RuntimeError as e:
        assert "no equilibrium found" in str(e)
    else:
        assert r.phases() == ["MSSOLN"] and r.residual > -1e-6


@pytest.mark.skipif(not CLALNA.exists(), reason="needs Thermochimica's data folder (ClAlNa.dat)")
def test_a_salt_at_its_formula_composition_is_solved():
    """NaCl and NaAlCl4 at exactly their formulas lie on the plane Cl = Na + 3 Al, and every
    phase of ClAlNa lies on or below it (its Cl2 gas is a dummy). Metal-bearing states (Na
    vapour, the liquid's vacancy, the metals) have zero amount there, but their samples sit a
    hair off the plane and made the solver's bases singular: NaAlCl4 failed ("linear program
    failed") and NaCl at 1200 K came back with its liquid unfound. The reference energies are
    Thermochimica's on the same file, run as a program (2026-11-16)."""
    db = mqmqa.Database.read(str(CLALNA))
    r = gem.equilibrium(db, 1200.0, {"Na": 1.0, "Al": 1.0, "Cl": 4.0})
    assert r.phases() == ["GAS_IDEAL", "MSSOLN"] and r.residual > -1e-6
    assert r.G * 6.0 == pytest.approx(-1579342.153, abs=0.1)
    r = gem.equilibrium(db, 1200.0, {"Na": 1.0, "Cl": 1.0})
    assert r.phases() == ["MSSOLN"] and r.residual > -1e-6
    assert r.G * 2.0 == pytest.approx(-542994.688, abs=1e-3)


CSTE = CLALNA.parent / "CsTe-2.dat"


@pytest.mark.skipif(not CSTE.exists(), reason="needs Thermochimica's data folder (CsTe-2.dat)")
def test_ionic_liquid_of_neutrals_alone_forms_without_its_cation():
    """Pure Te in the Cs-Te ionic liquid (Cs+)(Te-2, Va, Te): with only the neutral on the
    second sublattice the cation sites vanish (P = 0), so the model allows a liquid with no Cs
    at all. It was dropped because its only cation's element was absent ("no phase combination
    reaches this bulk"). Pure Te must be the limit of the liquid with a trace of Cs."""
    db = mqmqa.Database.read(str(CSTE))
    for T in (1000.0, 2500.0):
        r0 = gem.equilibrium(db, T, {"Te": 1.0})
        assert r0.phases() == ["IONIC_LIQUID"] and r0.residual > -1e-6
        gaps = [gem.equilibrium(db, T, {"Te": 1.0, "Cs": xc}).G - r0.G for xc in (1e-6, 1e-8)]
        # dilute mixing lowers G by ~x(ln x + c): small, negative, shrinking with x
        assert gaps[0] < gaps[1] < 0.0
        assert abs(gaps[1]) < 0.01


def test_two_copies_of_one_phase_are_one_set():
    """A ChemSage file lists a phase twice to give it room for a miscibility gap; where none
    opens the copies have one energy and the solver may split an amount between them at one
    composition. That is one composition set (NobleMetals-Kaye's two HCPN gave two before)."""
    def sp(name, stoich, a, b):
        st = "    ".join(f"{s:.1f}" for s in stoich)
        return f" {name}\n   4  1    {st}\n  6000.0000   {a:.4f}   {b:.4f}   0.0   0.0   0.0\n 0.0\n 1 0.0 0.00\n"

    liq = (" LIQ\n RKMP\n" + sp("A", [1.0, 0.0], -1000.0, -10.0) + sp("B", [0.0, 1.0], -2000.0, -12.0)
           + "   2\n   1   2   2\n  20000.0  -5.0  0.0  0.0  0.0  0.0\n  3000.0  0.0  0.0  0.0  0.0  0.0\n   0\n")
    text = (" System A-B\n    2    2    2    2    0\n A                        B\n    10.0    10.0\n"
            "   6   1   2   3   4   5   6\n   6   1   2   3   4   5   6\n" + liq + liq)
    db = mqmqa.Database.read_string(text)
    assert list(db.phase_names) == ["LIQ", "LIQ"]
    # where the solver before this rule split the amount (0.44 + 0.56 of LIQ at x_A = 0.18, 1500 K)
    for T, xa in ((1500.0, 0.18), (1500.0, 0.26), (1500.0, 0.36), (2000.0, 0.35)):
        r = gem.equilibrium(db, T, {"A": xa, "B": 1 - xa})
        assert [s.phase for s in r.sets] == ["LIQ"]
        assert r.sets[0].amount == pytest.approx(1.0, abs=1e-12)
        assert r.sets[0].x["A"] == pytest.approx(xa, abs=1e-9)


def test_sublattice_potentials_are_exact_with_a_dilute_interstitial():
    """(A,B)(Va,C) with additive endmember energies and no excess: each sublattice mixes
    ideally on its own, the site fractions follow from the composition, and every endmember's
    potential is its energy plus RT ln of its two site fractions. With 1e-7 of C the sampled
    compositions alone left mu(C) several J/mol out; the exact finish lands on the formula."""
    db = mqmqa.Database.read_string("""ELEMENT VA VACUUM 0 0 0 !
ELEMENT A BLANK 10 0 0 !
ELEMENT B BLANK 10 0 0 !
ELEMENT C BLANK 10 0 0 !
PHASE S % 2 1 1 !
CONSTITUENT S :A,B:VA,C: !
PARAMETER G(S,A:VA;0) 298.15 0; 6000 N !
PARAMETER G(S,B:VA;0) 298.15 -1000; 6000 N !
PARAMETER G(S,A:C;0) 298.15 -20000; 6000 N !
PARAMETER G(S,B:C;0) 298.15 -21000; 6000 N !
""")
    T, nA, nB, nC = 1000.0, 0.6, 0.4, 1e-7
    r = gem.equilibrium(db, T, {"A": nA, "B": nB, "C": nC})
    assert r.phases() == ["S"] and r.exact
    RT = _lib.mqmqa_gas_constant(_lib.mqmqa_db_R_own(db._db)) * T
    yA, yB = nA / (nA + nB), nB / (nA + nB)
    yC = nC / (nA + nB)
    yVa = 1.0 - yC
    assert r.mu["A"] == pytest.approx(RT * math.log(yA) + RT * math.log(yVa), abs=0.01)
    assert r.mu["B"] == pytest.approx(-1000.0 + RT * math.log(yB) + RT * math.log(yVa), abs=0.01)
    assert r.mu["C"] == pytest.approx(-20000.0 + RT * math.log(yC / yVa), abs=0.01)


def test_ionic_liquid_potentials_are_exact_with_dilute_vacancies():
    """(A+)_P(B-, Va)_Q: one cation of charge 1, so Q = 1 and P = y_B + y_Va = 1, and the
    liquid is two endmembers mixing ideally, A:B (one A and one B) and A:Va (one A). With A
    in excess by 1e-7 the vacancy fraction is 1e-7, and mu(A) = G(A:Va) + RT ln y_Va,
    mu(A) + mu(B) = G(A:B) + RT ln y_B, exactly."""
    def rec(name, stoich, a, b):
        st = "    ".join(f"{s:.1f}" for s in stoich)
        return f" {name}\n   4  1    {st}\n  6000.0000   {a:.4f}   {b:.4f}   0.0   0.0   0.0\n 0.0\n 1 0.0 0.00\n"

    text = (" System A-B\n    2    1    2    0\n A                        B\n    10.0    10.0\n"
            "   6   1   2   3   4   5   6\n   6   1   2   3   4   5   6\n LIQ\n SUBI\n"
            + rec("A+1:B-1", [1.0, 1.0], -50000.0, -10.0) + rec("A+1:VA", [1.0, 0.0], -1000.0, -12.0)
            + "   1   2\n A+1\n B-1  VA\n   2\n   1.0\n   -1.0 -1.0\n   1 1\n   1 2\n   0\n")
    db = mqmqa.Database.read_string(text)
    T, excess = 1200.0, 1e-7
    r = gem.equilibrium(db, T, {"A": 1.0, "B": 1.0 - excess})
    assert r.phases() == ["LIQ"] and r.exact
    RT = db.R * T
    g_ab, g_av = -50000.0 - 10.0 * T, -1000.0 - 12.0 * T
    mu_a = g_av + RT * math.log(excess)
    mu_b = g_ab + RT * math.log(1.0 - excess) - mu_a
    assert r.mu["A"] == pytest.approx(mu_a, abs=0.01)
    assert r.mu["B"] == pytest.approx(mu_b, abs=0.01)


CAS = ROOT / "data" / "cao-al2o3-sio2" / "CaO-Al2O3-SiO2.dat"


def test_oxide_system_is_finished_exactly_in_the_reduced_space():
    """CaO-Al2O3-SiO2 at 1673 K, little CaO: liquid and mullite. Oxygen is tied to the cations
    by charge balance in every phase, so the solver works with the cations' potentials, oxygen
    folded in, and the exact finish now runs there too (it was skipped for every slag). Checked
    against pycalphad's own numbers: the liquid alone at the liquid's composition gives the
    same potentials, and liquid plus mullite at pycalphad's energies gives the same G.
    pycalphad's default all-phase solve lands 790 J/mol higher here (corundum, anorthite,
    cristobalite)."""
    amt = {"CA": 0.036326, "AL": 0.507330, "SI": 0.456344, "O": 1.710009}
    T = 1673.0
    r = gem.equilibrium(mqmqa.Database.read(CAS), T, amt)
    assert r.exact and r.phases() == ["AL6SI2O13", "CAO-ALO1.5-SIO2-LIQUID"]
    assert "O" not in r.mu
    pdb = Database(str(CAS))
    liq = next(st for st in r.sets if st.phase == "CAO-ALO1.5-SIO2-LIQUID")
    mul = next(st for st in r.sets if st.phase == "AL6SI2O13")
    conds = {v.T: T, v.P: 101325, v.N: 1}
    conds.update({v.X(el): liq.x[el] for el in ("CA", "AL", "SI")})
    eq = equilibrium(pdb, sorted(amt), ["CAO-ALO1.5-SIO2-LIQUID"], conds)
    mu = {str(c): float(m) for c, m in zip(eq.component.values, eq.MU.values.ravel())}
    for el, o in (("CA", 1.0), ("AL", 1.5), ("SI", 2.0)):
        assert r.mu[el] == pytest.approx(mu[el] + o * mu["O"], abs=0.05)
    from pycalphad import calculate
    g_mul = float(calculate(pdb, sorted(amt), "AL6SI2O13", T=T, P=101325, N=1).GM.values.ravel()[0])
    assert r.G == pytest.approx(liq.amount * float(eq.GM.squeeze()) + mul.amount * g_mul, abs=0.01)
