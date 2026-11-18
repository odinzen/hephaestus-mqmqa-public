"""Read Thermochimica's daily test programs and split them into conditions and sealed reference values.

Writes conditions.json (no reference values) next to this folder's parent and expected.json into the
sealed folder given on the command line. Run with the Thermochimica checkout as the first argument.
"""
import json
import re
import sys
from pathlib import Path

TC = Path(sys.argv[1])
CONDITIONS_OUT = Path(sys.argv[2])
EXPECTED_OUT = Path(sys.argv[3])
TESTS = TC / "test" / "daily"
DATA = TC / "data"

SYMBOLS = (
    "H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr "
    "Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm "
    "Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No "
    "Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og"
).split()
MODEL_TYPES = {"IDMX", "RKMP", "RKMPM", "QKTO", "SUBL", "SUBLM", "SUBG", "SUBQ", "SUBI", "SUBM"}
NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[EeDd][-+]?\d+)?"

# Tests that only check how bad input is refused. Their database (CO.dat) exists, so they are kept.
INPUT_VALIDATION = {f"TestThermo{n:02d}" for n in range(3, 14)}


def fnum(s):
    return float(s.replace("D", "E").replace("d", "e"))


def db_info(name):
    path = DATA / name
    if not path.exists():
        return None
    lines = path.read_text(errors="replace").splitlines()
    n_el = int(lines[1].split()[0])
    elements, i = [], 1
    while len(elements) < n_el:
        toks = lines[i].split()
        if toks and not re.fullmatch(NUM, toks[0]):
            elements += [t for t in toks if not re.fullmatch(NUM, t)]
        i += 1
    models = {}
    for ln in lines:
        t = ln.strip()
        if t in MODEL_TYPES:
            models[t] = models.get(t, 0) + 1
    return {"elements_in_file_order": elements[:n_el], "solution_models": dict(sorted(models.items()))}


def code_lines(text):
    """Executable lines with trailing comments split off; full-line comments dropped."""
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith("!"):
            continue
        code, _, comment = ln.partition("!")
        out.append((code.rstrip(), comment.strip()))
    return out


def header_text(text):
    head = re.split(r"(?mi)^\s*program\s", text)[0]
    brief, details, grab = "", [], False
    for ln in head.splitlines():
        s = ln.strip()
        if r"\brief" in s:
            brief = s.split(r"\brief", 1)[1].strip()
        if r"\details" in s:
            grab = True
            s = s.split(r"\details", 1)[1]
        elif grab and re.match(r"!-{5,}", s):
            break
        if grab:
            details.append(s.lstrip("!>").strip())
    return brief, " ".join(d for d in details if d)


