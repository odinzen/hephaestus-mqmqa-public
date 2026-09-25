"""Database writers, XTDB: both directions between the XTDB engine and the database.

XTDB -> XTDB keeps every expression as read, so the third-generation models (Einstein
LNTH, the two-state liquid) survive and the energies agree bit for bit. XTDB -> TDB and
-> .dat carry a classic (second-generation) XTDB file across; third-generation models
have no form there and must be refused. .dat/.tdb/.utdb -> XTDB is compared phase by
phase against the source.

The two engines use different gas constants in the ideal mixing term: the database
engine R = 8.3145 (src/cef.c) and the XTDB engine R = 8.31451 (src/xtdb.c), each the
value its test suite validates against. A written file cannot reconcile them, so for
mixed compositions the comparison adds that known difference analytically,
(8.31451 - 8.3145) T sum_s a_s sum_i y ln y per mole of atoms, and then requires the
same 1e-14 relative agreement as the other writers. Endmembers carry no mixing term and
are compared directly.

The independent reader is data/xtdb-alc/xtdb_ref.py, the Python XTDB evaluator the C
engine was specified from (ElementTree XML parsing, Python arithmetic).
"""
import math
import os
import sys
import warnings

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))
import roundtrip_util as U  # noqa: E402
from mqmqa import Database, XTDB, ConversionError, R  # noqa: E402

sys.path.insert(0, os.path.join(U.ROOT, "data", "xtdb-alc"))
import xtdb_ref  # noqa: E402

R_XTDB = 8.31451
T_POINTS = [float(t) for t in np.linspace(300.37, 3000.37, 13)] + [6500.37]
XTDB_FILES = [f for f in U.shipped_databases() if f.endswith(".xtdb")]
XTDB_IDS = [os.path.relpath(f, U.ROOT).replace("\\", "/") for f in XTDB_FILES]
DB_FILES = [f for f in U.shipped_databases() if not f.endswith(".xtdb")
            and not U.is_nasa_thermo(f)]
DB_IDS = [os.path.relpath(f, U.ROOT).replace("\\", "/") for f in DB_FILES]
EXTRA = U.pycalphad_fixtures(["Al-Mg_Zhong.tdb", "alzn_mey.tdb", "pbsn.tdb"])
EXTRA_IDS = ["pycalphad/" + os.path.basename(f) for f in EXTRA]


def _endmembers(tp_phases, name):
    con = tp_phases[name]["con"]
    import itertools
    return [":".join(c) for c in itertools.product(*con)]


def _save(text, tmp_path, name):
    path = os.path.join(str(tmp_path), name)
    with open(path, "w", encoding="ascii", newline="\n") as f:
        f.write(text)
    return path


def _compare_xtdb(a, b, ref_path, x_grid=np.linspace(0.02, 0.98, 25)):
    """Two XTDB readings of the same model: every endmember and every phase's G(x)."""
    tp, params, phases = xtdb_ref.parse(ref_path)
    assert a.elements == b.elements and a.phase_names == b.phase_names
    worst = 0.0
    elements = a.elements
    for p, name in enumerate(a.phase_names):
        for cons in _endmembers(phases, name):
            if ("G", name, cons, "0") not in params:
                continue
            for T in T_POINTS:
                ga, gb = a.endmember_gibbs(name, cons, T), b.endmember_gibbs(name, cons, T)
                d = U.rel(ga, gb)
                assert d < U.REL_TOL, (name, cons, T, ga, gb)
                worst = max(worst, d)
        for T in T_POINTS[:-1]:
            for B in elements:
                for xB in x_grid:
                    ga, fa = a.phase_gibbs(p, B, xB, T)
                    gb, fb = b.phase_gibbs(p, B, xB, T)
                    assert fa == fb
                    if math.isnan(ga):
                        assert math.isnan(gb)
                        continue
                    d = U.rel(ga, gb)
                    assert d < U.REL_TOL, (name, B, xB, T, ga, gb)
                    worst = max(worst, d)
    return worst


@pytest.mark.parametrize("path", XTDB_FILES, ids=XTDB_IDS)
def test_xtdb_roundtrip(path, tmp_path):
    x = XTDB.read(path)
    out = _save(x.write_xtdb(), tmp_path, "converted.xtdb")
    back = XTDB.read(out)
    worst = _compare_xtdb(x, back, out)
    print(f"\nXTDB {os.path.basename(path)}: worst relative deviation {worst:.3g}")


