"""Database writers, TDB and uTDB: read -> write -> read back reproduces the model.

Every shipped database the target can represent is written, read back with the same
engine, and compared phase by phase (structure, endmember and solution Gibbs energies
over 300-3000 K plus two points above 6000 K, MQMQA pair/coordination/excess data and
single-phase equilibria) at 1e-14 relative (roundtrip_util explains the bound). The
written files are then read by pycalphad, an independent parser, and compared with
Hephaestus's energies for the ORIGINAL file. A binary phase diagram per format must pick
the same stable phases. Unrepresentable conversions must raise and write nothing.
"""
import os
import sys
import warnings

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))
import roundtrip_util as U  # noqa: E402
from mqmqa import Database, ConversionError  # noqa: E402
from mqmqa import equilibrium as eqm  # noqa: E402
from mqmqa.equilibrium import build_inputs  # noqa: E402

SHIPPED = [f for f in U.shipped_databases()
           if not f.endswith(".xtdb") and not U.is_nasa_thermo(f)]
IDS = [os.path.relpath(f, U.ROOT).replace("\\", "/") for f in SHIPPED]
EXTRA = U.pycalphad_fixtures(["Al-Mg_Zhong.tdb", "alzn_mey.tdb", "crfe_bcc_magnetic.tdb",
                              "pbsn.tdb", "Shishin_Fe-Sb-O-S_slag.dat"])
EXTRA_IDS = ["pycalphad/" + os.path.basename(f) for f in EXTRA]


def _has_mqmqa(db):
    return any(db.phase_kind(p) == 0 for p in range(len(db.phase_names)))


@pytest.mark.parametrize("path", SHIPPED + EXTRA, ids=IDS + EXTRA_IDS)
def test_tdb_roundtrip(path, tmp_path):
    db = Database.read(path)
    if _has_mqmqa(db):
        target = tmp_path / "x.tdb"
        with pytest.raises(ConversionError, match=r"MQMQA.*plain TDB.*\.utdb or \.dat"):
            db.write_tdb(str(target))
        assert not target.exists()
        return
    back, _ = U.roundtrip(db, "write_tdb", tmp_path, ".tdb")
    worst = U.compare(db, back)
    print(f"\nTDB  {os.path.basename(path)}: worst relative deviation {worst:.3g}")


@pytest.mark.parametrize("path", SHIPPED + EXTRA, ids=IDS + EXTRA_IDS)
def test_utdb_roundtrip(path, tmp_path):
    db = Database.read(path)
    back, _ = U.roundtrip(db, "write_utdb", tmp_path, ".utdb")
    worst = U.compare(db, back)
    print(f"\nuTDB {os.path.basename(path)}: worst relative deviation {worst:.3g}")


@pytest.mark.parametrize("path", SHIPPED, ids=IDS)
def test_rewrite_is_stable(path):
    """Writing the read-back database gives the same file: nothing drifts on repeat."""
    db = Database.read(path)
    first = db.write_utdb(source_name="s")
    again = Database.read_string(first).write_utdb(source_name="s")
    body = lambda t: [ln for ln in t.splitlines() if not ln.lstrip().startswith("$")]
    assert body(first) == body(again)


def _strip_mqmqa(text):
    """The CEF and compound part of a uTDB file, for readers without the MQ* statements."""
    keep = []
    for st in text.split("!"):
        code = " ".join(ln for ln in st.splitlines() if not ln.strip().startswith("$"))
        if ":Q" in code or "PARAMETER MQ" in code:
            continue
        keep.append(st)
    return "!".join(keep)


