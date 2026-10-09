"""PHREEQC dissolution constants (25 C) for the anhydrous slag solids, from the same Gibbs energies
the Hephaestus databases ship.

Each solid's reaction is written in wateq4f master species (Ca+2, Mg+2, Al+3, H4SiO4, H+, H2O) and
its log K is built by an exchange cycle against minerals wateq4f already carries:

    P + w H2O = a portlandite + b/2 forsterite + c gibbsite + (d - b/2) quartz    (solids only)

so log K(P) = a logK(portlandite) + b/2 logK(forsterite) + c logK(gibbsite) + (d - b/2) logK(quartz)
+ log K(solid exchange). The aqueous ions cancel, and so does any element reference convention.
The anchors' 298 K data are read from the Robie & Hemingway (1995) extracts, water is CODATA.
Diopside and anorthite are in both wateq4f and our repo: reproducing them is the verifier.

Run in the calphad env:  python derive_logk.py   (writes slag_phases.dat and phreeqc_slag.dat)
"""
import csv
import importlib.util
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[1]
# R&H 1995 rows for the anchors, copied with table, page and row (rh1995_anchors.csv).
RH_ANCHORS = HERE / "rh1995_anchors.csv"
PHREEQC_DB = Path(importlib.util.find_spec("phreeqpython").origin).parent / "database"
PHREEQC_DAT = PHREEQC_DB / "phreeqc.dat"
WATEQ = PHREEQC_DB / "wateq4f_PWN.dat"
T = 298.15
RTLN10 = 8.314462618 * T * math.log(10)

# CODATA 1989 (Cox, Wagman & Medvedev), H2O(l): checked below against R&H lime + portlandite
H2O = dict(dHf=-285830.0, S=69.95)


def _load(name, rel):
    s = importlib.util.spec_from_file_location(name, DATA / rel)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def rh(phase_key, table):
    """(dHf J, S J/K) for one phase from a Robie & Hemingway extract (no retyping)."""
    out = {}
    for r in csv.DictReader(open(RH_ANCHORS, encoding="utf-8")):
        if r["source_table"] != table:
            continue
        if phase_key in (r.get("phase", "") + " " + r.get("composition", "")).lower():
            scale = 1000.0 if r["unit"].startswith("kJ") else 1.0
            out[r["quantity"]] = float(r["value"]) * scale
    return out["formation_enthalpy"], out["standard_entropy"], out.get("gibbs_energy")


OXH = "oxides_hydroxides"
SIL = "silicates"
HYD = "hydroxide_summary"
ANCHOR = {"Portlandite": rh("portlandite", OXH), "Forsterite": rh("forsterite", SIL),
          "Gibbsite": rh("gibbsite", HYD), "Quartz": rh("quartz", SIL)}
G_ANCHOR = {k: dh - T * s for k, (dh, s, _) in ANCHOR.items()}
G_H2O = H2O["dHf"] - T * H2O["S"]


def wateq_logk():
    """log_k of every PHASES entry in wateq4f, and the Al(OH)4- association constant."""
    txt = WATEQ.read_text(errors="replace")
    ph = txt[txt.index("\nPHASES"):]
    out = {}
    for m in re.finditer(r"^(\w[\w()]*)\s+\d*\s*\n\s+(.+?)\n\s+log_k\s+(-?[\d.]+)", ph, re.M):
        out[m.group(1)] = float(m.group(3))
    sp = txt[txt.index("SOLUTION_SPECIES"):txt.index("\nPHASES")]
    m = re.search(r"Al\+3 \+ 4H2O = Al\(OH\)4- \+ 4H\+\s*\n\s+log_k\s+(-?[\d.]+)", sp)
    return out, float(m.group(1))


# This IPhreeqc build rejects a PHASES entry with only an -analytic expression and no log_k; the
# stock wateq4f has several. Same repair as greigite-porewater-redox/code/aqueous/build_ehph_diagram.py:
# insert log_k(25 C) from the analytic expression.
def _analytic_logk(text, T=298.15):
    nums = re.findall(r"-?\d+\.?\d*[eE]?[-+]?\d+|-?\d+\.?\d*", text)
    A = [float(c) for c in nums[:5]] + [0.0] * (5 - len(nums[:5]))
    return A[0] + A[1] * T + A[2] / T + A[3] * math.log10(T) + A[4] / T ** 2


