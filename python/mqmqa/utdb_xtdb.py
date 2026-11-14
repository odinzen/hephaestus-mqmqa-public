"""Convert uTDB files to XTDB and back, MQMQA liquids included.

XTDB (Sundman et al., Calphad 90 (2025) 102849) defines the compound energy formalism,
stoichiometric phases and the Inden-Hillert-Jarl magnetic model, and these are written
the way the paper and its documentation describe. For MQMQA the XTDB documentation
defines only the quadruplets, as species carrying an MQMQA attribute, and calls even
that tentative; it names no parameters for the pair energies or the excess. MQMQA
phases are therefore written in a form proposed here (docs/XTDB_MQMQA_PROPOSAL.md),
which no other software reads yet:

  - the phase has Configuration="MQMQA" and lists its ions on two sublattices;
  - each quadruplet with stated coordination numbers is a Species whose MQMQA
    attribute follows the XTDB documentation ("A,B/X Z_A Z_B Z_X"; a pure pair adds
    its zeta), with an MQSTOI attribute for the pair stoichiometry row;
  - pair energies, excess terms and chemical groups keep their uTDB parameter Ids
    (MQG, MQX<c>, MQXT<c>, MQGRP).

The conversion works on the text and keeps every expression as written, so a file
converted to XTDB and back reads as the same database. Function references lose their
TDB '#' on the way to XTDB and get it back on the return.

Sources read while writing this module: the XTDB paper and the format documentation in
github.com/sundmanbo/XTDB (GPL-3.0; documents only, no code), and the writer of
pycalphad-xtdb (Odinzen, MIT) for the magnetic model Ids.
"""
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import quoteattr

XTDB_VERSION = "0.1.5"
TDB_R = "8.3145"           # the gas constant a TDB file means when it states none

# TYPE_DEFINITION GES A_P_D <phase> MAGNETIC <afm> <p>  <->  XTDB magnetic model Id
MAGNETIC_IDS = {("-1.0", "0.4"): "IHJBCC", ("-3.0", "0.28"): "IHJREST"}
MAGNETIC_TDB = {v: k for k, v in MAGNETIC_IDS.items()}

_IGNORED = ("DEFINE_SYSTEM_DEFAULT", "DEFAULT_COMMAND", "DATABASE_INFO", "VERSION_DATE")


class ConversionError(ValueError):
    """The input holds something this converter cannot carry without losing it."""


@dataclass
class Ranged:
    """A TDB piecewise expression: LowT, then (expression, HighT) pieces, and a reference."""
    low: str
    pieces: list
    ref: str = ""


@dataclass
class Phase:
    name: str
    mqmqa: bool
    mult: list
    constituents: list = field(default_factory=list)
    magnetic: str = ""         # XTDB magnetic model Id, or ""


@dataclass
class Model:
    header: list = field(default_factory=list)
    elements: list = field(default_factory=list)     # (id, refstate, mass, H298, S298)
    species: list = field(default_factory=list)      # (id, stoichiometry)
    functions: list = field(default_factory=list)    # (id, Ranged)
    phases: list = field(default_factory=list)       # Phase, in source order
    params: list = field(default_factory=list)       # (Id, Ranged), in source order
    # MQMQA structure per phase: zeta and MQSTOI per pair, Z rows per quadruplet
    zeta: dict = field(default_factory=dict)         # (phase, cat, an) -> str
    stoi: dict = field(default_factory=dict)         # (phase, cat, an) -> str
    mqz: dict = field(default_factory=dict)          # (phase, A, B, X, Y) -> [4 str]


# ----------------------------------------------------------------------------- uTDB in
def _statements(text):
    header, body = [], []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("$"):
            if not body:
                header.append(s[1:].strip())
            continue
        body.append(line)
    return header, [" ".join(s.split()) for s in " ".join(body).split("!") if s.strip()]


def _expr(s):
    return "".join(s.split())


def _ranged(rest, raw=False):
    """'<lowT> <expr>; <hiT> Y <expr>; <hiT> N [ref]' -> Ranged."""
    low, _, tail = rest.strip().partition(" ")
    segs = tail.split(";")
    pieces, expr = [], segs[0]
    for seg in segs[1:]:
        tok = seg.split(None, 2)
        hi, flag = tok[0], tok[1].upper() if len(tok) > 1 else "N"
        pieces.append((" ".join(expr.split()) if raw else _expr(expr), hi))
        if flag == "N":
            return Ranged(low, pieces, tok[2].strip() if len(tok) > 2 else "")
        expr = tok[2] if len(tok) > 2 else ""
    raise ConversionError(f"unterminated expression: {rest[:60]}")


