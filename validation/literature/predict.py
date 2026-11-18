"""Predict every point of a sealed literature round from its conditions file alone.

    python validation/literature/predict.py [round] [workers]

Reads conditions_<round>.csv (no measured values), computes each point with the shipped
database the rules name, once as shipped and once with the liquid's ternary terms removed (the
baseline), and writes predictions_<round>.json. How each quantity is read is fixed in RULES.md,
"Decisions recorded before predicting", and is not changed after unsealing.
"""
import csv
import json
import math
import re
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "python"))
import mqmqa  # noqa: E402
from mqmqa import gem  # noqa: E402

DATA = REPO / "data"
DB_FOR = {      # system column -> shipped database (the lowest-order file holding it with its solids)
    "CaO-Al2O3-SiO2": "cao-al2o3-sio2/CaO-Al2O3-SiO2.dat",
    "CaO-SiO2": "cao-al2o3-sio2/CaO-Al2O3-SiO2.dat",
    "MgO-SiO2": "feo-mgo-sio2/FeO-MgO-SiO2-combined.dat",
    "FeO-SiO2": "feo-mgo-sio2/FeO-MgO-SiO2-combined.dat",
    "CaO-FeO-MgO-SiO2 (CaO-MgO-SiO2 face)": "cao-feo-mgo-sio2/CaO-FeO-MgO-SiO2-combined.dat",
    "CaO-FeO-MgO-SiO2 (CaO-FeO-SiO2 face, iron-saturated)": "cao-feo-mgo-sio2/CaO-FeO-MgO-SiO2-combined.dat",
    "NaCl-KCl-MgCl2": "nacl-kcl-mgcl2/NaCl-KCl-MgCl2.dat",
}
DROP = 1e-9                 # a phase below this amount (mol of atoms per mol) is not present
T_TOL = 0.01                # K, bisection width
T_LO, T_HI, T_STEP = 500.0, 3200.0, 100.0

# Named solids -> database phase, and the endmember that sets the construction's bulk.
# Polymorphs the databases do not distinguish map to one phase; None: not in the database.
SOLID = {
    "a-CaSiO3": ("CaSiO3", "WOLLASTONITE"), "b-CaSiO3 ss": ("CaSiO3", "WOLLASTONITE"),
    "pseudowollastonite": ("CaSiO3", "WOLLASTONITE"), "wollastonite ss": ("CaSiO3", "WOLLASTONITE"),
    "a-Ca2SiO4": ("Ca2SiO4", "LARNITE"), "b-Ca2SiO4": ("Ca2SiO4", "LARNITE"),
    "b-Ca2SiO4 ss": ("Ca2SiO4", "LARNITE"), "a-2CaO.SiO2": ("Ca2SiO4", "LARNITE"),
    "b-2CaO.SiO2": ("Ca2SiO4", "LARNITE"),
    "3CaO.2SiO2": ("Ca3Si2O7", "RANKINITE"),
    "tridymite": ("SiO2", "CRISTOBALITE"),
    "Ca-Fe olivine": ("Fe2SiO4", "OLIVINE"), "forsterite": ("Mg2SiO4", "OLIVINE"),
    "periclase": ("MgO", "MAGNESIOWUSTITE"), "diopside": ("CaMgSi2O6", "CLINOPYROXENE"),
    "2CaO.MgO.2SiO2": (None, None), "monticellite ss": (None, None),
    "5CaO.2MgO.6SiO2": (None, None), "5CaO.2MgO.6SiO2 ss": (None, None),
    "a-5CaO.2MgO.6SiO2 ss": (None, None), "CaFeSiO4": (None, None),
}

_cache = {}


def formula(s):
    """'Al2O3' -> {'AL': 2, 'O': 3}; FetO counts as FeO."""
    s = s.replace("FetO", "FeO")
    out = {}
    for el, n in re.findall(r"([A-Z][a-z]?)(\d*\.?\d*)", s):
        out[el.upper()] = out.get(el.upper(), 0.0) + (float(n) if n else 1.0)
    return out


def load(path, baseline):
    key = (path, baseline)
    if key not in _cache:
        db = mqmqa.Database.read(str(DATA / path))
        if baseline:
            ternary = set()
            for p, name in enumerate(db.phase_names):
                if "LIQUID" in name and db.phase_kind(p) == 0:
                    mx = db.mqmx(p, 1000.0)
                    ternary |= {(name, k) for k, a in enumerate(mx["addcat"]) if a >= 0}
            for prm in db.params():
                if prm["kind"] == "mqmx" and (prm["phase"], prm["term"]) in ternary:
                    db.set_param(prm["index"], 0.0)
        _cache[key] = db
    return _cache[key]