def _inject_logk(txt):
    def is_header(line):
        return (bool(line) and not line[0].isspace() and line.strip() and "=" not in line
                and not line.strip().startswith("-"))
    out, entry = [], []

    def flush():
        if not entry:
            return
        has_logk = any(re.search(r"log_k", x, re.I) for x in entry)
        ana = next((x for x in entry if re.match(r"\s*-analytic", x)), None)
        if any("=" in x for x in entry) and not has_logk and ana:
            for x in entry:
                out.append(x)
                if "=" in x and not x.strip().startswith("-"):
                    out.append(f"        log_k   {_analytic_logk(ana):.4f}")
        else:
            out.extend(entry)
    for line in txt.splitlines():
        if is_header(line):
            flush()
            entry = [line]
        else:
            entry.append(line)
    flush()
    return "\n".join(out)


LOGK, LOGK_ALOH4 = wateq_logk()


# --- our solids at 298.15 K, from the modules the builders read ----------------------------
_sil = _load("wet_sil", "cao-sio2/silicates.py")
_olv = _load("wet_olv", "olivine/endmembers.py")
_cpx = _load("wet_cpx", "clinopyroxene/endmembers.py")
_spl = _load("wet_spl", "spinel/endmembers.py")
_caal = _load("wet_caal", "cao-al2o3/build_dat.py")
_cas = _load("wet_cas", "cao-al2o3-sio2/build_dat.py")


def _g_dict(cf):
    return cf["dHf"] - T * cf["S298"]          # the builders' G at 298.15 K by construction


def _g_cas(name):
    entry = _cas.SOLIDS[name][3]
    return _sil.gibbs_cf(entry[0][1], T) if isinstance(entry, list) else _g_dict(entry)


# name: (Ca, Mg, Al, Si, H, G at 298.15 J/mol), PHREEQC formula
SOLIDS = {
    "Lime": ((1, 0, 0, 0, 0), _g_dict(_caal.SOLIDS["CaO_solid"][2]), "CaO"),
    "Corundum": ((0, 0, 2, 0, 0), _g_dict(_caal.SOLIDS["Al2O3_corundum"][2]), "Al2O3"),
    # the aluminates on their measured values: the CaO-Al2O3 assessment shifts them to fit the
    # melting data, a high-temperature compromise this 298 K database does not take
    "CaAl2O4": ((1, 0, 2, 0, 0), _g_dict(_caal.MEASURED["CaAl2O4"]), "CaAl2O4"),
    "CaAl4O7": ((1, 0, 4, 0, 0), _g_dict(_caal.MEASURED["CaAl4O7"]), "CaAl4O7"),
    "Ca3Al2O6": ((3, 0, 2, 0, 0), _g_dict(_caal.MEASURED["Ca3Al2O6"]), "Ca3Al2O6"),
    "Hibonite": ((1, 0, 12, 0, 0), _g_dict(_caal.MEASURED["CaAl12O19"]), "CaAl12O19"),
    "Wollastonite": ((1, 0, 0, 1, 0), _sil.gibbs("CaSiO3", T), "CaSiO3"),
    "Larnite": ((2, 0, 0, 1, 0), _sil.gibbs("Ca2SiO4", T), "Ca2SiO4"),
    "Hatrurite": ((3, 0, 0, 1, 0), _sil.gibbs("Ca3SiO5", T), "Ca3SiO5"),
    "Rankinite": ((3, 0, 0, 2, 0), _sil.gibbs("Ca3Si2O7", T), "Ca3Si2O7"),
    "Forsterite_H": ((0, 2, 0, 1, 0), _olv.gibbs("forsterite", T), "Mg2SiO4"),
    "Enstatite_H": ((0, 1, 0, 1, 0), _olv.gibbs("enstatite", T), "MgSiO3"),
    "Diopside_H": ((1, 1, 0, 2, 0), _cpx.gibbs("diopside", T), "CaMgSi2O6"),
    "Spinel": ((0, 1, 2, 0, 0), _spl.gibbs("spinel", T), "MgAl2O4"),
    "Gehlenite": ((2, 0, 2, 1, 0), _g_cas("Ca2Al2SiO7"), "Ca2Al2SiO7"),
    "Anorthite_H": ((1, 0, 2, 2, 0), _g_cas("CaAl2Si2O8"), "CaAl2Si2O8"),
}


def _h(gfun, step=0.5):
    """Enthalpy at 298.15 K from a Gibbs function of T, H = G - T dG/dT."""
    return gfun(T) - T * (gfun(T + step) - gfun(T - step)) / (2 * step)


