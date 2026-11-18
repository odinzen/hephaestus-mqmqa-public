"""Predict the published FactSage cases from their conditions alone (conditions.json).

    python validation/factsage_literature/predict.py

Case C: the KF-NiF2 liquid of Ocadiz-Flores et al. as packaged on Zenodo (data/Ocadiz_combined.dat,
SHA-256 checked against conditions.json), G, H and S per mole of atoms at 1600 K. H = G - T dG/dT
and S = -dG/dT by central differences of 0.5 K, the liquid being the file's only phase.

Cases A and B (`predict.py AB`): the invariants of the binary files that build_cases.py writes from
the papers' tables (checked by check_cases.py), added to predictions.json beside case C.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "python"))
import mqmqa  # noqa: E402
from mqmqa import gem  # noqa: E402

DT = 0.5


def case_c(case):
    path = HERE / "data" / "Ocadiz_combined.dat"
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if sha != case["parameters"]["database_file_sha256"]:
        raise SystemExit(f"{path.name}: SHA-256 {sha} is not the one the conditions name")
    db = mqmqa.Database.read(str(path))
    out = {}
    for c in case["conditions"]:
        x, T = c["x_NiF2"], float(c["T_K"])
        amt = {"K": 1.0 - x, "NI": x, "F": (1.0 - x) + 2.0 * x}
        amt = {k: v for k, v in amt.items() if v > 0.0}

        def G(t):
            r = gem.equilibrium(db, t, amt)
            if len(r.sets) != 1:
                raise RuntimeError(f"{c['id']}: the liquid splits into {len(r.sets)} sets at {t} K")
            return r.G

        g0, gp, gm = G(T), G(T + DT), G(T - DT)
        dgdt = (gp - gm) / (2 * DT)
        kind = c["compute"].split()[0]
        val = {"Gibbs": g0 / 1000.0, "enthalpy": (g0 - T * dgdt) / 1000.0, "entropy": -dgdt}[kind]
        out[c["id"]] = {"class": "computed", "value": val,
                        "unit": "J/K per mole of atoms" if kind == "entropy" else "kJ per mole of atoms"}
    return out


# Cases A and B: the invariants of each binary from the files build_cases.py writes. Each is
# found where a phase appears or vanishes on heating at a bulk composition the reaction fixes
# (x is the mole fraction of the ThCl4 or trifluoride component), bracketed on a 5 K scan from
# 298.15 K, where the tables start, and bisected to 1e-3 K. The liquid composition of a eutectic or peritectic is that of the liquid
# 0.01 K above, beside the solid in excess.
#   (id, file, x, phase that changes, "appears" or "vanishes", liquid composition wanted)
INVARIANTS = [
    ("A01", "caseA_LiCl-ThCl4", 0.0, "LIQUID", "appears", False),
    ("A02", "caseA_LiCl-ThCl4", 0.18, "LI4THCL8", "vanishes", False),
    ("A03", "caseA_LiCl-ThCl4", 0.6, "LIQUID", "appears", True),
    ("A04", "caseA_LiCl-ThCl4", 1.0, "THCL4_BETA", "appears", False),
    ("A05", "caseA_LiCl-ThCl4", 1.0, "LIQUID", "appears", False),
    ("A06", "caseA_NaCl-ThCl4", 0.0, "LIQUID", "appears", False),
    ("A07", "caseA_NaCl-ThCl4", 1 / 6, "LIQUID", "appears", True),
    ("A08", "caseA_NaCl-ThCl4", 1 / 3, "LIQUID", "appears", False),
    ("A09", "caseA_NaCl-ThCl4", 2 / 3, "LIQUID", "appears", True),
    ("A10", "caseA_KCl-ThCl4", 0.0, "LIQUID", "appears", False),
    ("A11", "caseA_KCl-ThCl4", 1 / 6, "LIQUID", "appears", True),
    ("A12", "caseA_KCl-ThCl4", 1 / 3, "LIQUID", "appears", False),
    ("A13", "caseA_KCl-ThCl4", 5 / 12, "LIQUID", "appears", True),
    ("A14", "caseA_KCl-ThCl4", 0.5, "LIQUID", "appears", False),
    ("A15", "caseA_KCl-ThCl4", 0.75, "LIQUID", "appears", True),
    ("B01", "caseB_LiF-LaF3", 0.5, "LIQUID", "appears", True),
    ("B02", "caseB_NaF-LaF3", 0.25, "LIQUID", "appears", True),
    ("B03", "caseB_NaF-LaF3", 0.52, "NALAF4", "vanishes", True),
    ("B04", "caseB_NaF-LaF3", 0.48, "NALAF4", "appears", False),
    ("B05", "caseB_LiF-CeF3", 0.5, "LIQUID", "appears", True),
    ("B06", "caseB_NaF-CeF3", 0.25, "LIQUID", "appears", True),
    ("B07", "caseB_NaF-CeF3", 0.52, "NACEF4", "vanishes", True),
    ("B08", "caseB_NaF-CeF3", 0.48, "NACEF4", "appears", False),
]
SCAN = (298.15, 1900.0, 5.0)


def _system(stem):
    a, b = stem.split("_", 1)[1].split("-")
    an = "Cl" if stem.startswith("caseA") else "F"
    cat_a = a[: -len(an)]
    q_b = 4 if an == "Cl" else 3
    cat_b = b[: -(len(an) + 1)]
    return cat_a, cat_b, an, q_b


def _state(db, stem, x, T):
    cat_a, cat_b, an, q_b = _system(stem)
    amt = {cat_a: 1.0 - x, cat_b: x, an: (1.0 - x) + q_b * x}
    amt = {k: v for k, v in amt.items() if v > 0.0}
    for dT in (0.0, 0.004, -0.004):           # as elsewhere: a congruent point can leave the certificate unmet
        try:
            r = gem.equilibrium(db, T + dT, amt)
            break
        except RuntimeError:
            r = None
    if r is None:
        raise RuntimeError(f"{stem} x={x:.4f}: no equilibrium at {T:.3f} K")
    present = {}
    x_liq = None
    for s in r.sets:
        if s.amount <= 1e-9:
            continue
        key = "LIQUID" if s.phase.endswith("LIQUID") else s.phase
        present[key] = present.get(key, 0.0) + s.amount
        if key == "LIQUID":
            fa = s.x.get(cat_a.upper(), s.x.get(cat_a, 0.0))
            fb = s.x.get(cat_b.upper(), s.x.get(cat_b, 0.0))
            x_liq = fb / (fa + fb)
    return present, x_liq


class NotFound(Exception):
    """the reaction does not happen inside the scanned range"""


def _invariant(db, stem, x, phase, how):
    """A phase that vanishes on heating is first waited for: a compound stable only above a
    eutectoid (NaLaF4) is absent at the bottom of the scan."""
    def has(T):
        return phase in _state(db, stem, x, T)[0]

    def hit(T):
        return has(T) if how == "appears" else not has(T)
    lo, hi, step = SCAN
    T = lo
    if how == "vanishes":
        while T < hi and not has(T):
            T += step
    elif hit(T):
        raise NotFound(f"{phase} is already present at {lo} K, the bottom of the data")
    while T < hi and not hit(T + step):
        T += step
    if T >= hi:
        raise NotFound(f"{phase} never {how} below {hi} K")
    a, b = T, T + step
    while b - a > 1e-3:
        m = 0.5 * (a + b)
        a, b = (a, m) if hit(m) else (m, b)
    return b


def case_ab():
    out = {}
    dbs = {}
    for cid, stem, x, phase, how, want_x in INVARIANTS:
        db = dbs.setdefault(stem, mqmqa.Database.read(str(HERE / "data" / f"{stem}.dat")))
        try:
            T = _invariant(db, stem, x, phase, how)
            rec = {"class": "computed", "T_K": round(T, 3), "bulk_x": round(x, 6), "phase": phase, "how": how}
            if want_x:
                _, xl = _state(db, stem, x, T + 0.01)
                rec["x_liquid"] = round(xl, 5)
        except NotFound as e:
            rec = {"class": "not found", "reason": str(e), "bulk_x": round(x, 6)}
        except RuntimeError as e:
            rec = {"class": "failed", "reason": str(e)}
        out[cid] = rec
        print(cid, rec, flush=True)
    return out


def git(*a):
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True).stdout.strip()


def main():
    """`predict.py` predicts case C; `predict.py AB` predicts cases A and B and adds them beside
    the case C predictions already in predictions.json, each case with the engine that made it."""
    cases = {c["case"]: c for c in json.loads((HERE / "conditions.json").read_text(encoding="utf-8"))["cases"]}
    engine = {"engine_commit": git("rev-parse", "--short", "HEAD"),
              "engine_dirty": bool(git("status", "--porcelain", "--", "src", "python"))}
    if sys.argv[1:] == ["AB"]:
        out = json.loads((HERE / "predictions.json").read_text(encoding="utf-8"))
        out.setdefault("engine_by_case", {"C": {k: out[k] for k in ("engine_commit", "engine_dirty")}})
        ab = case_ab()
        for case in "AB":
            out["predictions"][case] = {k: v for k, v in ab.items() if k.startswith(case)}
            out["engine_by_case"][case] = engine
    else:
        pred = {"C": case_c(cases["C"])}
        out = dict(engine, predictions=pred)
        for k, v in pred["C"].items():
            print("C", k, f"{v['value']:.4f}", v["unit"])
    (HERE / "predictions.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
