"""Database writer, ChemSage .dat: read -> write -> read back reproduces the model.

The same round-trip gate as the TDB writers (roundtrip_util) over every shipped
database, plus the cross-format paths .tdb -> .dat and .dat -> .utdb -> .dat. The
written files are then read by pycalphad's own ChemSage reader and compared with
Hephaestus's energies for the ORIGINAL file: CEF solutions and compounds through
pycalphad's calculate(), MQMQA liquids through its ModelMQMQA reference, ideal-mixing
and excess terms at fixed quadruplet fractions. The Inden magnetic model has no
ChemSage form the reader evaluates, so magnetic sources must be refused.
"""
import os
import re
import sys
import warnings

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))
import roundtrip_util as U  # noqa: E402
import mqmqa  # noqa: E402
from mqmqa import Database, ConversionError  # noqa: E402

SHIPPED = [f for f in U.shipped_databases()
           if not f.endswith(".xtdb") and not U.is_nasa_thermo(f)]
IDS = [os.path.relpath(f, U.ROOT).replace("\\", "/") for f in SHIPPED]
EXTRA = U.pycalphad_fixtures(["Al-Mg_Zhong.tdb", "alzn_mey.tdb", "pbsn.tdb",
                              "crfe_bcc_magnetic.tdb", "Shishin_Fe-Sb-O-S_slag.dat",
                              "MQMQA-tern-tests.dat"])
EXTRA_IDS = ["pycalphad/" + os.path.basename(f) for f in EXTRA]


def _magnetic(path):
    """The file declares the Inden magnetic model (only TDB sources can)."""
    return path.lower().endswith((".tdb", ".utdb")) and any(
        ln.strip().upper().startswith("TYPE_DEF") and "MAGNETIC" in ln.upper()
        for ln in open(path).read().splitlines())


@pytest.mark.parametrize("path", SHIPPED + EXTRA, ids=IDS + EXTRA_IDS)
def test_dat_roundtrip(path, tmp_path):
    db = Database.read(path)
    if _magnetic(path):
        target = tmp_path / "x.dat"
        with pytest.raises(ConversionError, match=r"Inden magnetic.*\.tdb or \.utdb"):
            db.write_dat(str(target))
        assert not target.exists()
        return
    back, _ = U.roundtrip(db, "write_dat", tmp_path, ".dat")
    worst = U.compare(db, back)
    print(f"\nDAT  {os.path.basename(path)}: worst relative deviation {worst:.3g}")


@pytest.mark.parametrize("path", [f for f in SHIPPED if f.endswith(".dat")],
                         ids=[i for i in IDS if i.endswith(".dat")])
def test_dat_utdb_dat(path, tmp_path):
    """.dat -> .utdb -> .dat: the MQMQA liquid crosses into TDB grammar and back."""
    db = Database.read(path)
    mid, _ = U.roundtrip(db, "write_utdb", tmp_path, ".utdb")
    back, _ = U.roundtrip(mid, "write_dat", tmp_path, ".dat")
    worst = U.compare(db, back)
    print(f"\nDAT->uTDB->DAT {os.path.basename(path)}: worst {worst:.3g}")


def test_pair_element_rows_rebuilt_from_utdb(tmp_path):
    """A uTDB pair has no element row; the .dat writer derives it from the ions and the
    quadruplet stoichiometry. It must equal the row the original .dat carried."""
    src = os.path.join(U.ROOT, "web", "FeO-MgO-SiO2-combined.dat")
    db = Database.read(src)
    mid, _ = U.roundtrip(db, "write_utdb", tmp_path, ".utdb")
    rows_orig = _pair_rows(open(src).read())
    rows_back = _pair_rows(mid.write_dat())
    assert rows_orig == rows_back


def _pair_rows(text):
    """{pair name: element row} of the first SUBQ block of a ChemSage file."""
    toks = text.upper().split("\n", 1)[1].split()
    n_el = int(toks[0])
    i = toks.index("SUBQ") + 1
    n_pairs = int(toks[i])
    i += 2
    rows = {}
    for _ in range(n_pairs):
        name, n_int = toks[i], int(toks[i + 2])
        eq = int(toks[i + 1])
        rows[name] = [float(x) for x in toks[i + 3:i + 3 + n_el]]
        i += 3 + n_el
        for _ in range(n_int):
            i += 1 + 6
            if eq == 4:
                i += 1 + 2 * int(toks[i])
        i += 5 + 1
    return rows