def amounts(db, comp, basis):
    """Element moles per mole of oxide (or salt) components from 'CaO=0.49; SiO2=0.11'."""
    mass = {e.upper(): m for e, m in db.elements}
    parts = [(k.strip(), float(v)) for k, v in (t.split("=") for t in comp.split(";") if "=" in t)]
    el = {}
    for name, frac in parts:
        f = formula(name)
        if name == "Fe2O3":     # total iron as FeO, as the authors' diagrams recalculate it
            f = {"FE": 2.0, "O": 2.0}
        mol = frac / sum(n * mass[e] for e, n in formula(name).items()) if basis.startswith("mass") else frac
        for e, n in f.items():
            el[e] = el.get(e, 0.0) + mol * n
    return {e: v for e, v in el.items() if v > 0.0}


def solve(db, T, amt, suspend=()):
    return gem.equilibrium(db, T, amt, suspend=suspend)


def solids(r):
    return sorted({s.phase for s in r.sets if "LIQUID" not in s.phase and s.amount > DROP})


def has_liquid(r):
    return any("LIQUID" in s.phase and s.amount > DROP for s in r.sets)


def bisect(pred, lo, hi):
    """pred(lo) false, pred(hi) true: the transition to TOL."""
    while hi - lo > T_TOL:
        mid = 0.5 * (lo + hi)
        if pred(mid):
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def liquidus(db, amt):
    """Highest temperature holding a solid: scanned down from T_HI, then bisected."""
    full = lambda T: not solids(solve(db, T, amt))
    T = T_HI
    if not full(T):
        return None, "solid at the top of the scan"
    while T > T_LO and full(T - T_STEP):
        T -= T_STEP
    if T <= T_LO:
        return None, "no solid down to the bottom of the scan"
    Tl = bisect(lambda t: full(t), T - T_STEP, T)
    return Tl, solids(solve(db, Tl - 2 * T_TOL, amt))


def solidus(db, amt):
    """Lowest temperature holding liquid: scanned up from T_LO, then bisected."""
    liq = lambda T: has_liquid(solve(db, T, amt))
    T = T_LO
    if liq(T):
        return None, "liquid at the bottom of the scan"
    while T < T_HI and not liq(T + T_STEP):
        T += T_STEP
    if T >= T_HI:
        return None, "no liquid up to the top of the scan"
    return bisect(liq, T, T + T_STEP), None


def invariant(db, names):
    """Solidus of the bulk at the centroid of the named solids' endmembers: the invariant's
    temperature, with the first liquid's composition and the solids just below it."""
    mapped = [SOLID.get(n.strip(), ("?", "?")) for n in names]
    if any(m[1] is None for m in mapped):
        lack = [n for n, m in zip(names, mapped) if m[1] is None]
        return {"class": "not_represented", "reason": f"no database phase for {', '.join(lack)}"}
    if any(m[1] == "?" for m in mapped):
        return {"class": "not_represented", "reason": f"a named solid is not in the mapping: {names}"}
    phases = sorted({m[1] for m in mapped})
    if len(phases) < 3:
        return {"class": "not_represented",
                "reason": f"the named solids map to {len(phases)} database phase(s): {phases}"}
    amt = {}
    for f, _ in mapped:
        fa = formula(f)
        tot = sum(fa.values())
        for e, n in fa.items():
            amt[e] = amt.get(e, 0.0) + n / tot
    Ts, why = solidus(db, amt)
    if Ts is None:
        return {"class": "refused", "reason": why}
    below = solve(db, Ts - 2 * T_TOL, amt)
    above = solve(db, Ts + 2 * T_TOL, amt)
    if solids(below) != phases:     # the database has the phases but not this assemblage: a miss
        return {"class": "wrong_assemblage", "T_K": Ts,
                "reason": f"below its solidus the bulk holds {solids(below)}, not {phases}"}
    liq = next(s for s in above.sets if "LIQUID" in s.phase)
    return {"class": "computed", "T_K": Ts, "liquid_x": liq.x,
            "solids_x": {s.phase: s.x for s in below.sets}}


def oxide_mass_fractions(db, x, oxides):
    """Element mole fractions of a phase -> mass fractions of the named oxides (cations decide)."""
    mass = {e.upper(): m for e, m in db.elements}
    w = {}
    for ox in oxides:
        f = formula(ox)
        cat = next(e for e in f if e != "O")
        mol = x.get(cat, 0.0) / f[cat]
        w[ox] = mol * sum(n * mass[e] for e, n in f.items())
    tot = sum(w.values())
    return {k: v / tot for k, v in w.items()}


def silica_activity(db, T, amt):
    r = solve(db, T, amt)
    silica = next(n for n in db.stoich if "CRISTOBALITE" in n)
    g0 = db.stoich_gibbs(db.stoich.index(silica), T)
    mu = r.mu.get("SI", 0.0) + 2.0 * r.mu.get("O", 0.0)
    return math.exp((mu - g0) / (db.R * T)), r.phases()


