"""Names and identifiers at and past the fixed buffers of every reader and writer.

The release DLL links the mingw-w64 5.3 C runtime, whose snprintf returns -1 and leaves
the buffer unterminated when the text does not fit, so no fixed buffer can be trusted
to cut text safely. A name that fits (the limits below are read from the C source) must
come through every reader and writer whole, with the same energies as the short-named
database. One character more must fail with a message that says what was too long:
never cut, never a crash, never a written file. Messages built from long names stay
terminated and bounded, and end in "..." when cut.
"""
import math
import os
import re
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))
import roundtrip_util as U  # noqa: E402
from mqmqa import Database, ConversionError  # noqa: E402
from mqmqa._xtdb import XTDB  # noqa: E402
from mqmqa._abi import _ffi, _lib  # noqa: E402

SRC = os.path.join(U.ROOT, "src")


def _define(path, name):
    with open(os.path.join(SRC, path), encoding="ascii") as f:
        return int(re.search(rf"#define {name} (\d+)", f.read()).group(1))


NAME = _define("cs_dat_priv.h", "NAME_MAX") - 1    # longest name the readers keep
DESC = _define("cs_dat_priv.h", "TDB_DESC") - 1    # longest PARAMETER descriptor
XNAME = _define("xtdb.c", "XNAME") - 1             # longest XTDB name
XEXPR = _define("xtdb.c", "XEXPR") - 1             # longest XTDB expression
T_GRID = [300.37, 933.47, 1500.0, 2500.0]


def nm(prefix, n):
    """A distinct name of exactly n characters."""
    return (prefix + "X" * n)[:n]


def read_text(text, suffix):
    return XTDB.read_string(text) if suffix == ".xtdb" else Database.read_string(text)


# ---------------------------------------------------------------------------------
# sources
# ---------------------------------------------------------------------------------
def tdb_text(P="P", SA="SA", SC="SC", F="F", Q="Q"):
    return f"""$ long-name fixture
 ELEMENT /-   ELECTRON_GAS  0 0 0 !
 ELEMENT VA   VACUUM  0 0 0 !
 ELEMENT AL   FCC_A1  26.98  0 0 !
 ELEMENT CR   BCC_A2  52.0  0 0 !
 SPECIES {SA}  AL1 !
 SPECIES {SC}  CR1 !
 FUNCTION {F}  298.15  -1000+2*T-3*T*LN(T);  6000 N !
 PHASE {P}  %  2  1  1 !
 CONSTITUENT {P} : {SA},{SC} : VA : !
 PARAMETER G({P},{SA}:VA;0)  298.15  +{F}#-10*T;  6000 N !
 PARAMETER G({P},{SC}:VA;0)  298.15  -2000+3*T;  6000 N !
 PARAMETER G({P},{SA},{SC}:VA;0)  298.15  -5000+T;  6000 N !
 PARAMETER G({P},{SA},{SC}:VA;1)  298.15  +700;  6000 N !
 PHASE {Q}  %  1  1 !
 CONSTITUENT {Q} : AL : !
 PARAMETER G({Q},AL;0)  298.15  -3000+{F}#;  6000 N !
"""