def parse(path):
    text = path.read_text(errors="replace")
    name = path.stem
    brief, details = header_text(text)
    extra = []
    lines = code_lines(text)
    cond = {"temperature_unit": None, "pressure_unit": None, "mass_unit": None, "database": None,
            "temperature": None, "pressure": None, "element_amounts": {}, "all_elements_amount": None}
    named = {}
    calls = set()
    notes = []
    for code, comment in lines:
        c = code.strip()
        m = re.match(r"(?i)cInputUnit(Temperature|Pressure|Mass)\s*=\s*'([^']*)'", c)
        if m:
            cond[f"{m.group(1).lower()}_unit"] = m.group(2)
            continue
        m = re.match(r"(?i)cThermoFileName\s*=\s*DATA_DIRECTORY\s*//\s*'([^']*)'", c)
        if m:
            cond["database"] = m.group(1)
            continue
        m = re.match(rf"(?i)dTemperature\s*=\s*({NUM})\s*$", c)
        if m:
            cond["temperature"] = fnum(m.group(1))
            continue
        m = re.match(rf"(?i)dPressure\s*=\s*({NUM})\s*$", c)
        if m:
            cond["pressure"] = fnum(m.group(1))
            continue
        if re.match(r"(?i)dPressure\s*=\s*sqrt", c):
            notes.append("pressure is set to sqrt(-1), i.e. NaN")
            cond["pressure"] = "NaN"
            continue
        if re.match(r"(?i)dTemperature\s*=\s*dTemperature\s*\*\s*dTemperature", c):
            notes.append("temperature is squared after assignment (1E37**2, intended as infinite)")
            continue
        m = re.match(rf"(?i)dElementMass\((\d+)\)\s*=\s*({NUM})\s*$", c)
        if m:
            z = int(m.group(1))
            cond["element_amounts"][SYMBOLS[z - 1]] = fnum(m.group(2))
            continue
        m = re.match(rf"(?i)dElementMass\s*=\s*({NUM})\s*$", c)
        if m:
            cond["all_elements_amount"] = fnum(m.group(1))
            continue
        m = re.match(rf"(?i)(?:real\(8\),\s*parameter\s*::\s*)?([A-Za-z_]\w*(?:check\w*|Check\w*|Expected|Tolerance))\s*=\s*({NUM})\s*$", c)
        if m:
            named[m.group(1)] = {"value": fnum(m.group(2)), "comment": comment or None}
            continue
        m = re.search(r"(?i)call\s+(HeatCapacity|ThermoDebug|PrintResults|ParseInput)\b", c)
        if m:
            calls.add(m.group(1))
    # Drop zero entries set by name only when an array-wide zero precedes them; keep explicit zeros
    # (they are what the test wrote).
    return name, text, brief, details, extra, cond, named, calls, notes, lines


QTY = [
    (r"dGibbsEnergySys", "integral_gibbs_energy", "J"),
    (r"dHeatCapacity(?!Check)", "heat_capacity", "J/K"),
    (r"dElementPotential\((\d+)\)\s*\*\s*\w+\s*\*\s*\w+", "element_chemical_potential", "J/mol"),
    (r"dMolFraction\((nSpeciesPhase\(j-1\)\s*\+\s*\d+|nSpeciesPhase\(j\)|j|\d+)\)", "mole_fraction", "-"),
    (r"dMolesPhase\(\w+(?:\s*\+\s*1\s*-\s*i)?\)", "phase_moles", "mol"),
    (r"dSiteFraction\(i,j,l\)", "site_fraction", "-"),
    (r"\bT\b", "magnetic_critical_temperature", "K"),
    (r"\bB\b", "magnetic_moment", "-"),
    (r"dSlagAmount", "phase_moles", "mol"),
]


def checks_from(lines, named, system_elements=None):
    checks = []
    phase = species = constituent = None
    liquid_group = 0
    in_ionic = False
    for code, comment in lines:
        c = code.strip()
        m = re.search(r"cSolnPhaseName\(\w+\)\)?\s*==\s*'([^']+)'", c)
        if m:
            phase, species, constituent = m.group(1), None, None
            in_ionic = phase.upper().startswith("IONIC")
            liquid_group = 0
        m = re.search(r"cSpeciesName\(j\)\)\)\s*==\s*'([^']+)'", c)
        if m:
            if "nConPhases" in phase_ctx_hint(lines, code):
                phase, species = m.group(1), None
            else:
                species = m.group(1)
        m = re.search(r"cConstituentNameSUB\(i,j,l\)\)\)\s*==\s*'([^']+)'", c)
        if m:
            constituent = m.group(1)
        if in_ionic and re.match(r"do j = 1, 2", c):
            liquid_group += 1
        hits = []
        for pat, qty, unit in QTY:
            for m in re.finditer(rf"\(*\s*({pat})\s*-\s*\(?\s*({NUM}|[A-Za-z_]\w*)\s*\)?", c):
                hits.append((m.start(), m, qty, unit))
        for _, m, qty, unit in sorted(hits, key=lambda h: h[0]):
            target = m.group(m.lastindex)
            if re.fullmatch(NUM, target):
                value, ref_name = fnum(target), None
            elif target in named:
                value, ref_name = named[target]["value"], target
            else:
                continue
            entry = {"quantity": qty, "unit": unit, "value": value}
            if ref_name:
                entry["variable"] = ref_name
                if named[ref_name]["comment"]:
                    entry["test_comment"] = named[ref_name]["comment"]
            expr = m.group(1)
            if qty == "element_chemical_potential":
                entry["element_index_in_system"] = int(re.search(r"\((\d+)\)", expr).group(1))
                if system_elements:
                    entry["element"] = system_elements[entry["element_index_in_system"] - 1]
            if qty == "mole_fraction":
                idx = re.search(r"dMolFraction\((.*)\)$", expr).group(1)
                if idx == "j":
                    entry.update(phase=phase, species=species)
                elif re.fullmatch(r"\d+", idx):
                    entry["species_index_in_system"] = int(idx)
                elif idx == "nSpeciesPhase(j)":
                    entry.update(phase=phase, species_position_in_phase="last")
                else:
                    entry.update(phase=phase, species_position_in_phase=int(re.search(r"\+\s*(\d+)", idx).group(1)))
            if qty == "phase_moles":
                entry["phase"] = "SlagBsoln" if expr == "dSlagAmount" else phase
            if qty == "site_fraction":
                entry.update(phase=phase, constituent=constituent, liquid_instance=liquid_group)
            if qty.startswith("magnetic"):
                entry["phase"] = phase
            checks.append(entry)
    return checks