@pytest.mark.parametrize("path", XTDB_FILES, ids=XTDB_IDS)
def test_written_xtdb_matches_reference_evaluator(path, tmp_path):
    """The Python reference evaluator on the WRITTEN file vs the C engine on the source."""
    x = XTDB.read(path)
    out = _save(x.write_xtdb(), tmp_path, "converted.xtdb")
    tp, params, phases = xtdb_ref.parse(out)
    worst, n = 0.0, 0
    for p, name in enumerate(x.phase_names):
        for cons in _endmembers(phases, name):
            if ("G", name, cons, "0") not in params:
                continue
            for T in T_POINTS[:-1]:
                d = U.rel(x.endmember_gibbs(name, cons, T),
                          xtdb_ref.endmember_G(tp, params, phases, name, cons, T))
                assert d < U.REL_TOL, (name, cons, T)
                worst, n = max(worst, d), n + 1
        for T in (500.37, 1500.37, 2500.37):
            for xB in (0.1, 0.35, 0.6, 0.9):
                g, _ = x.phase_gibbs(p, x.elements[-1], xB, T)
                gr, _ = xtdb_ref.phase_G(tp, params, phases, name, x.elements[-1], xB, T)
                if math.isnan(g):
                    assert gr is None
                    continue
                d = U.rel(g, gr)
                assert d < U.REL_TOL, (name, xB, T)
                worst, n = max(worst, d), n + 1
    print(f"\nreference evaluator on written {os.path.basename(path)}: {n} points, worst {worst:.3g}")


def _hull(x, B, T):
    pts = []
    for p, name in enumerate(x.phase_names):
        g, fixed = x.phase_gibbs(p, B, 1e-6, T)
        if fixed is not None:
            g, _ = x.phase_gibbs(p, B, fixed, T)
            if not math.isnan(g):
                pts.append((fixed, g, name))
            continue
        for xB in np.linspace(1e-6, 1 - 1e-6, 201):
            g, _ = x.phase_gibbs(p, B, xB, T)
            if not math.isnan(g):
                pts.append((float(xB), g, name))
    return U.lower_hull(pts)


@pytest.mark.parametrize("fname,B,Ts", [("PbSn.xtdb", "SN", (400.37, 450.37, 470.37, 520.37)),
                                        ("AlC.xtdb", "C", (800.37, 1500.37, 2300.37, 2500.37))])
def test_binary_diagram_survives_xtdb(fname, B, Ts, tmp_path):
    x = XTDB.read(os.path.join(U.ROOT, "web", fname))
    back = XTDB.read(_save(x.write_xtdb(), tmp_path, "converted.xtdb"))
    stable = set()
    for T in Ts:
        h1, h2 = _hull(x, B, T), _hull(back, B, T)
        U.compare_hulls(h1, h2)
        stable |= {ph for _, _, ph in h1}
    assert len(stable) >= 3


# ---- XTDB -> TDB / uTDB / .dat -----------------------------------------------------------

def _db_endmember(db, name, cons, T):
    """Per-formula G of an endmember of a database phase, CEF or stoichiometric."""
    if name in db.phase_names:
        p = db.phase_index(name)
        Y = []
        for s, c in zip(db.cef_sublattices(p), cons.split(":")):
            Y += [1.0 if k == c else 0.0 for k in s["constituents"]]
        return db.cef_gibbs(p, Y, T, per_mole_atoms=False)
    return db.stoich_gibbs(db.stoich.index(name), T)


def _mixing_shift(subls, Y, T):
    """XTDB-engine minus database-engine G per mole of atoms from the two gas constants."""
    s, atoms, off = 0.0, 0.0, 0
    for sl in subls:
        for c in sl["constituents"]:
            y = Y[off]
            if y > 0:
                s += sl["site_ratio"] * y * math.log(y)
            atoms += sl["site_ratio"] * y * (0.0 if c == "VA" else 1.0)
            off += 1
    return (R_XTDB - R()) * T * s / atoms


def _y_for_x(subls, B, xB):
    """Site fractions of a phase with one binary mixing sublattice at mole fraction xB."""
    m = [k for k, s in enumerate(subls) if len(s["constituents"]) > 1][0]
    first = subls[m]["constituents"][0]

    def xb(y):
        nB = tot = 0.0
        for k, s in enumerate(subls):
            ys = [y, 1 - y] if k == m else [1.0]
            for c, f in zip(s["constituents"], ys):
                a = 0.0 if c == "VA" else 1.0
                tot += s["site_ratio"] * f * a
                nB += s["site_ratio"] * f * a * (c == B)
        return nB / tot
    lo, hi = 1e-9, 1 - 1e-9
    flo = xb(lo) - xB
    if (xb(hi) - xB) * flo > 0:
        return None
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if (xb(mid) - xB) * flo <= 0:
            hi = mid
        else:
            lo = mid
    y = 0.5 * (lo + hi)
    Y = []
    for k, s in enumerate(subls):
        Y += [y, 1 - y] if k == m else [1.0]
    return Y