def _h_cas(name):
    entry = _cas.SOLIDS[name][3]
    return _h(lambda t: _sil.gibbs_cf(entry[0][1], t)) if isinstance(entry, list) else entry["dHf"]


# enthalpy of formation at 298.15 K of each slag solid, from the same source as its G (for the
# coefficient dicts the 298 K enthalpy is dHf itself)
H298 = {
    "Lime": _caal.SOLIDS["CaO_solid"][2]["dHf"], "Corundum": _caal.SOLIDS["Al2O3_corundum"][2]["dHf"],
    "CaAl2O4": _caal.MEASURED["CaAl2O4"]["dHf"], "CaAl4O7": _caal.MEASURED["CaAl4O7"]["dHf"],
    "Ca3Al2O6": _caal.MEASURED["Ca3Al2O6"]["dHf"], "Hibonite": _caal.MEASURED["CaAl12O19"]["dHf"],
    "Wollastonite": _h(lambda t: _sil.gibbs("CaSiO3", t)), "Larnite": _h(lambda t: _sil.gibbs("Ca2SiO4", t)),
    "Hatrurite": _h(lambda t: _sil.gibbs("Ca3SiO5", t)), "Rankinite": _h(lambda t: _sil.gibbs("Ca3Si2O7", t)),
    "Forsterite_H": _h(lambda t: _olv.gibbs("forsterite", t)), "Enstatite_H": _h(lambda t: _olv.gibbs("enstatite", t)),
    "Diopside_H": _h(lambda t: _cpx.gibbs("diopside", t)), "Spinel": _h(lambda t: _spl.gibbs("spinel", t)),
    "Gehlenite": _h_cas("Ca2Al2SiO7"), "Anorthite_H": _h_cas("CaAl2Si2O8"),
}


def _delta_h(path, phase):
    """Reaction enthalpy (J) of a PHASES entry: its delta_h line, in kcal or kJ as written."""
    lines = path.read_text(errors="replace").splitlines()
    start = next(i for i, l in enumerate(lines) if re.match(re.escape(phase) + r"(\s|$)", l))
    for l in lines[start + 1:start + 6]:
        m = re.match(r"\s+-?delta_h\s+(-?[\d.]+)\s*(kcal|kJ)?", l)
        if m:
            return float(m.group(1)) * (4184.0 if m.group(2) == "kcal" else 1000.0)
    raise ValueError(f"no delta_h for {phase}")


def logk(comp, g):
    """log K for P + (2a+2b+3c) H+ = a Ca+2 + b Mg+2 + c Al+3 + d H4SiO4 + n H2O."""
    a, b, c, d, y = comp
    w = (2 * a + 3 * c - y) / 2.0                           # water consumed by the solid exchange
    dg = (a * G_ANCHOR["Portlandite"] + b / 2 * G_ANCHOR["Forsterite"] + c * G_GIBBSITE_C18
          + (d - b / 2) * G_ANCHOR["Quartz"] - g - w * G_H2O)
    return (a * LOGK["Portlandite"] + b / 2 * LOGK["Forsterite"] + c * LOGK_AL
            + (d - b / 2) * LOGK["Quartz"] - dg / RTLN10)


def slag_dh(name, comp):
    """Reaction enthalpy of the dissolution, J: the anchors' own plus the solid exchange, as for log K."""
    a, b, c, d, y = comp
    w = (2 * a + 3 * c - y) / 2.0
    h_ex = (a * ANCHOR["Portlandite"][0] + b / 2 * ANCHOR["Forsterite"][0] + c * float(_GIB["dfH_J"])
            + (d - b / 2) * ANCHOR["Quartz"][0] - H298[name] - w * H2O["dHf"])
    return a * DH["Portlandite"] + b / 2 * DH["Forsterite"] + c * DH_GIB_C18 + (d - b / 2) * DH["Quartz"] + h_ex


def reaction(formula, comp):
    a, b, c, d, y = comp
    n_h = 2 * a + 2 * b + 3 * c
    n_w = (y + n_h - 4 * d) / 2.0
    left = f"{formula} + {round(n_h, 8):g}H+" + (f" + {round(-n_w, 8):g}H2O" if n_w < 0 else "")
    right = [f"{round(k, 8):g}{s}" for k, s in ((a, "Ca+2"), (b, "Mg+2"), (c, "Al+3"), (d, "H4SiO4")) if k]
    if n_w > 0:
        right.append(f"{round(n_w, 8):g}H2O")
    return f"{left} = " + " + ".join(right)