def _constant(rest):
    """'<lowT> <values>; <hiT> N' -> the values text, spaces kept."""
    r = _ranged(rest, raw=True)
    if len(r.pieces) != 1:
        raise ConversionError(f"expected one range: {rest[:60]}")
    return r.pieces[0][0]


def read_utdb(text):
    header, stmts = _statements(text)
    m = Model(header=header)
    types = {}           # type code char -> (phase, afm, p)
    phase_codes = {}
    for st in stmts:
        kw, _, rest = st.partition(" ")
        kw = kw.upper()
        if kw == "ELEMENT":
            m.elements.append(tuple(rest.split()[:5]))
        elif kw == "SPECIES":
            sid, stoich = rest.split()[:2]
            m.species.append((sid, stoich))
        elif kw == "FUNCTION":
            name, _, r = rest.partition(" ")
            m.functions.append((name, _ranged(r)))
        elif kw == "TYPE_DEFINITION":
            tok = rest.split()
            if tok[1].upper() == "SEQ":
                continue
            if tok[1:3] == ["GES", "A_P_D"] and len(tok) >= 7 and tok[4].upper() == "MAGNETIC":
                key = (tok[5], tok[6])
                if key not in MAGNETIC_IDS:
                    raise ConversionError(f"magnetic model with AFM {tok[5]} and p {tok[6]} has "
                                          f"no XTDB model Id")
                types[tok[0]] = (tok[3], MAGNETIC_IDS[key])
                continue
            raise ConversionError(f"TYPE_DEFINITION not supported: {st}")
        elif kw == "PHASE":
            tok = rest.split()
            name, suffix = (tok[0].split(":") + [""])[:2]
            if suffix and suffix.upper() != "Q":
                raise ConversionError(f"phase {tok[0]}: only :Q (MQMQA) phases are converted")
            n = int(tok[2])
            m.phases.append(Phase(name, suffix.upper() == "Q", tok[3:3 + n]))
            phase_codes[name] = tok[1]
        elif kw == "CONSTITUENT":
            token = rest.split()[0]
            name = token.split(":")[0]
            lists = rest[len(token):]
            subl = [[c.strip().rstrip("%") for c in part.split(",") if c.strip()]
                    for part in lists.split(":") if part.strip()]
            _phase(m, name).constituents = subl
        elif kw == "PARAMETER":
            _parameter(m, rest)
        elif kw in _IGNORED:
            continue
        else:
            raise ConversionError(f"statement not supported: {kw}")
    for code, (pname, model) in types.items():
        ph = _phase(m, pname)
        if code not in phase_codes.get(pname, ""):
            raise ConversionError(f"magnetic TYPE_DEFINITION {code} names {pname}, whose "
                                  f"PHASE does not carry it")
        ph.magnetic = model
    for ph in m.phases:
        if len(ph.constituents) != len(ph.mult):
            raise ConversionError(f"phase {ph.name}: CONSTITUENT does not match PHASE")
    return m


def _phase(m, name):
    for ph in m.phases:
        if ph.name.upper() == name.upper():
            return ph
    raise ConversionError(f"no PHASE {name}")


_PID = re.compile(r"^(\w+)\(([^)]*)\)\s*(.*)$")


def _parameter(m, rest):
    mt = _PID.match(rest)
    if not mt:
        raise ConversionError(f"cannot read PARAMETER {rest[:60]}")
    kind, inside, tail = mt.group(1).upper(), mt.group(2).replace(" ", ""), mt.group(3)
    phase, _, cons = inside.partition(",")
    if kind in ("MQZETA", "MQSTOI"):
        cat, an = cons.split(":")
        (m.zeta if kind == "MQZETA" else m.stoi)[(phase, cat, an)] = _constant(tail)
        return
    if kind == "MQZ":
        cats, ans = cons.split(":")
        a, b = cats.split(",")
        x, y = ans.split(",")
        m.mqz[(phase, a, b, x, y)] = _constant(tail).split()
        return
    if kind == "L":
        kind = "G"
    m.params.append((f"{kind}({inside})", _ranged(tail)))