def pure_solid_gibbs(db, oxide, T):
    """Gibbs energy of one formula unit of `oxide` as its lowest pure solid in the database: a
    compound of that composition, or a solid-solution endmember of it (MgO in magnesiowustite)."""
    f = formula(oxide)
    els = [e.upper() for e, _ in db.elements]
    atoms = sum(f.values())
    best = None

    def same(v):                # element vector proportional to the oxide's
        tot = sum(v)
        return tot > 0 and all(abs(v[i] / tot - f.get(e, 0.0) / atoms) < 1e-9 for i, e in enumerate(els))

    for i, name in enumerate(db.stoich):
        v = db.stoich_elements(i)
        if same(v):
            g = db.stoich_gibbs(i, T) * atoms / sum(v)
            best = g if best is None else min(best, g)
    for p, name in enumerate(db.phase_names):
        if "LIQUID" in name or db.phase_kind(p) != 1:
            continue
        subl = db.cef_sublattices(p)
        n = [len(s["constituents"]) for s in subl]
        idx = [0] * len(subl)
        while True:
            v = [0.0] * len(els)
            for s, k in zip(subl, idx):
                c = s["constituents"][k].upper()
                if c in els:
                    v[els.index(c)] += s["site_ratio"]
            if same(v):
                Y = []
                for s, k in zip(subl, idx):
                    Y += [1.0 if j == k else 0.0 for j in range(len(s["constituents"]))]
                g = db.cef_gibbs(p, Y, T) * atoms          # per mole of atoms -> per formula
                best = g if best is None else min(best, g)
            j = 0
            while j < len(idx) and idx[j] + 1 == n[j]:
                idx[j] = 0
                j += 1
            if j == len(idx):
                break
            idx[j] += 1
    if best is None:
        raise ValueError(f"no pure solid {oxide} in the database")
    return best


def oxide_activity(db, T, amt, oxide):
    """Activity of `oxide` against its pure solid, from the equilibrium potentials at the bulk."""
    r = solve(db, T, amt)
    mu = sum(n * r.mu.get(e, 0.0) for e, n in formula(oxide).items())
    return math.exp((mu - pure_solid_gibbs(db, oxide, T)) / (db.R * T)), r.phases()


def liquid_enthalpy(db, T, amt):
    """Enthalpy of the liquid alone at fixed composition, J per the amounts given:
    H = G - T dG/dT by central differences of 0.5 K."""
    liquid = next(n for n in db.phase_names if "LIQUID" in n)
    hold = [n for n in db.phase_names if n != liquid] + list(db.stoich)
    n = sum(amt.values())
    g = lambda t: solve(db, t, amt, suspend=hold).G * n
    return g(T) - T * (g(T + 0.5) - g(T - 0.5)) / 1.0


def compound_enthalpy(db, name, T):
    i = db.stoich.index(name)
    G = lambda t: db.stoich_gibbs(i, t)
    return G(T) - T * (G(T + 0.5) - G(T - 0.5)) / 1.0