# --- Cemdata18 hydrates (Lothenbach et al. 2019), values from cemdata18_dfG.csv -------------------
# Same exchange cycle, but against Cemdata18's own portlandite, gibbsite and quartz, so the hydrates
# keep their Cemdata18 stabilities relative to those three and land on this database's constants for
# them; the PSI/Nagra aqueous model under Cemdata18 cancels. Water: Cemdata18 Appendix B, p. 48.
C18_H2O = -237180.0
C18 = {r["name"]: r for r in csv.DictReader(open(HERE / "cemdata18_dfG.csv", encoding="ascii"))}
HYDRATES = ["C3AH6", "C3AS0.41H5.18", "C3AS0.84H4.32", "C4AH19", "C4AH13", "C2AH7.5", "CAH10",
            "Straetlingite", "Al(OH)3(mic)", "SiO2(am)_C18", "CSH_Tob", "CSH_Jen", "MSH_0.75", "MSH_1.5",
            "CSHQ_TobH", "CSHQ_TobD", "CSHQ_JenH", "CSHQ_JenD", "Gibbsite_C18"]
CLINKER_CHECK = {"Lime_C18": "Lime", "C3S_C18": "Hatrurite", "C2S_C18": "Larnite", "C3A_C18": "Ca3Al2O6",
                 "CA_C18": "CaAl2O4", "CA2_C18": "CaAl4O7"}


def _kw():
    """log Kw at 25 C from phreeqc.dat's own analytic expression (A1..A6)."""
    m = re.search(r"^H2O = OH- \+ H\+\s*\n\s+-analytic\s+([^\n]+)", PHREEQC_DAT.read_text(errors="replace"), re.M)
    a = [float(v) for v in m.group(1).split()] + [0.0] * 6
    return a[0] + a[1] * T + a[2] / T + a[3] * math.log10(T) + a[4] / T ** 2 + a[5] * T ** 2


def _analytic(species_line):
    """log K at 25 C of a phreeqc.dat SOLUTION_SPECIES entry, from its -analytic expression."""
    m = re.search(re.escape(species_line) + r"\s*\n(?:\s+-.*\n)*?\s+-analytic\s+([^\n]+)",
                  PHREEQC_DAT.read_text(errors="replace"))
    a = [float(v) for v in m.group(1).split()] + [0.0] * 6
    return a[0] + a[1] * T + a[2] / T + a[3] * math.log10(T) + a[4] / T ** 2 + a[5] * T ** 2


# Aluminium is anchored on Cemdata18's gibbsite, not phreeqc.dat's. phreeqc.dat's gibbsite (log K
# 8.11 with Al+3) and its Al(OH)4- constant make gibbsite 0.5 log units more soluble at high pH than
# Cemdata18's, and Wells, Clarke & McMurdie 1943 (validate_wells1943.py) side with Cemdata18. Its
# log KS0 (Al(OH)3 + OH- = Al(OH)4-) goes onto phreeqc.dat's Al+3 scale through phreeqc.dat's own
# Al(OH)4- and water constants, so the anchor is right where Al(OH)4- dominates (pH above about 9),
# which is where slag water lives; in acid solutions phreeqc.dat's own gibbsite is the better value.
_GIB = C18["Gibbsite_C18"]
LOGK_AL = float(_GIB["logKs0_table2"]) + _kw() - _analytic("Al+3 + 4 H2O = Al(OH)4- + 4 H+")
G_GIBBSITE_C18 = float(_GIB["dfH_J"]) - T * float(_GIB["S_JK"])     # same basis as the R&H anchors

# Reaction enthalpies of the anchors as the two databases give them, so every derived phase carries
# its own (van 't Hoff) temperature dependence. Cemdata18's gibbsite: phreeqc.dat's gibbsite value
# shifted by the difference between the two gibbsite formation enthalpies.
DH = {"Portlandite": _delta_h(WATEQ, "Portlandite"), "Forsterite": _delta_h(WATEQ, "Forsterite"),
      "Brucite": _delta_h(WATEQ, "Brucite"), "Quartz": _delta_h(PHREEQC_DAT, "Quartz"),
      "SiO2(a)": _delta_h(PHREEQC_DAT, "SiO2(a)")}
DH_GIB_C18 = _delta_h(PHREEQC_DAT, "Gibbsite") - (float(_GIB["dfH_J"]) - rh("gibbsite", HYD)[0])
C18_H2O_H = -285880.0                     # Cemdata18 Appendix B, p. 48

