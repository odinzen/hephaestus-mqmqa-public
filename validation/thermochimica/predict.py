"""Hephaestus on every Thermochimica test condition and extended-grid point.

Reads only the committed conditions.json and Thermochimica's data files, never the sealed
folder. For each point it records the stable phases, the total Gibbs energy (J), each phase's
amount in moles of atoms and its element fractions, the element chemical potentials (J/mol)
and the solver's certificate, or the refusal and its reason.

    python predict.py THERMOCHIMICA_DATA_DIR predictions.json
"""
import hashlib
import json
import subprocess
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "python"))
import mqmqa  # noqa: E402
from mqmqa import gem  # noqa: E402

ATM = 101325.0
_dbs = {}


def load(data, name):
    if name not in _dbs:
        try:
            _dbs[name] = mqmqa.Database.read(str(data / name))
        except Exception as e:
            _dbs[name] = e
    return _dbs[name]


def refused(reason):
    return {"class": "refused", "reason": reason}


def amounts(c, db):
    """Element amounts as the test sets them; a test may set every element first and then name some."""
    els = [e for e, _ in db.elements]
    amt = {}
    if c.get("all_elements_amount") is not None:
        amt = {e: float(c["all_elements_amount"]) for e in els}
    by_upper = {e.upper(): e for e in els}
    for k, v in (c.get("element_amounts") or {}).items():
        amt[by_upper.get(k.upper(), k)] = float(v)
    return {k: v for k, v in amt.items() if v != 0.0}


def predict(data, c):
    cat = c.get("category", "equilibrium")
    if cat == "equilibrium_modified_data":
        return refused("the test changes the database in memory after reading it")
    db = load(data, c["database"]) if c.get("database") else None
    if db is None:
        return refused("no database named")
    if isinstance(db, Exception):
        return refused(str(db))
    if cat == "parse_only":
        return {"class": "read", "phases": list(db.phase_names)}
    T, P = c.get("temperature"), c.get("pressure")
    if T is None or P is None or c.get("mass_unit") not in ("moles", None):
        return refused(f"input not accepted: T={T} {c.get('temperature_unit')}, P={P} {c.get('pressure_unit')}, "
                       f"unit {c.get('mass_unit')}")
    tu, pu = c.get("temperature_unit"), c.get("pressure_unit")
    if tu not in ("K", "C", None):
        return refused(f"temperature unit {tu}")
    if pu not in ("atm", None):
        return refused(f"pressure unit {pu}")
    T = float(T) + (273.15 if tu == "C" else 0.0)
    P = float(P)
    amt = amounts(c, db)
    if not (0 < T <= 1e5) or not (P > 0) or not amt or any(not (v >= 0) for v in amt.values()):
        return refused(f"input not accepted: T={T} K, P={P} atm, amounts {amt}")
    t0 = time.time()
    try:
        r = gem.equilibrium(db, T, amt, P=P * ATM)
    except Exception as e:
        return refused(str(e))
    n = sum(amt.values())
    return {"class": "computed", "T_K": T, "P_atm": P, "amounts": amt,
            "G_total_J": r.G * n, "G_per_atom_J": r.G,
            "phases": [{"phase": s.phase, "moles_of_atoms": s.amount * n, "x": s.x} for s in r.sets],
            "mu_J_per_mol": r.mu, "certificate_J": r.residual, "passes": r.passes, "exact_finish": r.exact,
            "seconds": round(time.time() - t0, 2)}


def git(*args):
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True).stdout.strip()


def fingerprint():
    lib = REPO / "python" / "mqmqa" / "mqmqa.dll"
    return {"commit": git("rev-parse", "HEAD"),
            "src_tree": git("rev-parse", "HEAD:src"),
            "python_tree": git("rev-parse", "HEAD:python/mqmqa"),
            "uncommitted_engine_changes": bool(git("status", "--porcelain", "src", "python")),
            "library": lib.name,
            "library_sha256": hashlib.sha256(lib.read_bytes()).hexdigest(),
            "conditions_sha256": hashlib.sha256((HERE / "conditions.json").read_bytes()).hexdigest(),
            "python": sys.version.split()[0]}


def main():
    data, out_path = Path(sys.argv[1]), Path(sys.argv[2])
    cond = json.loads((HERE / "conditions.json").read_text(encoding="utf-8"))
    points = cond["conditions"] + [g for g in cond["extended_grid"] if "skipped" not in g]
    out = {"engine": fingerprint(), "points": {}}
    if out["engine"]["uncommitted_engine_changes"]:
        sys.exit("refusing to predict with uncommitted changes under src/ or python/")
    for c in points:
        try:
            out["points"][c["id"]] = predict(data, c)
        except Exception:
            out["points"][c["id"]] = {"class": "failed", "reason": traceback.format_exc(limit=2)}
    out_path.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(Counter(p["class"] for p in out["points"].values()))
    for k, p in out["points"].items():
        if p["class"] in ("refused", "failed"):
            print(f"  {p['class']:8s} {k}: {p['reason'][:140]}")


if __name__ == "__main__":
    main()