def phase_ctx_hint(lines, code):
    # TestThermo63 compares a pure condensed phase name inside a loop over nConPhases.
    idx = [c for c, _ in lines].index(code)
    window = " ".join(c for c, _ in lines[max(0, idx - 3):idx])
    return window


def tolerance_for(lines, named):
    if "dGibbsRelativeTolerance" in named:
        return {"gibbs_relative": named["dGibbsRelativeTolerance"]["value"],
                "phase_moles_absolute": named["dSlagAmountTolerance"]["value"]}
    tols = {m for c, _ in lines for m in re.findall(r"<\s*(1D-\d+)", c)}
    return {"relative": sorted(fnum(t) for t in tols)}


def source_note(details):
    note = "the test program does not say where its reference values come from"
    if "pulled from the following article" in details:
        note += "; it cites the paper its data file was taken from, which is the source of the database, not of the values"
    if "tutorial manual" in details:
        note += "; it says the case is consistent with the test in Thermochimica's tutorial manual"
    return note


def main():
    files = sorted(TESTS.glob("*.F90"))
    dbs = {}
    conditions, expected, skipped = [], [], []
    for f in files:
        name, text, brief, details, extra, cond, named, calls, notes, lines = parse(f)
        if name.startswith("TestMSTDB"):
            skipped.append({"test": name, "database": cond["database"],
                            "reason": "MSTDB test; MSTDB database not shipped in data/"})
            continue
        if name == "parserTest":
            skipped.append({"test": name, "database": "C-O.dat (via inputs/trial-input.ti)",
                            "reason": "database C-O.dat not in data/; timing demo with no checks"})
            continue
        if cond["database"] is None or not (DATA / cond["database"]).exists():
            skipped.append({"test": name, "database": cond["database"],
                            "reason": "database deliberately missing (input-validation test of a missing data file)"})
            continue
        db = cond["database"]
        if db not in dbs:
            dbs[db] = db_info(db)
        category = "equilibrium"
        if name in INPUT_VALIDATION:
            category = "input_validation"
        elif name == "TestThermo14":
            category = "parse_only"
        elif name == "TestSUBQNonuniformZeta":
            category = "equilibrium_modified_data"
            notes.append("after parsing, the SUBQ phase SlagBsoln has its five species zeta values replaced "
                         "in memory by 1.8 + 0.15*i (i = 1..5); the shipped FeTiVO.dat is not changed, so the "
                         "condition is not reproducible from the data file alone (same state as TestThermo57 otherwise)")
        present = {el for el, amt in cond["element_amounts"].items() if amt > 0}
        system_elements = [el for el in dbs[db]["elements_in_file_order"] if el in present]
        checks = checks_from(lines, named, system_elements) if category not in ("input_validation", "parse_only") else []
        quantities = sorted({c["quantity"] for c in checks})
        if "HeatCapacity" in calls and "heat_capacity" not in quantities:
            quantities.append("heat_capacity")
        if name == "TestThermo64":
            quantities.append("phase_present:BCC_A2")
        described = []
        for c in checks:
            d = {k: v for k, v in c.items() if k not in ("value", "test_comment", "variable")}
            described.append(d)
        for c in checks:
            if c["quantity"] == "element_chemical_potential":
                tc = c.get("test_comment")
                if tc and tc.strip() != c.get("element"):
                    notes.append(f"chemical potential index {c['element_index_in_system']} is {c.get('element')} by the "
                                 f"database element order, but the test's comment names {tc.strip()}")
        if any(c["quantity"].startswith("magnetic") for c in checks):
            notes.append("magnetic checks are Thermochimica's CompMagneticTemperatureMoment output for the phase; "
                         "for FCC_A1 both are multiplied by minus the first species' magnetic structure factor")
        if any("species_index_in_system" in c for c in checks):
            notes.append("mole fractions indexed by Thermochimica's internal system species index; the species "
                         "name is not given in the test")
        info_code = None
        m = re.search(r"if \(INFOThermo == (\d+)\) then", text)
        if category == "input_validation" and m:
            info_code = int(m.group(1))
        if category == "parse_only":
            described = [{"quantity": "data_file_parses"}]
        if category == "input_validation":
            described = [{"quantity": "input_refused_with_error"}]
        # Header text mismatches with the code are worth flagging for whoever runs the condition.
        mism = re.search(r"(\d+)\s*K", brief)
        if mism and cond["temperature"] not in (None,) and isinstance(cond["temperature"], float) \
                and cond["temperature_unit"] == "K" and float(mism.group(1)) != cond["temperature"]:
            notes.append(f"header says {mism.group(1)} K but the code sets {cond['temperature']:g} K; "
                         "the code's temperature and composition are used")
        conditions.append({
            "id": name, "grid": "test", "category": category,
            "description": brief, "purpose": (details + " " + " ".join(extra)).strip(),
            "database": db,
            "temperature": cond["temperature"], "temperature_unit": cond["temperature_unit"],
            "pressure": cond["pressure"], "pressure_unit": cond["pressure_unit"],
            "element_amounts": cond["element_amounts"],
            "all_elements_amount": cond["all_elements_amount"],
            "mass_unit": cond["mass_unit"],
            "checks": described,
            "quantities_checked": quantities,
            "notes": notes,
        })
        check_start = text.find("! Check results")
        if check_start < 0:
            check_start = text.find("call Thermochimica")
        expected.append({
            "test": name, "database": db,
            "stated_source_of_reference_values": None,
            "source_note": source_note(details),
            "tolerance": tolerance_for(lines, named),
            "expected_INFOThermo": info_code if category == "input_validation" else 0,
            "checks": checks,
            "named_reference_values": named,
            "check_source_verbatim": text[check_start:] if category not in ("parse_only",) else "",
        })
    out = {
        "generated_from": "ORNL-CEES/thermochimica test/daily/*.F90 (commit 1c076b20f958be65bac750f00af2e59ef4f28d9e)",
        "files_read": "test/daily/*.F90, data/*.dat headers and model-type lines, inputs/*.ti, README.md; src/ not opened",
        "databases": dbs,
        "skipped_tests": skipped,
        "conditions": conditions,
    }
    CONDITIONS_OUT.write_text(json.dumps(out, indent=1))
    EXPECTED_OUT.write_text(json.dumps({
        "generated_from": out["generated_from"],
        "note": "reference values held in Thermochimica's daily test programs; sealed until the comparison step",
        "tests": expected}, indent=1))
    print(f"tests read {len(files)}; conditions {len(conditions)}; skipped {len(skipped)}")


if __name__ == "__main__":
    main()