# The hydrates' silicon is anchored on amorphous silica (Cemdata18's SiO2(am) against phreeqc.dat's
# SiO2(a), both -2.71 at 25 C, the measured value), not on quartz: Cemdata18's quartz (-3.75) and
# phreeqc.dat's (-3.98) disagree, and anchoring on quartz put Cemdata18's amorphous silica at -2.95.
LOGK_SIAM = 0.0                            # set below from phreeqc.dat's analytic expression


def _phase_analytic(phase):
    """log K at 25 C of a phreeqc.dat PHASES entry from its -analytic expression."""
    lines = PHREEQC_DAT.read_text(errors="replace").splitlines()
    start = next(i for i, l in enumerate(lines) if re.match(re.escape(phase) + r"(\s|$)", l))
    for l in lines[start + 1:start + 6]:
        m = re.match(r"\s+-analytic\s+(.+)", l)
        if m:
            a = [float(v) for v in m.group(1).split()] + [0.0] * 6
            return a[0] + a[1] * T + a[2] / T + a[3] * math.log10(T) + a[4] / T ** 2 + a[5] * T ** 2
    raise ValueError(f"no -analytic for {phase}")


LOGK_SIAM = _phase_analytic("SiO2(a)")


def c18_comp(name):
    r = C18[name]
    # rounded to 4 decimals so every derived coefficient is a finite decimal and PHREEQC's balance
    # check passes exactly (the CSHQ endmembers carry 2/3, 5/6, 11/6)
    ca, al2o3, si, mg, h2o = (round(float(r[k]), 4) for k in ("CaO", "Al2O3", "SiO2", "MgO", "H2O"))
    return (ca, mg, 2 * al2o3, si, 2 * h2o)               # (Ca, Mg, Al, Si, H) atoms


def c18_formula(comp):
    ca, mg, al, si, h = comp
    o = ca + mg + 1.5 * al + 2 * si + h / 2
    return "".join(f"{el}{round(n, 8):g}" if n != 1 else el for el, n in
                   (("Ca", ca), ("Mg", mg), ("Al", al), ("Si", si), ("O", o), ("H", h)) if n)


def c18_logk(name, si_anchor="am"):
    """log K in this database's species. Mg phases: Cemdata18's Table 2 log KS0 converted directly
    (no Mg reference phase in Cemdata18 itself); everything else by the exchange cycle, silicon on
    amorphous silica (si_anchor="quartz" only for the clinker cross-check against our quartz-based
    solids)."""
    ca, mg, al, si, h = comp = c18_comp(name)
    if mg:
        n_oh = 2 * mg                                      # M-S-H: Mg+2 + SiO2 + OH- (+ H2O) in Table 2
        return float(C18[name]["logKs0_table2"]) - n_oh * _kw(), comp
    g = lambda n: float(C18[n]["dfG_J"])
    si_ph, si_k = ("SiO2(am)_C18", LOGK_SIAM) if si_anchor == "am" else ("Quartz_C18", LOGK["Quartz"])
    w = (2 * ca + 3 * al - h) / 2.0
    dg = ca * g("Portlandite_C18") + al * g("Gibbsite_C18") + si * g(si_ph) - g(name) - w * C18_H2O
    return (ca * LOGK["Portlandite"] + al * LOGK_AL + si * si_k - dg / RTLN10), comp


def c18_dh(name):
    """Reaction enthalpy, J, by the same cycle from Cemdata18's formation enthalpies; None for the
    M-S-H phases (no Mg reference in Cemdata18), which then keep a temperature-independent log K."""
    ca, mg, al, si, h = c18_comp(name)
    if mg:
        return None
    hf = lambda n: float(C18[n]["dfH_J"])
    w = (2 * ca + 3 * al - h) / 2.0
    h_ex = (ca * hf("Portlandite_C18") + al * hf("Gibbsite_C18") + si * hf("SiO2(am)_C18") - hf(name)
            - w * C18_H2O_H)
    return ca * DH["Portlandite"] + al * DH_GIB_C18 + si * DH["SiO2(a)"] + h_ex


