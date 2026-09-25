"""Chemical groups in the MQMQA excess vs pycalphad, and the cases still refused.

The group-dependent interpolation (Pelton et al. 2001; Poschmann et al. 2021) puts a
third species on the side of the mixing species it shares a chemical group with, in
the Xi or Chi variables and in the additional-constituent factor, whose exponent r may
exceed 1. pycalphad's MQMQA-tern-tests.dat carries one ternary G term under four group
assignments; synthetic salts written here as uTDB (and converted to .dat so pycalphad
can read them) cover the Q and G codes, r = 1 to 3, every assignment of three species
to groups, and groups on the anion sublattice.

Where the other sublattice holds more than one species the published equations admit
more than one reading and the engine refuses the term (NaN, with a message naming the
phase); so it does for r > 1 there and for ChemSage chemical-group override strings.
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
import mqmqa  # noqa: E402
from mqmqa import Database, UnsupportedModelError  # noqa: E402
from mqmqa import equilibrium as eq  # noqa: E402
from mqmqa._abi import _ffi, _lib, c_equilibrate  # noqa: E402

pytest.importorskip("pycalphad")
TERN = U.pycalphad_fixtures(["MQMQA-tern-tests.dat"])
SHISHIN = U.pycalphad_fixtures(["Shishin_Fe-Sb-O-S_slag.dat"])
ASSIGNMENTS = ["111", "121", "122", "123", "211", "112"]


def _quads(db, p):
    return list(zip(*mqmqa.enumerate_quadruplets(len(db.cations(p)), len(db.anions(p)))))


def _excess(db, p, T, Xkey, grouped=True):
    cats, ans = db.cations(p), db.anions(p)
    nc, na = len(cats), len(ans)
    qc, qa = [c["charge"] for c in cats], [a["charge"] for a in ans]
    mz = db.mqmz(p)

    def Z(is_cat, sp, A, B, X, Y):
        return mqmqa.coordination(is_cat, sp, A, B, X, Y, nc, na, qc, qa,
                                  mz["A"], mz["B"], mz["X"], mz["Y"], mz["Z"])
    quads = _quads(db, p)
    ca, cb, ax, ay = (list(v) for v in zip(*quads))
    mx = db.mqmx(p, T)
    return mqmqa.excess_energy(
        nc, na, ca, cb, ax, ay, [Xkey[q] for q in quads],
        [Z(1, A, A, B, X, Y) for A, B, X, Y in quads], [Z(1, B, A, B, X, Y) for A, B, X, Y in quads],
        [Z(0, X, A, B, X, Y) for A, B, X, Y in quads], [Z(0, Y, A, B, X, Y) for A, B, X, Y in quads],
        mx["mix"], mx["code"], mx["A"], mx["B"], mx["X"], mx["Y"], mx["p"], mx["q"], mx["L"],
        mx["r"], mx["addcat"],
        [c["group"] for c in cats] if grouped else None,
        [a["group"] for a in ans] if grouped else None)


def _excess_pycalphad(path, name, db, p, T, Xkey):
    from pycalphad import Database as PDatabase, variables as v
    from pycalphad.models.model_mqmqa import ModelMQMQA
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pdb = PDatabase(str(path))
        mod = ModelMQMQA(pdb, [e for e, _ in db.elements] + ["VA"], name)

    def ec(sp):
        return (next(iter(sp.constituents)) if sp.constituents else sp.name), abs(sp.charge)
    rc = [(re.match(r"[A-Z]+", c["name"]).group(0), c["charge"]) for c in db.cations(p)]
    ra = [(re.match(r"[A-Z]+", a["name"]).group(0), a["charge"]) for a in db.anions(p)]
    ci = {c: rc.index(ec(c)) for c in mod.cations}
    ai = {a: ra.index(ec(a)) for a in mod.anions}
    subs = {v.T: T}
    for A, B, X, Y in mod._quadruplets:
        a, b, x, y = ci[A], ci[B], ai[X], ai[Y]
        subs[mod._X_ijkl(A, B, X, Y)] = Xkey[(min(a, b), max(a, b), min(x, y), max(x, y))]
    return float(mod.excess_mixing_energy(pdb).subs(subs))


def _compare(path, name, n_x=3):
    """Worst relative deviation of the engine's excess from pycalphad's."""
    db = Database.read(str(path))
    p = db.phase_index(name)
    assert db.excess_unsupported(p) is None
    rng = np.random.default_rng(7)
    quads = _quads(db, p)
    worst, values = 0.0, []
    for T in (1273.37, 1873.37):
        for _ in range(n_x):
            w = rng.uniform(0.2, 1.0, len(quads))
            Xkey = dict(zip(quads, w / w.sum()))
            ours = _excess(db, p, T, Xkey)
            theirs = _excess_pycalphad(path, name, db, p, T, Xkey)
            d = U.rel(ours, theirs)
            assert d < U.ORACLE_TOL, (name, T, ours, theirs)
            worst = max(worst, d)
            values.append(ours)
    return worst, values


# ---- pycalphad's own test database ----

@pytest.mark.skipif(not TERN, reason="pycalphad test databases not installed")
@pytest.mark.parametrize("name", ["TERN_XS_111", "TERN_XS_121", "TERN_XS_122", "TERN_XS_123",
                                  "XS_DIFF_CG", "XS_SAME_CG"])
def test_tern_tests_match_pycalphad(name):
    worst, _ = _compare(TERN[0], name)
    print(f"\n{name}: worst relative deviation {worst:.3g}")


@pytest.mark.skipif(not TERN, reason="pycalphad test databases not installed")
def test_groups_change_the_number():
    """The four assignments of one term differ where the groups put Ni on a side, so
    the agreement above is the groups being honored, not ignored."""
    vals = {n: _compare(TERN[0], n)[1] for n in ("TERN_XS_111", "TERN_XS_121",
                                                   "TERN_XS_122", "TERN_XS_123")}
    assert vals["TERN_XS_111"] == vals["TERN_XS_123"]       # Ni in gamma both times
    for n in ("TERN_XS_121", "TERN_XS_122"):
        assert all(abs(a - b) > 1e-3 * abs(b) for a, b in zip(vals[n], vals["TERN_XS_111"]))


@pytest.mark.skipif(not TERN, reason="pycalphad test databases not installed")
def test_ungrouped_call_is_the_single_group_expression():
    """Omitting the groups is an explicit single-group request."""
    db = Database.read(TERN[0])
    p121, p111 = db.phase_index("TERN_XS_121"), db.phase_index("TERN_XS_111")
    Xkey = {q: 1.0 / 6 for q in _quads(db, p121)}
    assert _excess(db, p121, 1500.0, Xkey, grouped=False) == _excess(db, p111, 1500.0, Xkey)
    assert _excess(db, p121, 1500.0, Xkey) != _excess(db, p111, 1500.0, Xkey)


@pytest.mark.skipif(not TERN, reason="pycalphad test databases not installed")
def test_grouped_equilibrium_runs_in_c():
    db = Database.read(TERN[0])
    p = db.phase_index("TERN_XS_121")
    inp = eq.build_inputs(db, p, 1500.0)
    res = c_equilibrate(inp, U._neutral_composition(db, p, np.full(3, 1.0 / 3)))
    assert math.isfinite(res["GM"]) and res["comp_error"] < 1e-9


# ---- synthetic salts: every group assignment, both codes, r up to 3 ----

EL = {"NA": 22.99, "K": 39.098, "MG": 24.305, "CL": 35.453, "F": 18.998, "BR": 79.904}
CH = {"NA": 1, "K": 1, "MG": 2, "CL": -1, "F": -1, "BR": -1}
G0 = {"NA": -400000, "K": -420000, "MG": -620000}
AN = {"CL": 0, "F": -150000, "BR": 60000}


def _sp(e):
    return f"{e}{'+' if CH[e] > 0 else '-'}{abs(CH[e])}"


def _utdb(cats, ans, cgrp, agrp, terms):
    """A uTDB SUBQ salt. terms: (code, A, B, X, Y, p, q, r, additional cation, L)."""
    s = [" ELEMENT /-   ELECTRON_GAS 0.0 0.0 0.0 !", " ELEMENT VA   VACUUM 0.0 0.0 0.0 !"]
    s += [f" ELEMENT {e}   X  {EL[e]}  0.0  0.0 !" for e in sorted(set(cats) | set(ans))]
    s += [f" SPECIES {_sp(e)}  {e}1/{_sp(e)[len(e):]} !" for e in sorted(set(cats) | set(ans))]
    s += [" TYPE_DEFINITION % SEQ * !", " PHASE L:Q %  2  1.0  1.0 !",
          f" CONSTITUENT L:Q : {','.join(map(_sp, cats))} : {','.join(map(_sp, ans))} : !"]
    for c in cats:
        for a in ans:
            s.append(f" PARAMETER MQG(L,{_sp(c)}:{_sp(a)};0) 298.15 "
                     f"{G0[c] + AN[a]}+{20 + CH[c]}*T-5*T*LN(T); 6000 N !")
            s.append(f" PARAMETER MQZETA(L,{_sp(c)}:{_sp(a)}) 298.15 1.3774438; 6000 N !")
            s.append(f" PARAMETER MQSTOI(L,{_sp(c)}:{_sp(a)}) 298.15 1 {CH[c]} 0 0 0; 6000 N !")
            za = 6.0 if CH[c] == 1 else 3.0
            s.append(f" PARAMETER MQZ(L,{_sp(c)},{_sp(c)}:{_sp(a)},{_sp(a)}) 298.15 "
                     f"6 6 {za} {za}; 6000 N !")
    for sp, g in list(zip(cats, cgrp)) + list(zip(ans, agrp)):
        s.append(f" PARAMETER MQGRP(L,{_sp(sp)}) 298.15 {g}; 6000 N !")
    for code, A, B, X, Y, p, q, r, T, L in terms:
        head = f"(L,{_sp(A)},{_sp(B)}:{_sp(X)},{_sp(Y)};{p},{q}"
        s.append(f" PARAMETER MQXT{code}{head},{r}:{_sp(T)}) 298.15 {L}; 6000 N !" if T else
                 f" PARAMETER MQX{code}{head}) 298.15 {L}; 6000 N !")
    return "\n".join(s) + "\n"


def _as_dat(tmp_path, tag, *args):
    """The salt read from uTDB and written as .dat, the form pycalphad reads."""
    src = tmp_path / f"{tag}.utdb"
    src.write_text(_utdb(*args))
    out = tmp_path / f"{tag}.dat"
    Database.read(str(src)).write_dat(str(out))
    return out


CATION_TERMS = [
    ("Q", "NA", "K", "CL", "CL", 1, 1, 1, "MG", -9000),
    ("G", "NA", "MG", "CL", "CL", 2, 0, 2, "K", -3000),
    ("Q", "K", "MG", "CL", "CL", 0, 1, 0, None, -15000),
    ("Q", "NA", "MG", "CL", "CL", 1, 1, 3, "K", -7000),
    ("G", "K", "MG", "CL", "CL", 1, 0, 1, "NA", -8000),
    ("G", "NA", "K", "CL", "CL", 1, 1, 3, "MG", 2000),
]
ANION_TERMS = [
    ("G", "K", "K", "F", "CL", 1, 0, 0, None, -8000),
    ("Q", "K", "K", "CL", "BR", 0, 1, 0, None, -5000),
    ("Q", "K", "K", "F", "BR", 1, 1, 0, None, -3000),
    ("G", "K", "K", "F", "BR", 2, 1, 0, None, -2000),
]


@pytest.mark.parametrize("groups", ASSIGNMENTS)
def test_cation_groups_match_pycalphad(tmp_path, groups):
    path = _as_dat(tmp_path, "cat", ["NA", "K", "MG"], ["CL"], list(groups), [1], CATION_TERMS)
    worst, _ = _compare(path, "L")
    print(f"\ncation groups {groups}: worst relative deviation {worst:.3g}")


@pytest.mark.parametrize("groups", ASSIGNMENTS)
def test_anion_groups_match_pycalphad(tmp_path, groups):
    path = _as_dat(tmp_path, "an", ["K"], ["F", "CL", "BR"], [1], list(groups), ANION_TERMS)
    worst, _ = _compare(path, "L")
    print(f"\nanion groups {groups}: worst relative deviation {worst:.3g}")


# ---- still refused, loudly ----

def _refused(db, name, pattern, raw=True):
    """Refused through every database-level path; raw=False where the refusal hangs on
    data the array-level routine is not given (override strings)."""
    p = db.phase_index(name)
    why = db.excess_unsupported(p)
    assert why and name in why and re.search(pattern, why), why
    if raw:
        Xkey = {q: 1.0 / len(_quads(db, p)) for q in _quads(db, p)}
        assert math.isnan(_excess(db, p, 1500.0, Xkey))
    with pytest.raises(UnsupportedModelError, match=name):
        eq.build_inputs(db, p, 1500.0)
    target = _ffi.new("double[]", [1.0] * len(db.elements))
    X = _ffi.new("double[]", 256)
    assert math.isnan(_lib.mqmqa_equilibrate_db(db._db, p, 1500.0, target, X, _ffi.NULL))
    assert why == _ffi.string(_lib.mqmqa_db_error()).decode()


def test_groups_with_several_other_ions_refused(tmp_path):
    src = tmp_path / "recip.utdb"
    src.write_text(_utdb(["NA", "K"], ["F", "CL", "BR"], [1, 1], [1, 2, 1], ANION_TERMS[:2]))
    _refused(Database.read(str(src)), "L",
             r"more than one cation; mixed chemical groups are not supported")


@pytest.mark.skipif(not SHISHIN, reason="pycalphad test databases not installed")
def test_multi_anion_groups_and_r_refused():
    """Shishin's Fe-Sb-O-S slag mixes O and S: groups on its cations, or r = 2 in a new
    ternary term, are refused."""
    text = open(SHISHIN[0]).read()
    grouped = text.replace("  2.00000      3.00000      3.00000\n   1   1   1\n",
                           "  2.00000      3.00000      3.00000\n   1   2   1\n")
    assert grouped != text
    _refused(Database.read_string(grouped), "SLAG-LIQ",
             r"more than one anion; mixed chemical groups are not supported")
    term = ("   3\n Q   1   2   4   4   1   1   2   0\n"
            + " 0.00000000       0.00 0.00000000       0.00 0.00000000       0.00\n" * 2
            + "   3   0 -5000.0     0.00000000     0.00000000     0.00000000\n"
            + " 0.00000000     0.00000000\n")
    tern = text.replace("\n   0\n Sb2O3", "\n" + term.rstrip("\n") + "\n   0\n Sb2O3", 1)
    assert tern != text
    _refused(Database.read_string(tern), "SLAG-LIQ", r"exponent r other than 1")


@pytest.mark.skipif(not TERN, reason="pycalphad test databases not installed")
def test_group_override_strings_refused():
    """ChemSage chemical-group override strings (a negative mixing type) change the
    interpolation; the reader cannot model them, so the phase is refused."""
    text = open(TERN[0]).read()
    head, tail = text.split(" TERN_XS_111", 1)
    body, rest = tail.split(" TERN_XS_121", 1)
    marker = "     0.00000000     0.00000000\n   0\n"
    assert body.endswith(marker)
    override = "     0.00000000     0.00000000\n  -1\n 1 2 3 4 5 6 7 8 9 10\n"
    patched = head + " TERN_XS_111" + body[:-len(marker)] + override + " TERN_XS_121" + rest
    _refused(Database.read_string(patched), "TERN_XS_111", r"override strings", raw=False)