# ---------------------------------------------------------------------------- XTDB out
def _quad_species(m, ph):
    """Species for the quadruplets of an MQMQA phase, as the XTDB documentation lists them."""
    out = []
    for (pn, a, b, x, y), z in m.mqz.items():
        if pn.upper() != ph.name.upper():
            continue
        if len(z) != 4:
            raise ConversionError(f"MQZ {a},{b}:{x},{y} needs four coordination numbers")
        cats = [a] if a == b else [a, b]
        ans = [x] if x == y else [x, y]
        if (a == b and z[0] != z[1]) or (x == y and z[2] != z[3]):
            raise ConversionError(f"MQZ {a},{b}:{x},{y}: unequal numbers on a repeated ion "
                                  f"have no XTDB form")
        nums = ([z[0]] if a == b else z[:2]) + ([z[2]] if x == y else z[2:])
        sid = "".join(cats) + "/" + "".join(ans)
        attrs = {"MQMQA": ",".join(cats) + "/" + ",".join(ans) + " " + " ".join(nums)}
        if a == b and x == y:
            key = (pn, a, x)
            if key not in m.zeta or key not in m.stoi:
                raise ConversionError(f"pair {a}:{x} of {ph.name} needs MQZETA and MQSTOI")
            attrs["MQMQA"] += " " + m.zeta[key]
            attrs["MQSTOI"] = m.stoi[key]
        out.append((sid, attrs))
    pairs = {(a, x) for (pn, a, b, x, y) in m.mqz if pn.upper() == ph.name.upper()
             and a == b and x == y}
    for (pn, a, x) in set(m.zeta) | set(m.stoi):
        if pn.upper() == ph.name.upper() and (a, x) not in pairs:
            raise ConversionError(f"pair {a}:{x} of {ph.name} has no MQZ row")
    return out


def _xml_ranged(tag, ident, r):
    first, hi = r.pieces[0]
    bib = f" Bibref={quoteattr(r.ref)}" if r.ref else ""
    head = f'<{tag} Id={quoteattr(ident)} LowT="{r.low}" Expr="{first};" HighT="{hi}"{bib}'
    if len(r.pieces) == 1:
        return [head + " />"]
    return [head + " >"] + [f'  <Trange Expr="{e};" HighT="{h}" />' for e, h in r.pieces[1:]] \
        + [f"</{tag}>"]


def _comment(lines):
    return [ln.replace("--", "- -") for ln in lines]


def write_xtdb(m, source_name="", version=""):
    special = [e[0] for e in m.elements if e[0] in ("VA", "/-")]
    out = [f'<XTDB version="{XTDB_VERSION}">',
           "<!-- " + f"Converted to XTDB by the Hephaestus{(' ' + version) if version else ''} "
           f"uTDB converter{(' from ' + source_name) if source_name else ''}.",
           "     Converting a database does not change its license; the license of the source "
           "data applies."]
    if any(ph.mqmqa for ph in m.phases):
        out.append("     MQMQA phases are written in the form proposed in Hephaestus "
                   "docs/XTDB_MQMQA_PROPOSAL.md;")
        out.append("     the XTDB documentation defines only their quadruplets, and no other "
                   "software reads them yet.")
    if m.header:
        out.append("     Source header:")
        out += ["       " + h for h in _comment(m.header)]
    out.append("-->")
    if special:
        out.append(f'<Defaults Elements="{" ".join(special)}" />')
    for el in m.elements:
        if el[0] in special:
            continue
        out.append(f'<Element Id={quoteattr(el[0])} Refstate={quoteattr(el[1])} Mass="{el[2]}" '
                   f'H298="{el[3]}" S298="{el[4]}" />')
    for sid, stoich in m.species:
        out.append(f'<Species Id={quoteattr(sid)} Stoichiometry={quoteattr(stoich)} />')
    for ph in m.phases:
        if ph.mqmqa:
            for sid, attrs in _quad_species(m, ph):
                extra = "".join(f" {k}={quoteattr(v)}" for k, v in attrs.items())
                out.append(f'<Species Id={quoteattr(sid)}{extra} />')
    if not any(f[0].upper() == "R" for f in m.functions):
        out.append(f'<TPfun Id="R" Expr="{TDB_R};" />')
    for name, r in m.functions:
        out += _xml_ranged("TPfun", name, _unhash(r))
    for ph in m.phases:
        conf = "MQMQA" if ph.mqmqa else "CEF"
        state = ' State="L"' if ph.mqmqa else ""
        out.append(f'<Phase Id={quoteattr(ph.name)} Configuration="{conf}"{state} >')
        out.append(f'  <Sublattices NumberOf="{len(ph.mult)}" Multiplicities="{" ".join(ph.mult)}" >')
        for i, subl in enumerate(ph.constituents):
            out.append(f'    <Constituents Sublattice="{i + 1}" List={quoteattr(" ".join(subl))} />')
        out.append("  </Sublattices>")
        if ph.magnetic:
            out.append(f'  <AmendPhase Models="{ph.magnetic}" />')
        out.append("</Phase>")
    for ident, r in m.params:
        out += _xml_ranged("Parameter", ident, _unhash(r))
    out.append("</XTDB>")
    return "\n".join(out) + "\n"


