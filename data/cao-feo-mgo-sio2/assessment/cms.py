"""The CaO-MgO-SiO2 face of the combined quaternary as a ternary file the vis3d liquidus code
can read: the face of the liquid, and forsterite, enstatite, diopside and periclase as
line compounds. On the iron-free face each CEF solid is one endmember with nothing to mix,
so its line compound is exact; the Gibbs lines are copied from the combined file verbatim.
"""
import csv
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
D = HERE.parents[1]
COMBINED = HERE.parent / "CaO-FeO-MgO-SiO2-combined.dat"
TABLE = HERE / "bowen1914_liquidus.csv"

# (name in the combined file, name here); element order there is Ca, Fe, Mg, Si, O
SOLIDS = [("FORSTERITE", "FORSTERITE"), ("MG2SI2O6", "ENSTATITE"), ("DIOPSIDE", "DIOPSIDE"),
          ("MGO", "PERICLASE"), ("CRISTOBALITE", "CRISTOBALITE"), ("LIME", "LIME"),
          ("WOLLASTONITE", "WOLLASTONITE"), ("RANKINITE", "RANKINITE"), ("LARNITE", "LARNITE"),
          ("HATRURITE", "HATRURITE")]
FE = 1

# Bowen's primary phases as the phases of this file (tridymite is scored as cristobalite)
MODEL = {"pyroxene": {"DIOPSIDE", "ENSTATITE"}, "forsterite": {"FORSTERITE"},
         "silica": {"CRISTOBALITE"}}


def _load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def _gibbs_lines(lines, name):
    """The endmember or compound block `name`: its type/stoichiometry line and every Gibbs
    line under it (type 4 adds one line of extra terms per interval)."""
    i = next(k for k, l in enumerate(lines) if l.strip() == name)
    head = lines[i + 1].split()
    kind, n = int(head[0]), int(head[1])
    per = 2 if kind == 4 else 1
    body = lines[i + 2:i + 2 + n * per]
    if kind == 4:
        for extra in body[1::2]:
            k = int(extra.split()[0])
            assert len(extra.split()) == 1 + 2 * k, f"{name}: extra terms wrap onto more lines"
    return kind, n, [float(v) for v in head[2:]], body


def solid_blocks(lines):
    out = []
    for src, name in SOLIDS:
        kind, n, st, body = _gibbs_lines(lines, src)
        assert st[FE] == 0.0, src
        st = st[:FE] + st[FE + 1:]
        out += [f" {name}", f"   {kind}   {n}   " + "   ".join(f"{v:.6f}" for v in st)] + body
    return out


def build(path, excess):
    """Write the face with the liquid excess `excess` (quaternary indexing) to `path`."""
    bq = _load("cms_bq", HERE.parent / "build_dat.py")
    liq = bq.build(excess=excess, cations=["Ca", "Mg", "Si"]).splitlines()
    solids = solid_blocks(COMBINED.read_text().splitlines())
    head = [" System CaO-MgO-SiO2 face of the combined quaternary (assessment scratch file)",
            f"    4    1    3    {len(SOLIDS)}"] + liq[2:6]
    Path(path).write_text("\n".join(head + liq[6:] + solids) + "\n", encoding="ascii")
    return str(path)


# molar masses from the element weights the files carry
_M = {"Ca": 40.078, "Mg": 24.305, "Si": 28.085, "O": 15.9994}
_FORMULA = {"En": {"Mg": 1, "Si": 1, "O": 3}, "Di": {"Ca": 1, "Mg": 1, "Si": 2, "O": 6},
            "SiO2": {"Si": 1, "O": 2}, "Mg2SiO4": {"Mg": 2, "Si": 1, "O": 4}}


def cation_fractions(row):
    """(x_Ca, x_Mg, x_Si) of one Bowen mixture, from its weight percentages."""
    px = float(row["pyroxene_wt"]) / 100.0
    parts = [("En", px * float(row["En"]) / 100.0), ("Di", px * float(row["Di"]) / 100.0)]
    if row["added"] != "none":
        parts.append((row["added"], float(row["added_wt"]) / 100.0))
    n = {"Ca": 0.0, "Mg": 0.0, "Si": 0.0}
    for f, w in parts:
        mass = sum(_M[e] * k for e, k in _FORMULA[f].items())
        for e in n:
            n[e] += w / mass * _FORMULA[f].get(e, 0)
    tot = sum(n.values())
    return n["Ca"] / tot, n["Mg"] / tot, n["Si"] / tot


def rows():
    return list(csv.DictReader(open(TABLE, encoding="ascii")))


def allowed(primary):
    """The model phases that count as Bowen's primary phase; a boundary point takes either."""
    return set().union(*(MODEL[p] for p in primary.split("+")))