# ---- independent reader: pycalphad's ChemSage parser on the written files ----

def _pyc_order(name_lists):
    """pycalphad orders each sublattice's constituents by name; Hephaestus by file."""
    return [sorted(range(len(n)), key=lambda k: n[k]) for n in name_lists]


def _mqmqa_energy_hephaestus(db, p, T, Xkey):
    """Reference + ideal + excess per mole of quadruplets from the C energy routines."""
    cats, ans = db.cations(p), db.anions(p)
    nc, na = len(cats), len(ans)
    qc, qa = [c["charge"] for c in cats], [a["charge"] for a in ans]
    ca, cb, ax, ay = mqmqa.enumerate_quadruplets(nc, na)
    quads = list(zip(ca, cb, ax, ay))
    mz = db.mqmz(p)

    def Z(is_cat, sp, A, B, X, Y):
        return mqmqa.coordination(is_cat, sp, A, B, X, Y, nc, na, qc, qa,
                                  mz["A"], mz["B"], mz["X"], mz["Y"], mz["Z"])
    Za = [Z(1, A, A, B, X, Y) for A, B, X, Y in quads]
    Zb = [Z(1, B, A, B, X, Y) for A, B, X, Y in quads]
    Zx = [Z(0, X, A, B, X, Y) for A, B, X, Y in quads]
    Zy = [Z(0, Y, A, B, X, Y) for A, B, X, Y in quads]
    X = [Xkey[q] for q in quads]
    pr = db.pairs(p, T)
    Ztab = [Z(1, pc, A, B, Xq, Yq) if pc in (A, B) else 1.0
            for pc in pr["cat"] for A, B, Xq, Yq in quads]
    ref = mqmqa.reference_energy(ca, cb, ax, ay, X, pr["cat"], pr["an"], pr["G"],
                                 pr["stoich"], Ztab)
    zeta = [0.0] * (nc * na)
    for c, a, z in zip(pr["cat"], pr["an"], pr["zeta"]):
        zeta[c * na + a] = z
    ideal = mqmqa.ideal_mixing_energy(T, nc, na, ca, cb, ax, ay, X, Za, Zb, Zx, Zy,
                                      zeta, db.is_subq(p))
    mx = db.mqmx(p, T)
    exc = mqmqa.excess_energy(nc, na, ca, cb, ax, ay, X, Za, Zb, Zx, Zy, mx["mix"],
                              mx["code"], mx["A"], mx["B"], mx["X"], mx["Y"], mx["p"],
                              mx["q"], mx["L"], mx["r"], mx["addcat"],
                              [c["group"] for c in cats], [a["group"] for a in ans])
    return ref + ideal + exc


def _element_charge(sp):
    el = next(iter(sp.constituents)) if sp.constituents else sp.name
    return el, abs(sp.charge)


def _mqmqa_energy_pycalphad(pdb, name, comps, db, p, T, Xkey):
    from pycalphad import variables as v
    from pycalphad.models.model_mqmqa import ModelMQMQA
    mod = ModelMQMQA(pdb, comps, name)
    rc = [(re.match(r"[A-Z]+", c["name"]).group(0), c["charge"]) for c in db.cations(p)]
    ra = [(re.match(r"[A-Z]+", a["name"]).group(0), a["charge"]) for a in db.anions(p)]
    ci = {c: rc.index(_element_charge(c)) for c in mod.cations}
    ai = {a: ra.index(_element_charge(a)) for a in mod.anions}
    subs = {v.T: T}
    for A, B, X, Y in mod._quadruplets:
        a, b, x, y = ci[A], ci[B], ai[X], ai[Y]
        subs[mod._X_ijkl(A, B, X, Y)] = Xkey[(min(a, b), max(a, b), min(x, y), max(x, y))]
    return float((mod.reference_energy(pdb) + mod.ideal_mixing_energy(pdb)
                  + mod.excess_mixing_energy(pdb)).subs(subs))


DAT_WRITABLE = [f for f in SHIPPED + EXTRA if not _magnetic(f)]