def checks():
    rows = []
    # water: lime + H2O = portlandite on R&H (dHf, S) vs R&H dGf
    lime, port = rh("lime", OXH), rh("portlandite", OXH)
    dg_hs = (port[0] - T * port[1]) - (lime[0] - T * lime[1]) - G_H2O
    dg_rh = port[2] - lime[2] - (-237140.0)
    rows.append(("CODATA water vs R&H dGf (lime + H2O = portlandite)", dg_hs / 1000, dg_rh / 1000, "kJ"))
    # our forsterite vs R&H forsterite (the anchor)
    rows.append(("our forsterite G vs R&H", SOLIDS["Forsterite_H"][1] / 1000, G_ANCHOR["Forsterite"] / 1000, "kJ"))
    rows.append(("our lime G vs R&H", SOLIDS["Lime"][1] / 1000, lime[0] / 1000 - T * lime[1] / 1000, "kJ"))
    # wateq4f phases we did not anchor on
    rows.append(("Diopside log K, ours vs wateq4f", logk(*SOLIDS["Diopside_H"][:2]), LOGK["Diopside"], ""))
    an_wateq_al3 = LOGK["Anorthite"] - 2 * LOGK_ALOH4        # Al(OH)4- form -> Al+3 form
    rows.append(("Anorthite log K, ours vs wateq4f", logk(*SOLIDS["Anorthite_H"][:2]), an_wateq_al3, ""))
    return rows


def main():
    print("checks (ours / reference):")
    for name, ours, ref, unit in checks():
        print(f"  {name:52s} {ours:10.3f} / {ref:10.3f}  diff {ours - ref:+.3f} {unit}")
    lines = ["# Hephaestus slag solids for wateq4f, log K at 25 C from data/wet-slag/aqueous/derive_logk.py",
             "PHASES"]
    print("\nlog K at 25 C:")
    for name, (comp, g, formula) in SOLIDS.items():
        k = logk(comp, g)
        rx = reaction(formula, comp)
        dh = slag_dh(name, comp)
        print(f"  {name:13s} {k:9.3f}  dH {dh / 1000:8.1f} kJ   {rx}")
        lines += [name, f"    {rx}", f"    log_k     {k:.3f}", f"    -delta_h  {dh / 1000:.3f} kJ"]
    print("\nCemdata18 clinker phases vs our solids (log K, same anchors):")
    for c18, ours in CLINKER_CHECK.items():
        k18, _ = c18_logk(c18, si_anchor="quartz")
        k = logk(*SOLIDS[ours][:2])
        print(f"  {c18:10s} vs {ours:10s} {k18:9.3f} / {k:9.3f}  diff {k18 - k:+.3f}")
    print("\nCemdata18 hydrates, log K at 25 C:")
    for name in HYDRATES:
        k, comp = c18_logk(name)
        safe = name.replace(".", "_") if name == "Gibbsite_C18" else name.replace(".", "_").replace("_C18", "")
        rx = reaction(c18_formula(comp), comp)
        dh = c18_dh(name)
        print(f"  {safe:15s} {k:9.3f}  dH {'   n/a  ' if dh is None else f'{dh / 1000:8.1f}'} kJ   {rx}")
        lines += [safe, f"    {rx}", f"    log_k     {k:.3f}"] + ([] if dh is None else [f"    -delta_h  {dh / 1000:.3f} kJ"])
    (HERE / "slag_phases.dat").write_text("\n".join(lines) + "\nEND\n", encoding="ascii")
    # phreeqc.dat loads clean in this IPhreeqc build (wateq4f does not: a few gas and redox-tracer
    # entries). It shares gibbsite, quartz and anorthite with wateq4f to the digit, so the three
    # anchors it lacks are copied in verbatim from wateq4f, then our phases, inside its PHASES block.
    wq = WATEQ.read_text(errors="replace")
    extra = []
    for name in ("Portlandite", "Forsterite", "Brucite"):
        m = re.search(rf"^{name}\s+\d*\s*\n\s+(.+?=.+?)\s*\n\s+log_k\s+(-?[\d.]+)", wq, re.M)
        extra += [name, f"    {m.group(1)}", f"    log_k     {m.group(2)}", f"    -delta_h  {DH[name] / 1000:.3f} kJ"]
    txt = PHREEQC_DAT.read_text(errors="replace")
    m = re.search(r"^PHASES\s*\n", txt, re.M)
    txt = txt[:m.end()] + "\n".join(extra + lines[2:]) + "\n" + txt[m.end():]
    (HERE / "phreeqc_slag.dat").write_text(txt, encoding="utf-8")
    print("\nwrote slag_phases.dat and phreeqc_slag.dat")


if __name__ == "__main__":
    main()