def dat_text(elements, phase, subl, em_names, stoich_name=None):
    """A ChemSage file with one SUBL phase: `subl` lists each sublattice's constituents,
    which are monatomic, and em_names the endmembers in constituent-product order."""
    combos = list(np.ndindex(*[len(s) for s in subl]))
    assert len(combos) == len(em_names)
    cons = [c for s in subl for c in s]

    def elem_of(c):
        return next(e for e in sorted(elements, key=len, reverse=True) if c.startswith(e))

    lines = [" long-name fixture",
             f"   {len(elements)}   1   {len(combos)}   {1 if stoich_name else 0}",
             " " + "   ".join(elements),
             " " + "   ".join("10.0" for _ in elements),
             "   6   1   2   3   4   5   6", "   6   1   2   3   4   5   6",
             f" {phase}", " SUBL"]
    for k, (combo, name) in enumerate(zip(combos, em_names)):
        amounts = [0.0] * len(elements)
        for s, i in enumerate(combo):
            amounts[elements.index(elem_of(subl[s][i]))] += 1.0
        lines += [f" {name}", "   1   1   " + "   ".join(f"{a:.1f}" for a in amounts),
                  f"   6000.0   {-1000.0 - 37 * k}   {2.0 + k}   -3.0   0   0   0"]
    lines += [f"   {len(subl)}", "   " + "   ".join("1.0" for _ in subl),
              "   " + "   ".join(str(len(s)) for s in subl)]
    lines += ["   " + "   ".join(s) for s in subl]
    for s in range(len(subl)):
        lines.append("   " + "   ".join(str(c[s] + 1) for c in combos))
    mixing = next((s for s in range(len(subl)) if len(subl[s]) == 2), None)
    if mixing is not None:
        idx, off = [], 0
        for s, names in enumerate(subl):
            idx += [off + 1, off + 2] if s == mixing else [off + 1]
            off += len(names)
        lines += [f"   {len(idx)}   " + "   ".join(map(str, idx)), "   1",
                  "   -5000.0   1.0   0   0   0   0"]
    lines.append("   0")
    if stoich_name:
        lines += [f" {stoich_name}", "   1   1   " + "   ".join("1.0" for _ in elements),
                  "   6000.0   -3000.0   0   0   0   0   0"]
    return "\n".join(lines) + "\n"


def licl_kcl(li="Li+1", cl="Cl", element_li="Li", code="Q"):
    """The shipped LiCl-KCl liquid with its Li cation, Cl anion or Li element renamed."""
    with open(os.path.join(U.ROOT, "data", "licl-kcl", "LiCl-KCl.dat"), encoding="ascii") as f:
        text = f.read()
    text = text.replace(" Li+1 ", f" {li} ", 1)
    text = text.replace("\n Cl\n", f"\n {cl}\n", 1)
    text = text.replace("\n Li ", f"\n {element_li} ", 1)
    return text.replace("\n Q   1   2   3   3   0", f"\n {code}   1   2   3   3   0", 1)


def xtdb_text(P="LIQ", A="AL", B="CR", F="GA", expr="-1000+2*T-3*T*LN(T);", high="6000",
              inter=True, extra=""):
    ex = f'<Parameter Id="G({P},{A},{B};0)" Expr="-5000+T;" />\n' if inter else ""
    return f"""<XTDB version="0.1.5">
<!-- long-name fixture -->
<Defaults LowT="298.15" HighT="6000" Elements="VA /-" />
<Element Id="{A}" Refstate="FCC_A1" Mass="26.98" H298="0" S298="0" />
<Element Id="{B}" Refstate="BCC_A2" Mass="52.0" H298="0" S298="0" />
<Species Id="VA" Stoichiometry="VA" />
<Species Id="{A}" Stoichiometry="{A}" />
<Species Id="{B}" Stoichiometry="{B}" />
<Phase Id="{P}" Configuration="CEF" State="L" >
  <Sublattices NumberOf="1" Multiplicities="1" >
    <Constituents Sublattice="1" List="{A} {B}" />
  </Sublattices>
</Phase>
<TPfun Id="{F}" LowT="298.15" Expr="{expr}" HighT="{high}" />
<Parameter Id="G({P},{A};0)" Expr="+{F};" />
<Parameter Id="G({P},{B};0)" Expr="-2000+3*T;" />
{ex}{extra}</XTDB>
"""


# ---------------------------------------------------------------------------------
# comparisons
# ---------------------------------------------------------------------------------
def db_energies(db):
    rng = np.random.default_rng(3)
    out = []
    for p in range(len(db.phase_names)):
        subls = db.cef_sublattices(p)
        ys = [Y for Y in U._endmembers(subls)] + [U._random_Y(subls, rng) for _ in range(3)]
        out += [db.cef_gibbs(p, Y, T) for Y in ys for T in T_GRID]
    out += [db.stoich_gibbs(i, T) for i in range(len(db.stoich)) for T in T_GRID]
    return out


def xtdb_energies(x, B):
    return [x.phase_gibbs(p, B, xb, T)[0] for p in range(len(x.phase_names))
            for xb in (1e-6, 0.3, 0.7, 1 - 1e-6) for T in T_GRID]