@pytest.mark.parametrize("path", SHIPPED + EXTRA, ids=IDS + EXTRA_IDS)
def test_written_tdb_matches_pycalphad(path):
    pytest.importorskip("pycalphad")
    from pycalphad import Database as PDatabase, calculate
    db = Database.read(path)
    text = _strip_mqmqa(db.write_utdb())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pdb = PDatabase.from_string(text, fmt="tdb")
    comps = [e for e, _ in db.elements] + ["VA"]
    rng = np.random.default_rng(5)
    worst, n = 0.0, 0
    for p, name in enumerate(db.phase_names):
        if db.phase_kind(p) != 1:
            continue
        subls = db.cef_sublattices(p)
        for T in (300.37, 1000.37, 2200.37):
            Ys = [U._random_Y(subls, rng) for _ in range(4)]
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = calculate(pdb, comps, name, T=T, P=101325, N=1, points=np.array(Ys))
            for Y, g in zip(Ys, np.atleast_1d(res.GM.values.squeeze())):
                d = U.rel(db.cef_gibbs(p, Y, T, per_mole_atoms=True), float(g))
                assert d < U.ORACLE_TOL, (name, T, Y)
                worst, n = max(worst, d), n + 1
    for i, name in enumerate(db.stoich):
        atoms = sum(db.stoich_elements(i))
        for T in (300.37, 1500.37):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = calculate(pdb, comps, name, T=T, P=101325, N=1)
            d = U.rel(db.stoich_gibbs(i, T), float(res.GM.values.squeeze()) * atoms)
            assert d < U.ORACLE_TOL, (name, T)
            worst, n = max(worst, d), n + 1
    print(f"\npycalphad on written TDB {os.path.basename(path)}: {n} points, worst {worst:.3g}")


@pytest.mark.parametrize("fname,A,B", [("FeC.tdb", "FE", "C"), ("AlZn.tdb", "AL", "ZN")])
def test_binary_diagram_survives_tdb(fname, A, B, tmp_path):
    db = Database.read(os.path.join(U.ROOT, "web", fname))
    back, _ = U.roundtrip(db, "write_tdb", tmp_path, ".tdb")
    stable = set()
    for T in np.linspace(500.37, 1900.37, 15):
        h1 = U.lower_hull(U.cef_binary_points(db, A, B, T))
        h2 = U.lower_hull(U.cef_binary_points(back, A, B, T))
        U.compare_hulls(h1, h2)
        stable |= {ph for _, _, ph in h1}
    assert len(stable) >= 3        # the section really crosses several phase fields


def test_binary_diagram_survives_utdb(tmp_path):
    """LiCl-KCl liquid + two salts along the join, through the MQ* statements."""
    db = Database.read(os.path.join(U.ROOT, "web", "LiCl-KCl.dat"))
    back, _ = U.roundtrip(db, "write_utdb", tmp_path, ".utdb")
    solids = lambda d, T: [(0.0 if n.startswith("LICL") else 1.0, d.stoich_gibbs(i, T), n)
                           for i, n in enumerate(d.stoich)]
    seen = set()
    for T in (600.37, 700.37, 900.37, 1100.37):
        pl, pb = db.phase_index("LICL-KCL-LIQUID"), back.phase_index("LICL-KCL-LIQUID")
        il, ib = build_inputs(db, pl, T), build_inputs(back, pb, T)
        for xi in (0.1, 0.3, 0.42, 0.6, 0.9):
            r1 = eqm.multiphase_binary(il, {"LI": 1, "CL": 1}, {"K": 1, "CL": 1},
                                       solids(db, T), xi, ngrid=120)
            r2 = eqm.multiphase_binary(ib, {"LI": 1, "CL": 1}, {"K": 1, "CL": 1},
                                       solids(back, T), xi, ngrid=120)
            assert r1["phases"] == r2["phases"], (T, xi)
            assert r1["endpoints"] == r2["endpoints"], (T, xi)
            assert U.rel(r1["GM"], r2["GM"]) < U.REL_TOL
            seen |= set(r1["phases"])
    assert {"LIQUID", "LICL_SOLID", "KCL_SOLID"} <= seen


# ---- loud failures: a clear error naming the model and a format that holds it -------