def _unhash(r):
    return Ranged(r.low, [(e.replace("#", ""), h) for e, h in r.pieces], r.ref)


def utdb_to_xtdb(text, source_name="", version=""):
    """uTDB (or plain TDB) text -> XTDB text."""
    return write_xtdb(read_utdb(text), source_name, version)


# ----------------------------------------------------------------------------- XTDB in
def read_xtdb(text):
    root = ET.fromstring(text)
    m = Model()
    defaults = root.find("Defaults")
    special = (defaults.get("Elements") or "").split() if defaults is not None else []
    for e in special:
        m.elements.append((e, "ELECTRON_GAS" if e == "/-" else "VACUUM", "0.0000E+00",
                           "0.0000E+00", "0.0000E+00"))
    for e in root.findall("Element"):
        m.elements.append((e.get("Id"), e.get("Refstate"), e.get("Mass"), e.get("H298"),
                           e.get("S298")))
    quads = []
    for s in root.findall("Species"):
        if s.get("MQMQA"):
            quads.append(s)
        else:
            m.species.append((s.get("Id"), s.get("Stoichiometry")))
    for f in root.findall("TPfun"):
        m.functions.append((f.get("Id"), _xml_read_ranged(f)))
    for p in root.findall("Phase"):
        conf = p.get("Configuration", "CEF").upper()
        if conf not in ("CEF", "MQMQA"):
            raise ConversionError(f"phase {p.get('Id')}: Configuration {conf} not supported")
        sub = p.find("Sublattices")
        mult = sub.get("Multiplicities").split()
        cons = [None] * len(mult)
        for c in sub.findall("Constituents"):
            cons[int(c.get("Sublattice")) - 1] = c.get("List").split()
        ph = Phase(p.get("Id"), conf == "MQMQA", mult, cons)
        amend = p.find("AmendPhase")
        if amend is not None:
            models = (amend.get("Models") or "").split()
            mag = [x for x in models if x in MAGNETIC_TDB]
            other = [x for x in models if x not in MAGNETIC_TDB]
            if other or len(amend):
                raise ConversionError(f"phase {ph.name}: AmendPhase {other} not supported")
            ph.magnetic = mag[0] if mag else ""
        m.phases.append(ph)
    mq_phases = [ph for ph in m.phases if ph.mqmqa]
    for s in quads:
        _read_quad(m, mq_phases, s)
    for p in root.findall("Parameter"):
        m.params.append((p.get("Id"), _xml_read_ranged(p)))
    return m


def _read_quad(m, mq_phases, s):
    ions, *nums = s.get("MQMQA").split()
    cats, ans = (part.split(",") for part in ions.split("/"))
    owner = [ph for ph in mq_phases if set(cats) <= set(ph.constituents[0])
             and set(ans) <= set(ph.constituents[1])]
    if len(owner) != 1:
        raise ConversionError(f"quadruplet {s.get('Id')} belongs to {len(owner)} MQMQA phases")
    pn = owner[0].name
    a, b = (cats * 2)[:2]
    x, y = (ans * 2)[:2]
    zc = nums[:len(cats)]
    za = nums[len(cats):len(cats) + len(ans)]
    z = (zc * 2)[:2] + (za * 2)[:2]
    m.mqz[(pn, a, b, x, y)] = z
    if len(cats) == 1 and len(ans) == 1:
        if len(nums) != 3 or not s.get("MQSTOI"):
            raise ConversionError(f"pair {s.get('Id')} needs Z_A Z_X zeta and MQSTOI")
        m.zeta[(pn, a, x)] = nums[2]
        m.stoi[(pn, a, x)] = s.get("MQSTOI")