def names_of(db):
    return (db.phase_names, db.stoich,
            [[s["constituents"] for s in db.cef_sublattices(p)] for p in range(len(db.phase_names))])


def assert_close(a, b):
    assert len(a) == len(b)
    for u, v in zip(a, b):
        assert U.rel(u, v) <= U.REL_TOL, (u, v)


# ---------------------------------------------------------------------------------
# TDB reader
# ---------------------------------------------------------------------------------
def test_tdb_names_at_the_limit_read_whole():
    long_ = Database.read_string(tdb_text(P=nm("P", NAME), SA=nm("SA", NAME), SC=nm("SC", NAME),
                                          F=nm("F", NAME), Q=nm("Q", NAME)))
    short = Database.read_string(tdb_text())
    assert long_.phase_names == [nm("P", NAME)] and long_.stoich == [nm("Q", NAME)]
    assert long_.cef_sublattices(0)[0]["constituents"] == [nm("SA", NAME), nm("SC", NAME)]
    assert db_energies(long_) == db_energies(short)


@pytest.mark.parametrize("kind", ["phase", "species", "function", "compound", "reference"])
def test_tdb_name_past_the_limit_fails(kind):
    long_ = nm(kind.upper(), NAME + 1)
    text = {"phase": tdb_text(P=long_), "species": tdb_text(SA=long_),
            "function": tdb_text(F=long_), "compound": tdb_text(Q=long_),
            "reference": tdb_text().replace("+F#-10*T", f"+{long_}#-10*T")}[kind]
    with pytest.raises(OSError, match=rf"{long_[:20]}X*\.\.\. is longer than {NAME} characters"):
        Database.read_string(text)


def test_tdb_element_past_the_limit_fails():
    long_ = nm("EL", NAME + 1)
    text = tdb_text().replace(" ELEMENT CR   BCC_A2", f" ELEMENT {long_}   BCC_A2")
    with pytest.raises(OSError, match=rf"longer than {NAME} characters"):
        Database.read_string(text)


def test_tdb_long_keyword_word_is_tolerated():
    """Only a keyword's start is matched, so an overlong first word of a statement the
    reader skips is not an error."""
    text = tdb_text() + f" DATABASE_INFO_{'Z' * 3 * NAME} some text !\n"
    assert db_energies(Database.read_string(text)) == db_energies(Database.read_string(tdb_text()))


# Six sublattices of 63-character species, the first mixing two: the interaction's
# descriptor, phase + "," + seven names, five colons and a comma + ";0", is the longest.
WIDE_FIT = DESC - (7 * NAME + 6) - 3


def _wide_tdb(phase_len):
    species = [nm(f"S{k}", NAME) for k in range(7)]
    P = nm("P", phase_len)
    rest = ":".join(species[2:])
    text = tdb_text().split(" PHASE ")[0] + "".join(f" SPECIES {s}  AL1 !\n" for s in species)
    text += f" PHASE {P}  %  6" + "  1" * 6 + " !\n"
    text += f" CONSTITUENT {P} : {species[0]},{species[1]} : " + " : ".join(species[2:]) + " : !\n"
    text += f" PARAMETER G({P},{species[0]}:{rest};0)  298.15  -1234+5*T;  6000 N !\n"
    text += f" PARAMETER G({P},{species[1]}:{rest};0)  298.15  -2345+6*T;  6000 N !\n"
    text += f" PARAMETER G({P},{species[0]},{species[1]}:{rest};0)  298.15  -3456;  6000 N !\n"
    return text, P


def test_tdb_parameter_descriptor_at_and_past_the_limit():
    text, P = _wide_tdb(WIDE_FIT)
    db = Database.read_string(text)
    assert db.phase_names == [P]
    assert db.cef_gibbs(0, [1, 0] + [1] * 5, 1000.0, per_mole_atoms=False) == -1234 + 5 * 1000.0
    back = Database.read_string(db.write_tdb())          # the writer keeps within it too
    assert names_of(back) == names_of(db)
    assert db_energies(back) == db_energies(db)
    text, _ = _wide_tdb(WIDE_FIT + 1)
    with pytest.raises(OSError, match=rf"PARAMETER descriptor .* is longer than {DESC} characters"):
        Database.read_string(text)