# Ternary terms with mixed chemical groups: Hephaestus's excess routine does not
# implement the multi-group interpolation and refuses these phases (NaN), so the written
# file is checked against pycalphad on the source only, and the refusal is asserted.
ENGINE_GAPS = {("MQMQA-tern-tests.dat", "TERN_XS_121"), ("MQMQA-tern-tests.dat", "TERN_XS_122")}


@pytest.mark.parametrize("path", DAT_WRITABLE,
                         ids=[os.path.relpath(f, U.ROOT).replace("\\", "/")
                              if f.startswith(U.ROOT) else "pycalphad/" + os.path.basename(f)
                              for f in DAT_WRITABLE])
def test_written_dat_matches_pycalphad(path):
    pytest.importorskip("pycalphad")
    from pycalphad import Database as PDatabase, calculate
    db = Database.read(path)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pdb = PDatabase.from_string(db.write_dat(), fmt="dat")
        pdb_orig = PDatabase(path) if path.endswith(".dat") else None
    comps = [e for e, _ in db.elements] + ["VA"]
    rng = np.random.default_rng(3)
    worst, n = 0.0, 0
    for p, name in enumerate(db.phase_names):
        if db.phase_kind(p) == 1:
            subls = db.cef_sublattices(p)
            order = _pyc_order([s["constituents"] for s in subls])
            for T in (300.37, 1000.37, 2200.37):
                Ys = [U._random_Y(subls, rng) for _ in range(4)]
                pts = []
                for Y in Ys:
                    row, off = [], 0
                    for s, o in zip(subls, order):
                        blk = Y[off:off + len(s["constituents"])]
                        row += [blk[k] for k in o]
                        off += len(s["constituents"])
                    pts.append(row)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    res = calculate(pdb, comps, name, T=T, P=101325, N=1, points=np.array(pts))
                for Y, g in zip(Ys, np.atleast_1d(res.GM.values.squeeze())):
                    d = U.rel(db.cef_gibbs(p, Y, T, per_mole_atoms=True), float(g))
                    assert d < U.ORACLE_TOL, (name, T, Y)
                    worst, n = max(worst, d), n + 1
            continue
        nc, na = len(db.cations(p)), len(db.anions(p))
        quads = list(zip(*mqmqa.enumerate_quadruplets(nc, na)))
        for T in (1273.37, 1873.37):
            w = rng.uniform(0.2, 1.0, len(quads))
            Xkey = dict(zip(quads, w / w.sum()))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                g_py = _mqmqa_energy_pycalphad(pdb, name, comps, db, p, T, Xkey)
                if pdb_orig is not None:   # pycalphad alone: the writer changed nothing
                    g_po = _mqmqa_energy_pycalphad(pdb_orig, name, comps, db, p, T, Xkey)
                    assert U.rel(g_po, g_py) < U.ORACLE_TOL, (name, T, g_po, g_py)
            g_he = _mqmqa_energy_hephaestus(db, p, T, Xkey)
            if (os.path.basename(path), name) in ENGINE_GAPS:
                assert np.isnan(g_he), (name, T, g_he)
                continue
            d = U.rel(g_he, g_py)
            assert d < U.ORACLE_TOL, (name, T, g_he, g_py)
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
    print(f"\npycalphad on written DAT {os.path.basename(path)}: {n} points, worst {worst:.3g}")


def test_binary_diagram_survives_dat(tmp_path):
    """Al-Zn from a TDB source, through .dat, keeps its stable phases at every T."""
    db = Database.read(os.path.join(U.ROOT, "web", "AlZn.tdb"))
    back, _ = U.roundtrip(db, "write_dat", tmp_path, ".dat")
    stable = set()
    for T in np.linspace(400.37, 1000.37, 13):
        h1 = U.lower_hull(U.cef_binary_points(db, "AL", "ZN", T))
        h2 = U.lower_hull(U.cef_binary_points(back, "AL", "ZN", T))
        U.compare_hulls(h1, h2)
        stable |= {ph for _, _, ph in h1}
    assert len(stable) >= 3


def test_header_carries_provenance():
    db = Database.read(os.path.join(U.ROOT, "web", "LiCl-KCl.dat"))
    first = db.write_dat().splitlines()[0]
    assert "Converted to ChemSage .dat by Hephaestus" in first
    assert "from LiCl-KCl.dat" in first
    assert ("Converting a database does not change its license; "
            "the license of the source data applies.") in first