def _compare_db_xtdb(db, x):
    """A database and an XTDB reading of the same model (either direction)."""
    worst = 0.0
    names = db.phase_names + db.stoich
    assert sorted(names) == sorted(x.phase_names)
    for p, name in enumerate(x.phase_names):
        if name in db.phase_names:
            dp = db.phase_index(name)
            subls = db.cef_sublattices(dp)
            import itertools
            for combo in itertools.product(*[s["constituents"] for s in subls]):
                cons = ":".join(combo)
                for T in T_POINTS:
                    a, b = _db_endmember(db, name, cons, T), x.endmember_gibbs(name, cons, T)
                    d = U.rel(a, b)
                    assert d < U.REL_TOL, (name, cons, T, a, b)
                    worst = max(worst, d)
            mixing = [s for s in subls if len(s["constituents"]) > 1]
            if not mixing:
                continue
            B = mixing[0]["constituents"][0]
            for T in T_POINTS[:-1]:
                for xB in np.linspace(0.01, 0.99, 21):
                    Y = _y_for_x(subls, B, xB)
                    g, _ = x.phase_gibbs(p, B, xB, T)
                    if Y is None:
                        assert math.isnan(g)
                        continue
                    a = db.cef_gibbs(dp, Y, T, per_mole_atoms=True) + _mixing_shift(subls, Y, T)
                    d = U.rel(a, g)
                    assert d < U.REL_TOL, (name, xB, T, a, g)
                    worst = max(worst, d)
        else:
            i = db.stoich.index(name)
            atoms = sum(db.stoich_elements(i))
            for T in T_POINTS:
                g, fixed = x.phase_gibbs(p, x.elements[0], 0.5, T)
                d = U.rel(db.stoich_gibbs(i, T) / atoms, g)
                assert d < U.REL_TOL, (name, T)
                worst = max(worst, d)
    return worst


@pytest.mark.parametrize("path", DB_FILES + EXTRA, ids=DB_IDS + EXTRA_IDS)
def test_db_to_xtdb(path, tmp_path):
    db = Database.read(path)
    kinds = {db.phase_kind(p) for p in range(len(db.phase_names))}
    try:
        text = db.write_xtdb()
    except ConversionError as e:
        # only the models the XTDB engine does not evaluate may be refused
        msg = str(e)
        assert ((0 in kinds and "MQMQA" in msg) or "Inden magnetic" in msg
                or "one binary mixing sublattice" in msg), msg
        return
    out = _save(text, tmp_path, "converted.xtdb")
    x = XTDB.read(out)
    worst = _compare_db_xtdb(db, x)
    # independent reader on the written file, endmember by endmember
    tp, params, phases = xtdb_ref.parse(out)
    for name in x.phase_names:
        for cons in _endmembers(phases, name):
            for T in T_POINTS[:-1]:
                d = U.rel(x.endmember_gibbs(name, cons, T),
                          xtdb_ref.endmember_G(tp, params, phases, name, cons, T))
                assert d < U.REL_TOL
    print(f"\n-> XTDB {os.path.basename(path)}: worst relative deviation {worst:.3g}")


@pytest.mark.parametrize("method,suffix", [("write_tdb", ".tdb"), ("write_utdb", ".utdb"),
                                           ("write_dat", ".dat")])
def test_classic_xtdb_to_tdb_and_dat(method, suffix, tmp_path):
    """Pb-Sn is a classic assessment in XTDB, so .tdb and .dat can hold it."""
    x = XTDB.read(os.path.join(U.ROOT, "web", "PbSn.xtdb"))
    out = os.path.join(str(tmp_path), "converted" + suffix)
    getattr(x, method)(out)
    db = Database.read(out)
    worst = _compare_db_xtdb(db, x)
    print(f"\nPbSn.xtdb -> {suffix}: worst relative deviation {worst:.3g}")