# ---------------------------------------------------------------------------------
# ChemSage .dat reader
# ---------------------------------------------------------------------------------
def _dat(n_el=NAME, n_ph=NAME, n_em=NAME, n_q=NAME):
    A, B = nm("A", n_el), nm("B", n_el)
    return dat_text([A, B], nm("PH", n_ph), [[A, B]], [nm("EA", n_em), nm("EB", n_em)],
                    stoich_name=nm("Q", n_q)), A, B


def test_dat_names_at_the_limit_read_whole():
    text, A, B = _dat()
    db = Database.read_string(text)
    short = Database.read_string(_dat(2, 2, 2, 2)[0])
    assert [e for e, _ in db.elements] == [A, B]
    assert db.phase_names == [nm("PH", NAME)] and db.stoich == [nm("Q", NAME)]
    assert db.cef_sublattices(0)[0]["constituents"] == [A, B]
    assert db_energies(db) == db_energies(short)


@pytest.mark.parametrize("which", ["n_el", "n_ph", "n_em", "n_q"])
def test_dat_name_past_the_limit_fails(which):
    text = _dat(**{which: NAME + 1})[0]
    with pytest.raises(OSError, match=rf"line \d+: name .* is longer than {NAME} characters"):
        Database.read_string(text)


# ---------------------------------------------------------------------------------
# writers
# ---------------------------------------------------------------------------------
# (format, longest species name that fits, why one more does not)
WRITER_LIMITS = [
    ("write_tdb", ".tdb", NAME, None),
    ("write_utdb", ".utdb", NAME, None),
    # a TDB endmember is named by its constituents, SA:VA
    ("write_dat", ".dat", NAME - 3, rf"species name .* is longer than the {NAME} characters"),
    # the XTDB interaction SA,SC:VA is a parameter-Id field of XNAME characters
    ("write_xtdb", ".xtdb", (XNAME - 4) // 2, rf"interaction .* is longer than the XTDB engine's {XNAME}"),
]


def _long_tdb(n_species, n_sc=None):
    return Database.read_string(tdb_text(P=nm("P", NAME), SA=nm("SA", n_species),
                                         SC=nm("SC", n_species if n_sc is None else n_sc),
                                         F=nm("F", NAME), Q=nm("Q", NAME)))


@pytest.mark.parametrize("fn,suffix,fit,why", WRITER_LIMITS, ids=[w[0] for w in WRITER_LIMITS])
def test_writer_at_the_limit_keeps_every_name(fn, suffix, fit, why, tmp_path):
    n_sc = XNAME - 4 - fit if fn == "write_xtdb" else fit   # SA,SC:VA exactly XNAME long
    db = _long_tdb(fit, n_sc)
    path = tmp_path / ("out" + suffix)
    getattr(db, fn)(str(path))
    back = (XTDB.read if suffix == ".xtdb" else Database.read)(str(path))
    if suffix == ".xtdb":
        assert back.phase_names == db.phase_names + db.stoich
        sa, sc = db.cef_sublattices(0)[0]["constituents"]
        for T in T_GRID:
            assert U.rel(back.endmember_gibbs(db.phase_names[0], f"{sa}:VA", T),
                         db.cef_gibbs(0, [1, 0, 1], T, per_mole_atoms=False)) <= U.REL_TOL
            assert U.rel(back.endmember_gibbs(db.phase_names[0], f"{sc}:VA", T),
                         db.cef_gibbs(0, [0, 1, 1], T, per_mole_atoms=False)) <= U.REL_TOL
        assert f"G({db.phase_names[0]},{sa},{sc}:VA;1)" in path.read_text()
    else:
        assert names_of(back) == names_of(db)
        assert_close(db_energies(back), db_energies(db))


@pytest.mark.parametrize("fn,suffix,fit,why", [w for w in WRITER_LIMITS if w[3]],
                         ids=[w[0] for w in WRITER_LIMITS if w[3]])
def test_writer_past_the_limit_fails_and_writes_nothing(fn, suffix, fit, why, tmp_path):
    n_sc = XNAME - 4 - fit + 1 if fn == "write_xtdb" else fit + 1
    db = _long_tdb(fit, n_sc) if fn == "write_xtdb" else _long_tdb(fit + 1)
    path = tmp_path / ("out" + suffix)
    with pytest.raises(ConversionError, match=why):
        getattr(db, fn)(str(path))
    assert not path.exists()


def _wide_dat(n_subl, phase_len):
    """A .dat phase of n_subl sublattices, the first mixing two constituents, each a
    63-character aluminium ion (AL000...0k+) the TDB writer resolves to AL with charge k."""
    ion = ["AL" + str(k + 1).zfill(NAME - 3) + "+" for k in range(n_subl + 1)]
    assert all(len(c) == NAME for c in ion)
    subl = [ion[:2]] + [[c] for c in ion[2:]]
    return dat_text(["AL"], nm("P", phase_len), subl, ["EM1", "EM2"])


def test_tdb_writer_long_constituent_arrays():
    """The .dat twin of the descriptor limit: at it the TDB text reads back whole, one
    phase character more is refused, and twenty sublattices (past the 1023-character
    array buffer, where the old code stepped past its end) are refused too."""
    db = Database.read_string(_wide_dat(6, WIDE_FIT))
    back = Database.read_string(db.write_tdb())
    assert names_of(back)[2] == names_of(db)[2]
    assert_close(db_energies(back), db_energies(db))
    with pytest.raises(ConversionError, match=rf"longer than the {DESC} characters a TDB descriptor"):
        Database.read_string(_wide_dat(6, WIDE_FIT + 1)).write_tdb()
    wide = Database.read_string(_wide_dat(20, NAME))
    with pytest.raises(ConversionError, match=r"a constituent array of P\w* is longer than 1023"):
        wide.write_tdb()
    with pytest.raises(ConversionError, match=r"20 sublattices; the XTDB engine reads 8"):
        wide.write_xtdb()
    again = Database.read_string(wide.write_dat())
    assert names_of(again) == names_of(wide)
    assert_close(db_energies(again), db_energies(wide))


def test_species_composition_past_the_limit_fails():
    """1E14 is four characters in a TDB species but prints as fifteen, so eight of them
    fit the reader and not the writer's species field."""
    comp = "".join(f"{e}1E14" for e in ("AL", "CR", "FE", "NI", "CO", "MN", "SI", "TI"))
    assert len(comp) <= NAME
    els = "".join(f" ELEMENT {e}   X  1.0  0 0 !\n" for e in ("FE", "NI", "CO", "MN", "SI", "TI"))
    text = tdb_text().replace(" SPECIES SA  AL1 !", els + f" SPECIES SA  {comp} !")
    with pytest.raises(ConversionError, match=rf"composition of species SA is longer than the {NAME}"):
        Database.read_string(text).write_tdb()


def _pair_dat(anion_base):
    """LiCl-KCl with ions named so the uTDB reading names its LiCl pair from them:
    LI1.000...0+1 (base 33 characters) and CL1.000...0-1."""
    li = "LI1." + "0" * 29 + "+1"
    cl = "CL1." + "0" * (anion_base - 4) + "-1"
    return Database.read_string(licl_kcl(li=li, cl=cl))


def test_pair_name_at_and_past_the_limit():
    ok = Database.read_string(_pair_dat(NAME - 33).write_utdb())
    assert ok.cations(0)[0]["name"] == "LI1." + "0" * 29 + "+1"
    back = Database.read_string(ok.write_dat())
    for T in T_GRID:
        assert back.pairs(0, T)["G"] == ok.pairs(0, T)["G"]
    bad = Database.read_string(_pair_dat(NAME - 32).write_utdb())
    with pytest.raises(ConversionError, match=rf"species name LI1\.0+CL1\.0+\.\.\. is longer than the {NAME}"):
        bad.write_dat()


def test_utdb_long_quadruplet_names():
    """A 63-character MQMQA liquid, cation and anion come through the uTDB statements
    whole, also where a statement names the phase with its :Q suffix; 64 fails. The ions
    are LI000...01+ and CL000...01-, which the writer resolves to Li+ and Cl-."""
    li, cl = "LI" + "0" * (NAME - 4) + "1+", "CL" + "0" * (NAME - 4) + "1-"
    liq = nm("LIQ", NAME)
    text = licl_kcl(li=li, cl=cl).replace(" LiCl-KCl-liquid\n", f" {liq}\n")
    db = Database.read_string(text)
    utdb = db.write_utdb()
    assert f" PHASE {liq}:Q " in utdb
    for version in (utdb, utdb.replace(f"({liq},", f"({liq}:Q,")):
        back = Database.read_string(version)
        assert back.phase_names == db.phase_names
        assert [c["name"] for c in back.cations(0)] == [c["name"] for c in db.cations(0)]
        assert [a["name"] for a in back.anions(0)] == [cl]
        for T in T_GRID:
            assert_close(back.pairs(0, T)["G"], db.pairs(0, T)["G"])
            assert_close(back.mqmx(0, T)["L"], db.mqmx(0, T)["L"])
    long_ = "LI" + "0" * (NAME - 3) + "1+"
    with pytest.raises(OSError, match=rf"longer than {NAME} characters"):
        Database.read_string(utdb.replace(li, long_))


# ---------------------------------------------------------------------------------
# XTDB reader and writers
# ---------------------------------------------------------------------------------
def test_xtdb_names_at_the_limit_read_whole():
    half = (XNAME - 1) // 2            # the interaction A,B fills XNAME exactly
    A, B = nm("A", half), nm("B", XNAME - 1 - half)
    x = XTDB.read_string(xtdb_text(P=nm("P", XNAME), A=A, B=B, F=nm("F", XNAME)))
    short = XTDB.read_string(xtdb_text(A="A", B="B"))
    assert x.phase_names == [nm("P", XNAME)] and x.elements == [A, B]
    assert xtdb_energies(x, B) == xtdb_energies(short, "B")
    back = XTDB.read_string(x.write_xtdb())
    assert xtdb_energies(back, B) == xtdb_energies(x, B)
    # 63-character element names, no interaction parameter
    A, B = nm("A", XNAME), nm("B", XNAME)
    x = XTDB.read_string(xtdb_text(A=A, B=B, inter=False))
    assert x.elements == [A, B]
    assert xtdb_energies(x, B) == xtdb_energies(XTDB.read_string(xtdb_text(A="A", B="B", inter=False)), "B")


def test_xtdb_expression_at_the_limit():
    expr = "-1000+2*T-3*T*LN(T);"
    pad = "-1000." + "0" * (XEXPR - len(expr) - 1)     # same value, XEXPR characters in all
    full = pad + expr[5:]
    assert len(full) == XEXPR
    x = XTDB.read_string(xtdb_text(expr=full))
    assert xtdb_energies(x, "CR") == xtdb_energies(XTDB.read_string(xtdb_text()), "CR")
    assert xtdb_energies(XTDB.read_string(x.write_xtdb()), "CR") == xtdb_energies(x, "CR")
    with pytest.raises(OSError, match=rf"Expr attribute of a TPfun, .* is longer than {XEXPR}"):
        XTDB.read_string(xtdb_text(expr="-1000.0" + full[6:]))


@pytest.mark.parametrize("case", ["phase", "element", "constituent", "tpfun", "interaction",
                                  "high", "multiplicities"])
def test_xtdb_value_past_the_limit_fails(case):
    long_ = nm("L", XNAME + 1)
    half = (XNAME - 1) // 2
    text = {
        "phase": xtdb_text(P=long_),
        "element": xtdb_text(A=long_, inter=False).replace(f'List="{long_} CR"', 'List="AL CR"'),
        "constituent": xtdb_text(inter=False).replace('List="AL CR"', f'List="AL {long_}"'),
        "tpfun": xtdb_text(F=long_),
        "interaction": xtdb_text(A=nm("A", half), B=nm("B", XNAME - half)),
        "high": xtdb_text(high="6000." + "0" * (XNAME - 4)),
        "multiplicities": xtdb_text().replace('Multiplicities="1"',
                                              'Multiplicities="1' + " " * XEXPR + '"'),
    }[case]
    with pytest.raises(OSError, match=r"is longer than \d+ characters"):
        XTDB.read_string(text)


def test_xtdb_carried_text_past_the_limit_blocks_the_writers():
    """Reference text the engine does not evaluate loads, but no writer passes on a
    copy cut to fit."""
    extra = f'<Bibliography>\n<Bibitem Id="REF1" Text="{"T" * (XEXPR + 1)}" />\n</Bibliography>\n'
    x = XTDB.read_string(xtdb_text(extra=extra))
    assert xtdb_energies(x, "CR") == xtdb_energies(XTDB.read_string(xtdb_text()), "CR")
    for fn in ("write_xtdb", "write_tdb", "write_utdb", "write_dat"):
        with pytest.raises(ConversionError, match=rf"Text attribute longer than {XEXPR} characters"):
            getattr(x, fn)()


def test_xtdb_overlong_function_reference_is_not_cut():
    """A 64-character reference in an expression names no function (Ids hold 63), so the
    read fails on that expression; cut to 63 it would name the 63-character function the
    file does define."""
    ref = nm("F", XNAME + 1)
    with pytest.raises(OSError, match=rf"cannot read the expression of G\(LIQ,AL;0\): \+{ref};"):
        XTDB.read_string(xtdb_text(F=nm("F", XNAME)).replace(
            f'Expr="+{nm("F", XNAME)};"', f'Expr="+{ref};"'))


# ---------------------------------------------------------------------------------
# messages and notes
# ---------------------------------------------------------------------------------
def test_cut_messages_stay_terminated_and_say_so():
    """The first lossy note (a 255-character field) holds a 400-character parameter Id;
    the writer's message around it is cut again at 255. Both end in '...'."""
    extra = f'<Parameter Id="{"G" * 400}" Expr="1;" />\n'
    x = XTDB.read_string(xtdb_text(extra=extra))
    with pytest.raises(ConversionError) as err:
        x.write_xtdb()
    msg = str(err.value)
    assert msg.startswith("cannot write XTDB: the source carries an unparsed parameter Id GGG")
    assert msg.endswith("...") and len(msg) == 255


def test_excess_message_names_long_ions_whole():
    li, cl = nm("LI", NAME - 2) + "+1", nm("CL", NAME)
    db = Database.read_string(licl_kcl(li=li, cl=cl, code="B"))
    msg = db.excess_unsupported(0)
    assert f"between {li} and K+1 uses an excess code other than Q or G" in msg
    assert msg.endswith("so its energy is not computed")


def test_read_error_reaches_the_tq_interface_whole():
    _ffi.cdef("""
      void* tq_init(void);
      int tq_read_string(void*, const char*);
      void tq_free(void*);
      const char* tq_error(const void*);
    """, override=True)
    ctx = _lib.tq_init()
    try:
        assert _lib.tq_read_string(ctx, _dat(n_ph=NAME + 1)[0].encode()) == 1
        err = _ffi.string(_lib.tq_error(ctx)).decode()
        assert re.fullmatch(rf"line \d+: name PHX+\.\.\. is longer than {NAME} characters", err)
    finally:
        _lib.tq_free(ctx)


# ---------------------------------------------------------------------------------
# equilibrium: element symbols read from constituent names are not cut
# ---------------------------------------------------------------------------------
def _equilibrate(text, target):
    cdb = _lib.mqmqa_db_read_string(text.encode())
    try:
        els = [_ffi.string(_lib.mqmqa_db_element(cdb, e)).decode()
               for e in range(_lib.mqmqa_db_num_elements(cdb))]
        nq = _lib.mqmqa_num_quadruplets(2, 1)
        X = _ffi.new("double[]", nq)
        gm = _lib.mqmqa_equilibrate_db(cdb, 0, 1000.0,
                                       _ffi.new("double[]", [target[e] for e in els]), X, _ffi.NULL)
        return gm, list(X)
    finally:
        _lib.mqmqa_db_free(cdb)


def test_long_element_symbol_reaches_the_equilibrium():
    """An element named with eight letters or more was cut to seven when matched to its
    cation, so its share of the target composition was dropped."""
    long_ = nm("LITHIUM", 20)
    ref = _equilibrate(licl_kcl(), {"LI": 0.3, "K": 0.7, "CL": 1.0})
    got = _equilibrate(licl_kcl(li=long_ + "+1", element_li=long_),
                       {long_: 0.3, "K": 0.7, "CL": 1.0})
    assert math.isfinite(ref[0]) and got == ref