def predict_one(row, baseline):
    path = DB_FOR.get(row["system"])
    if path is None:
        return {"class": "refused", "reason": f"no shipped database for {row['system']}"}
    db = load(path, baseline)
    q = row["quantity"]
    try:
        if q == "activity":
            # the oxide the row names ('CaO in liquid slag (reference: pure solid CaO)'); the frozen
            # round-1 predictions computed SiO2 for every row, the error corrected after unsealing
            oxide = row["phase_or_species"].split()[0]
            amt = amounts(db, row["composition"], row["composition_basis"])
            a, ph = oxide_activity(db, float(row["T_K"]), amt, oxide)
            return {"class": "computed", "value": a, "phases": ph, "oxide": oxide}
        if q == "liquidus_T":
            amt = amounts(db, row["composition"], row["composition_basis"])
            T, ph = liquidus(db, amt)
            if T is None:
                return {"class": "refused", "reason": ph}
            return {"class": "computed", "value": T, "primary_phase": ph}
        if q == "solidus_T":
            amt = amounts(db, row["composition"], row["composition_basis"])
            T, why = solidus(db, amt)
            return {"class": "refused", "reason": why} if T is None else {"class": "computed", "value": T}
        if q in ("invariant_T", "invariant_liquid_composition", "coexisting_solid_composition"):
            label = row["composition"]
            # an invariant is named after the colon; a congruent melting point names its solid
            # in the phase column ('CaFeSiO4 (kirschsteinite) and liquid CaFeSiO4')
            named = label.split(":", 1)[1] if ":" in label else row["phase_or_species"]
            names = re.split(r"\s*\+\s*", named.split("(")[0].strip())
            names = [n for n in names if n and n != "L"]
            inv = invariant(db, names)
            if inv["class"] != "computed":
                return inv
            if q == "invariant_T":
                return {"class": "computed", "value": inv["T_K"]}
            if q == "invariant_liquid_composition":
                ox = row["phase_or_species"].split(":")[-1].strip()
                oxides = [o for o in ("CaO", "FeO", "MgO", "SiO2") if formula(o).keys() - {"O"} <= set(inv["liquid_x"])]
                return {"class": "computed", "value": oxide_mass_fractions(db, inv["liquid_x"], oxides)[ox]}
            # coexisting solid: '<solid> at invariant X: <endmember> content'
            solid = row["phase_or_species"].split(" at invariant")[0].strip()
            endm = row["phase_or_species"].split(":")[-1].replace("content", "").strip()
            phase = SOLID.get(solid, (None, None))[1]
            if phase not in inv["solids_x"]:
                return {"class": "not_represented", "reason": f"{solid} maps to {phase}, not in the assemblage"}
            x = inv["solids_x"][phase]
            cat = next(e for e in formula(endm) if e != "O")
            others = {e: v for e, v in x.items() if e not in ("O", "SI")}
            tot = sum(others.values())
            return {"class": "computed", "value": others.get(cat, 0.0) / tot if tot else 0.0,
                    "basis": "cation fraction of the endmember's cation among the non-Si cations"}
        if q == "enthalpy_of_mixing":
            amt = amounts(db, row["composition"], "mole fraction")
            T = float(row["T_K"])
            xf = amt.get("FE", 0.0)
            xs = amt.get("SI", 0.0)
            H = liquid_enthalpy(db, T, amt)
            h_feo = liquid_enthalpy(db, T, {"FE": 1.0, "O": 1.0})
            silica = next(n for n in db.stoich if "CRISTOBALITE" in n)
            h_sio2 = compound_enthalpy(db, silica, T)
            return {"class": "computed", "value": (H - xf * h_feo - xs * h_sio2) / 1000.0,
                    "unit": "kJ per mol of FeO + SiO2"}
        return {"class": "refused", "reason": f"quantity {q} has no rule"}
    except Exception as e:      # a failed point is listed, not hidden
        return {"class": "refused", "reason": f"{type(e).__name__}: {e}"}


def work(args):
    row, baseline = args
    t0 = time.time()
    out = predict_one(row, baseline)
    out["seconds"] = round(time.time() - t0, 1)
    return row["row"], baseline, out


def git(*a):
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True).stdout.strip()


def corrected(rnd, workers):
    """After unsealing: recompute only the activity rows, every other row kept from the frozen
    file, written to predictions_<round>_corrected.json beside it."""
    frozen = json.loads((HERE / f"predictions_{rnd}.json").read_text(encoding="utf-8"))
    rows = [r for r in csv.DictReader(open(HERE / f"conditions_{rnd}.csv", encoding="utf-8-sig"))
            if r["quantity"] == "activity"]
    res = frozen["predictions"]
    with Pool(workers) as pool:
        for rid, base, out in pool.imap_unordered(work, [(r, b) for r in rows for b in (False, True)]):
            res[rid]["baseline" if base else "hephaestus"] = out
    frozen.update({"corrected_after_unsealing": "activity rows: the named oxide, not SiO2 for every row",
                   "corrected_engine_commit": git("rev-parse", "--short", "HEAD")})
    (HERE / f"predictions_{rnd}_corrected.json").write_text(json.dumps(frozen, indent=1), encoding="utf-8")
    print(f"recomputed {len(rows)} activity rows")


def main():
    rnd = sys.argv[1] if len(sys.argv) > 1 else "round1"
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    if len(sys.argv) > 3 and sys.argv[3] == "corrected":
        return corrected(rnd, workers)
    rows = list(csv.DictReader(open(HERE / f"conditions_{rnd}.csv", encoding="utf-8-sig")))
    jobs = [(r, b) for r in rows for b in (False, True)]
    jobs.sort(key=lambda j: j[0]["quantity"] in ("activity", "enthalpy_of_mixing"))   # slow ones first
    t0 = time.time()
    res = {r["row"]: {"system": r["system"], "quantity": r["quantity"]} for r in rows}
    with Pool(workers) as pool:
        for n, (rid, base, out) in enumerate(pool.imap_unordered(work, jobs), 1):
            res[rid]["baseline" if base else "hephaestus"] = out
            if n % 40 == 0:
                print(f"{n}/{len(jobs)}  {time.time() - t0:.0f} s", flush=True)
    out = {"round": rnd, "engine_commit": git("rev-parse", "--short", "HEAD"),
           "engine_dirty": bool(git("status", "--porcelain", "--", "src", "python")),
           "databases": DB_FOR, "predictions": res}
    (HERE / f"predictions_{rnd}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"done {len(jobs)} predictions in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