def test_classic_xtdb_to_tdb_matches_pycalphad(tmp_path):
    pytest.importorskip("pycalphad")
    from pycalphad import Database as PDatabase, calculate
    x = XTDB.read(os.path.join(U.ROOT, "web", "PbSn.xtdb"))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pdb = PDatabase.from_string(x.write_tdb(), fmt="tdb")
    worst = 0.0
    for name in x.phase_names:
        cons_sets = [sorted(sp.name for sp in c) for c in pdb.phases[name].constituents]
        import itertools
        for combo in itertools.product(*cons_sets):
            pts = [[1.0 if c == k else 0.0 for c in s] for s, k in zip(cons_sets, combo)]
            atoms = sum(r for r, k in zip(pdb.phases[name].sublattices, combo) if k != "VA")
            for T in (300.37, 450.37, 800.37, 1500.37):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    res = calculate(pdb, ["PB", "SN", "VA"], name, T=T, P=101325, N=1,
                                    points=np.array([sum(pts, [])]))
                g = float(res.GM.values.squeeze()) * atoms
                d = U.rel(x.endmember_gibbs(name, ":".join(combo), T), g)
                assert d < U.ORACLE_TOL, (name, combo, T)
                worst = max(worst, d)
    print(f"\npycalphad on PbSn.xtdb -> .tdb: worst {worst:.3g}")


# ---- loud failures ---------------------------------------------------------------------------

@pytest.mark.parametrize("method", ["write_tdb", "write_utdb", "write_dat"])
def test_third_generation_refused(method, tmp_path):
    x = XTDB.read(os.path.join(U.ROOT, "data", "xtdb", "AlC.xtdb"))
    target = tmp_path / "out.file"
    with pytest.raises(ConversionError, match=r"(two-state|Einstein).*\.xtdb can"):
        getattr(x, method)(str(target))
    assert not target.exists()


def test_einstein_without_two_state_refused(tmp_path):
    """Drop the two-state liquid: the Einstein LNTH terms alone must still be refused."""
    text = open(os.path.join(U.ROOT, "data", "xtdb", "AlC.xtdb")).read()
    text = text.replace('<AmendPhase Models="LIQ2STATE" />', "")
    text = "\n".join(ln for ln in text.splitlines() if "GD(" not in ln)
    x = XTDB.read_string(text)
    with pytest.raises(ConversionError, match=r"Einstein heat capacity \(LNTH\).*\.xtdb can"):
        x.write_tdb()


def test_unevaluated_xtdb_parameter_refused():
    text = open(os.path.join(U.ROOT, "web", "PbSn.xtdb")).read()
    text = text.replace("<Bibliography>",
                        '<Parameter Id="TC(FCC_A1,PB:VA;0)" Expr="+100;" />\n<Bibliography>')
    x = XTDB.read_string(text)
    for m in ("write_xtdb", "write_tdb", "write_dat"):
        with pytest.raises(ConversionError, match=r"TC parameter.*silently drop"):
            getattr(x, m)()


def test_mqmqa_and_magnetic_refused_by_xtdb(tmp_path):
    for fname, pattern in (("LiCl-KCl.dat", r"MQMQA.*\.utdb or \.dat"),
                           ("FeC.tdb", r"Inden magnetic.*\.tdb or \.utdb")):
        db = Database.read(os.path.join(U.ROOT, "web", fname))
        target = tmp_path / "out.xtdb"
        with pytest.raises(ConversionError, match=pattern):
            db.write_xtdb(str(target))
        assert not target.exists()


def test_xtdb_header_carries_provenance():
    x = XTDB.read(os.path.join(U.ROOT, "web", "PbSn.xtdb"))
    text = x.write_xtdb()
    assert "Converted to XTDB by Hephaestus" in text.splitlines()[1]
    assert ("Converting a database does not change its license; "
            "the license of the source data applies.") in text
    assert "CC BY 4.0" in text                   # the source's own note travels with it
    import xml.etree.ElementTree as ET
    ET.fromstring(text)                          # well-formed XML


def test_xtdb_comparison_catches_a_planted_change(tmp_path):
    """The gate itself: one Pb-Sn excess coefficient moved in its 12th digit."""
    x = XTDB.read(os.path.join(U.ROOT, "web", "PbSn.xtdb"))
    text = x.write_xtdb()
    assert text.count('Expr="+5125+1.46424*T;"') == 1
    out = _save(text.replace('Expr="+5125+1.46424*T;"', 'Expr="+5125.00000001+1.46424*T;"'),
                tmp_path, "planted.xtdb")
    with pytest.raises(AssertionError):
        _compare_xtdb(x, XTDB.read(out), out)