def _refuses(db, method, tmp_path, pattern):
    target = tmp_path / "out.file"
    with pytest.raises(ConversionError, match=pattern):
        getattr(db, method)(str(target))
    assert not target.exists()


def test_subg_liquid_refused_by_utdb(tmp_path):
    found = U.pycalphad_fixtures(["MQMQA-tern-tests.dat"])
    if not found:
        pytest.skip("pycalphad SUBG test database not present")
    db = Database.read(found[0])
    _refuses(db, "write_utdb", tmp_path, r"SUBG.*only \.dat")
    _refuses(db, "write_tdb", tmp_path, r"MQMQA")


def test_chemsage_magnetic_source_refused(tmp_path):
    """KF-NiF2 carries magnetic records on its Ni solids, which the reader skips."""
    found = U.pycalphad_fixtures(["KF-NIF2_switched.dat"])
    if not found:
        pytest.skip("pycalphad test database not present")
    _refuses(Database.read(found[0]), "write_utdb", tmp_path, r"magnetic record.*NI_SOLID")


def test_unread_parameter_type_refused(tmp_path):
    """The reader skips a volume parameter; converting would drop it, so writers refuse."""
    src = open(os.path.join(U.ROOT, "web", "AlZn.tdb")).read()
    src += "\n PARAMETER V0(LIQUID,AL;0) 298.15 1.1E-5; 6000 N !\n"
    db = Database.read_string(src)
    for m in ("write_tdb", "write_utdb"):
        _refuses(db, m, tmp_path, r"PARAMETER type V0.*silently drop")


def test_chemsage_magnetic_record_refused(tmp_path):
    """A ChemSage magnetic endmember (option 13-24) is read but not modeled."""
    lines = open(os.path.join(U.ROOT, "data", "olivine", "Olivine-CEF.dat")).read().splitlines()
    for i, ln in enumerate(lines):
        if ln.strip() == "FAYALITE":
            tok = lines[i + 1].split()
            lines[i + 1] = "   13   " + "   ".join(tok[1:])        # option 1 -> 13 (magnetic)
            lines.insert(i + 3, "   0.0   0.0")                   # Tc, moment after interval
            break
    db = Database.read_string("\n".join(lines) + "\n")
    _refuses(db, "write_tdb", tmp_path, r"magnetic record.*FAYALITE")


def test_ln_t_term_refused_by_tdb(tmp_path):
    """ChemSage exponent 99 is c*ln(T); the TDB reader has no standalone LN(T)."""
    text = open(os.path.join(U.ROOT, "data", "olivine", "Olivine-CEF.dat")).read()
    text = text.replace("   1   3.3744000000E+03   5.0000000000E-01",
                        "   1   3.3744000000E+03   99")
    db = Database.read_string(text)
    _refuses(db, "write_tdb", tmp_path, r"ln\(T\).*\.dat or \.xtdb")


def test_provenance_header():
    db = Database.read(os.path.join(U.ROOT, "web", "FeO-MgO-SiO2-combined.dat"))
    text = db.write_utdb()
    head = [ln for ln in text.splitlines() if ln.startswith("$")]
    import mqmqa._abi as abi
    version = abi._ffi.string(abi._lib.mqmqa_version()).decode()
    assert head[0] == (f"$ Converted to uTDB by Hephaestus {version} "
                       "from FeO-MgO-SiO2-combined.dat.")
    assert head[1] == ("$ Converting a database does not change its license; "
                       "the license of the source data applies.")
    assert any("Source header" in ln for ln in head)
    assert text.isascii()


def test_comparison_catches_a_planted_change(tmp_path):
    """The gate itself: one endmember constant moved in its 14th significant digit."""
    src = os.path.join(U.ROOT, "data", "olivine", "Olivine-CEF.dat")
    text = Database.read(src).write_tdb()
    assert text.count("-1543550.9474+") == 1
    planted = Database.read_string(text.replace("-1543550.9474+", "-1543550.9474001+"))
    with pytest.raises(AssertionError):
        U.compare(Database.read(src), planted)