def _xml_read_ranged(e):
    pieces = [(e.get("Expr").rstrip(";"), e.get("HighT"))]
    pieces += [(t.get("Expr").rstrip(";"), t.get("HighT")) for t in e.findall("Trange")]
    return Ranged(e.get("LowT", "298.15"), pieces, e.get("Bibref", ""))


# ---------------------------------------------------------------------------- uTDB out
def write_utdb(m, source_name=""):
    funcs = {f[0].upper() for f in m.functions}
    hashed = re.compile(r"\b(" + "|".join(sorted(map(re.escape, funcs), key=len, reverse=True))
                        + r")\b(?!#)", re.I) if funcs else None

    def ranged(r):
        out, low = [], r.low
        for i, (e, hi) in enumerate(r.pieces):
            if hashed:
                e = hashed.sub(lambda mt: mt.group(1) + "#", e)
            flag = "N" if i == len(r.pieces) - 1 else "Y"
            out.append(f"{e}; {hi} {flag}")
        tail = f" {r.ref}" if r.ref else ""
        return f"{low} " + " ".join(out) + tail + " !"

    out = [f"$ Converted to uTDB by the Hephaestus XTDB converter"
           f"{(' from ' + source_name) if source_name else ''}."]
    for el in m.elements:
        out.append(f" ELEMENT {el[0]} {el[1]} {el[2]} {el[3]} {el[4]} !")
    for sid, stoich in m.species:
        out.append(f" SPECIES {sid} {stoich} !")
    for name, r in m.functions:
        out.append(f" FUNCTION {name} {ranged(r)}")
    out.append(" TYPE_DEFINITION % SEQ * !")
    codes = iter("&'()*+,-./0123456789")
    for ph in m.phases:
        code = "%"
        if ph.magnetic:
            c = next(codes)
            afm, p = MAGNETIC_TDB[ph.magnetic]
            out.append(f" TYPE_DEFINITION {c} GES A_P_D {ph.name} MAGNETIC {afm} {p} !")
            code += c
        q = ":Q" if ph.mqmqa else ""
        out.append(f" PHASE {ph.name}{q} {code} {len(ph.mult)} {' '.join(ph.mult)} !")
        out.append(f" CONSTITUENT {ph.name}{q} : "
                   + " : ".join(",".join(s) for s in ph.constituents) + " : !")
        if ph.mqmqa:
            for (pn, a, x), zeta in m.zeta.items():
                if pn == ph.name:
                    out.append(f" PARAMETER MQZETA({pn},{a}:{x}) 298.15 {zeta}; 6000 N !")
                    out.append(f" PARAMETER MQSTOI({pn},{a}:{x}) 298.15 {m.stoi[(pn, a, x)]}; "
                               f"6000 N !")
            for (pn, a, b, x, y), z in m.mqz.items():
                if pn == ph.name:
                    out.append(f" PARAMETER MQZ({pn},{a},{b}:{x},{y}) 298.15 {' '.join(z)}; "
                               f"6000 N !")
    for ident, r in m.params:
        out.append(f" PARAMETER {ident} {ranged(r)}")
    return "\n".join(out) + "\n"


def xtdb_to_utdb(text, source_name=""):
    """XTDB text (with MQMQA in the proposed form) -> uTDB text."""
    return write_utdb(read_xtdb(text), source_name)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: python -m mqmqa.utdb_xtdb IN.utdb OUT.xtdb   (or IN.xtdb OUT.utdb)")
        return 2
    src, dst = Path(argv[0]), Path(argv[1])
    text = src.read_text(encoding="utf-8")
    if src.suffix.lower() == ".xtdb":
        result = xtdb_to_utdb(text, src.name)
    else:
        from ._abi import _lib
        from ._database import _s
        result = utdb_to_xtdb(text, src.name, _s(_lib.mqmqa_version()))
    dst.write_text(result, encoding="utf-8")
    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
