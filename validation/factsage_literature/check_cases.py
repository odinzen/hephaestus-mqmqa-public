"""Check the case A and B files against the tables they were built from.

    python validation/factsage_literature/check_cases.py

Every species' Gibbs energy as the engine reads it from data/case*.dat is compared with G = H - TS
from the transcribed table in conditions.json, H and S integrated numerically (scipy quad) from
dfH298 and S298 at 298.15 K: a separate route from the term-by-term integration in build_cases.py.
"""
import json
import math
import sys
from pathlib import Path

from scipy.integrate import quad

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))
import mqmqa  # noqa: E402
from mqmqa import gem  # noqa: E402
from mqmqa._abi import _lib  # noqa: E402

POW = {"A": {"a": 0, "b": 1, "c": 2, "d": -2}, "B": {"a": 0, "b": 1, "c": -2, "d": 2, "e_T3": 3}}
TS = (298.15, 500.0, 800.0, 1000.0, 1043.0, 1100.0, 1300.0, 1500.0)


def g_table(rec, case, T):
    segs = sorted(rec["cp"], key=lambda s: s["T_range_K"][0])
    bounds = []
    lo = 298.15
    for i, s in enumerate(segs):
        hi = s["T_range_K"][1] if i + 1 < len(segs) else math.inf
        if i + 1 < len(segs) and segs[i + 1]["T_range_K"][0] < hi:
            hi = s["T_range_K"][1]
        bounds.append((lo, hi, s))
        lo = hi
    h = rec["dfH298_kJ"] * 1000 if case == "A" else rec["dfH298_J"]
    s0 = rec["S298_J_K"]
    for lo, hi, seg in bounds:
        top = min(T, hi)
        if top <= lo:
            break
        cp = lambda t, seg=seg: sum(v * t ** POW[case][k] for k, v in seg.items() if k in POW[case])
        h += quad(cp, lo, top, epsabs=1e-10, epsrel=1e-13)[0]
        s0 += quad(lambda t: cp(t) / t, lo, top, epsabs=1e-12, epsrel=1e-13)[0]
    return h - T * s0


def engine_stoich(db, name, T):
    for j in range(_lib.mqmqa_db_num_stoich(db._db)):
        from mqmqa._database import _s
        if _s(_lib.mqmqa_db_stoich_name(db._db, j)) == name.upper():
            return _lib.mqmqa_db_stoich_gibbs(db._db, j, T)
    raise KeyError(name)


def main():
    cases = {c["case"]: c for c in json.loads((HERE / "conditions.json").read_text(encoding="utf-8"))["cases"]}
    worst = 0.0
    rows = []
    for path in sorted((HERE / "data").glob("case*.dat")):
        case = path.name[4]
        data = cases[case]["parameters"]["end_members_and_compounds"]["data"]
        db = mqmqa.Database.read(str(path))
        sys_name = path.stem.split("_", 1)[1]
        a, b = sys_name.split("-")
        cat_a = a[:-2] if case == "A" else a[:-1]
        anion = "Cl" if case == "A" else "F"
        cat_b = b.replace(anion + "4", "").replace(anion + "3", "")
        names = {k.upper(): v for k, v in TABLE_NAME[case].items()}
        stoich = db_solids(path)
        for nm in stoich:
            for T in TS:
                ge, gt = engine_stoich(db, nm, T), g_table(data[names[nm]], case, T)
                worst = max(worst, abs(ge - gt))
                rows.append((path.name, nm, T, ge - gt))
        for ph in [p for p in db.phase_names if p.endswith("HEXAGONAL")]:
            k = db.phase_index(ph)
            for i, key in enumerate(("NaF(alpha)", f"{cat_b}F3(s)")):
                for T in TS:
                    y = [1.0, 0.0] if i == 0 else [0.0, 1.0]
                    ge, gt = db.cef_gibbs(k, y, T, per_mole_atoms=False), g_table(data[key], case, T)
                    worst = max(worst, abs(ge - gt))
                    rows.append((path.name, ph + ":" + key, T, ge - gt))
        # liquid end members, as the pure liquid at each end of the binary
        liq = [p for p in db.phase_names if p.endswith("LIQUID")][0]
        others = [p for p in db.phase_names if p != liq]
        for cat, n_an, key in ((cat_a, 1, f"{cat_a}{anion}(l)"),
                               (cat_b, 4 if case == "A" else 3, f"{cat_b}{anion}{4 if case == 'A' else 3}(l)")):
            for T in TS:
                r = gem.equilibrium(db, T, {cat: 1.0, anion: float(n_an)}, suspend=others + [s.upper() for s in stoich])
                ge = r.G * (1 + n_an)
                gt = g_table(data[key], case, T)
                worst = max(worst, abs(ge - gt))
                rows.append((path.name, key, T, ge - gt))
    for r in rows:
        if abs(r[3]) > 1e-6:
            print("MISMATCH", r)
    print(f"{len(rows)} species-temperature checks, largest |engine - table| {worst:.3e} J/mol")


TABLE_NAME = {
    "A": {"LiCl_cr": "LiCl(cr)", "NaCl_cr": "NaCl(cr)", "KCl_cr": "KCl(cr)", "ThCl4_alpha": "alpha-ThCl4(cr)",
          "ThCl4_beta": "beta-ThCl4(cr)", "Li4ThCl8": "Li4ThCl8(cr)", "Na2ThCl6": "Na2ThCl6(cr)",
          "KThCl5": "KThCl5(cr)", "K2ThCl6": "K2ThCl6(cr)"},
    "B": {"LiF_s": "LiF(s)", "LaF3_s": "LaF3(s)", "CeF3_s": "CeF3(s)", "NaLaF4": "NaLaF4(s)",
          "NaCeF4": "NaCeF4(s)", "NaF_s": "NaF(s)"},
}


def db_solids(path):
    """names of the stoichiometric phases, read from the file's tail"""
    db = mqmqa.Database.read(str(path))
    from mqmqa._database import _s
    return [_s(_lib.mqmqa_db_stoich_name(db._db, j)) for j in range(_lib.mqmqa_db_num_stoich(db._db))]


if __name__ == "__main__":
    main()
