"""Score predictions_<round>.json against the sealed values, once, after they are unsealed.

    python validation/literature/score.py SEALED_VALUES.csv [round]

Written and committed before the round was unsealed; the scores are those of RULES.md. Writes
score_<round>.json and score_<round>.md beside this script.
"""
import csv
import json
import math
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXCLUDED = {"478", "479"}       # RULES.md: Xu 2018, not shown to be outside the KCl-MgCl2 fit
TEMPS = ("liquidus_T", "solidus_T", "invariant_T")
REPORTED = {    # reported primary phase -> database phase, as predict.py maps named solids
    "a-CaSiO3": "WOLLASTONITE", "b-CaSiO3 ss": "WOLLASTONITE", "Ca-Fe olivine": "OLIVINE",
    "tridymite": "CRISTOBALITE", "Ca2SiO4": "LARNITE", "3CaO.2SiO2 (rankinite)": "RANKINITE",
}


def rms(v):
    return math.sqrt(sum(x * x for x in v) / len(v)) if v else None


def summary(errs, within=None):
    if not errs:
        return {"n": 0}
    out = {"n": len(errs), "rms": rms(errs), "median_abs": statistics.median(abs(e) for e in errs),
           "mean": sum(errs) / len(errs)}
    if within is not None:
        out["fraction_within_uncertainty"] = sum(within) / len(within)
    return out


def score(values_path, rnd="round1"):
    pred = json.loads((HERE / f"predictions_{rnd}.json").read_text(encoding="utf-8"))["predictions"]
    sealed = list(csv.DictReader(open(values_path, encoding="utf-8-sig")))
    cond = list(csv.DictReader(open(HERE / f"conditions_{rnd.removesuffix('_corrected')}.csv", encoding="utf-8-sig")))
    # the sealed file has no row column; seal.py numbered its rows by position from 1
    if len(sealed) != len(cond):
        raise SystemExit(f"sealed file has {len(sealed)} rows, conditions {len(cond)}")
    meas = {}
    for c, r in zip(cond, sealed):
        for col in ("system", "quantity", "composition", "phase_or_species"):
            if c[col] != r[col]:
                raise SystemExit(f"row {c['row']}: {col} differs between conditions and sealed file")
        meas[c["row"]] = r
    out = {"round": rnd, "by_model": {}, "points": {}}
    for model in ("hephaestus", "baseline"):
        groups, classes, ident = {}, {}, []
        for rid, p in pred.items():
            m = meas.get(rid)
            q, sysname, got = p["quantity"], p["system"], p[model]
            key = f"{sysname} | {q}"
            cls = got["class"] if rid not in EXCLUDED else "excluded"
            classes.setdefault(key, {}).setdefault(cls, 0)
            classes[key][cls] += 1
            point = out["points"].setdefault(rid, {"system": sysname, "quantity": q,
                                                   "measured": float(m["value"]) if m and m["value"] else None,
                                                   "unit": m["unit"] if m else None})
            point[model] = {"class": cls, "value": got.get("value"), "reason": got.get("reason")}
            if cls != "computed" or m is None or not m["value"]:
                continue
            v, c = float(m["value"]), float(got["value"])
            g = groups.setdefault(key, {"err": [], "within": []})
            if q == "activity":
                if c > 0 and v > 0:
                    g["err"].append(math.log10(c) - math.log10(v))
            else:
                g["err"].append(c - v)
            if q in TEMPS:
                u = float(m["uncertainty"]) if m.get("uncertainty") else 10.0
                g["within"].append(abs(c - v) <= u)
            point[model]["error"] = g["err"][-1] if g["err"] else None
            if q == "liquidus_T":
                rep = m["phase_or_species"].replace("primary phase", "").strip()
                calc = (got.get("primary_phase") or [None])[0]
                ident.append(REPORTED.get(rep) == calc)
        out["by_model"][model] = {
            "scores": {k: summary(g["err"], g["within"] if g["within"] else None) for k, g in groups.items()},
            "classes": classes,
            "phase_identity_not_blind": (sum(ident) / len(ident)) if ident else None,
        }
    (HERE / f"score_{rnd}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    lines = [f"# Held-out literature test, {rnd}: scores", "",
             "Errors are calculated minus measured: K for temperatures, log10 units for activities, "
             "kJ/mol for enthalpies, absolute fractions for compositions. Phase identity is not blind "
             "(RULES.md).", ""]
    for model, s in out["by_model"].items():
        lines += [f"## {model}", "", "| System, quantity | n | RMS | median abs | mean | within unc. |",
                  "|---|---|---|---|---|---|"]
        for k, r in sorted(s["scores"].items()):
            if r["n"]:
                w = r.get("fraction_within_uncertainty")
                lines.append(f"| {k} | {r['n']} | {r['rms']:.4g} | {r['median_abs']:.4g} | {r['mean']:.4g} | "
                             + (f"{w:.2f}" if w is not None else "") + " |")
        lines += ["", "Classes of every point:", ""]
        for k, c in sorted(s["classes"].items()):
            lines.append(f"- {k}: " + ", ".join(f"{n} {cls}" for cls, n in sorted(c.items())))
        lines += ["", f"Primary phase as reported (not blind): {s['phase_identity_not_blind']}", ""]
    (HERE / f"score_{rnd}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    o = score(*sys.argv[1:])
    print(json.dumps({m: s["phase_identity_not_blind"] for m, s in o["by_model"].items()}))
