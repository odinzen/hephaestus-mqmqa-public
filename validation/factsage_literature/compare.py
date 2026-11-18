"""Score the committed predictions against the sealed FactSage values, once.

    python compare.py SEALED_DIR [OUT_DIR]

Checks factsage_published.json against SEALED_HASHES.txt before reading it, writes
comparison.json and comparison.md to OUT_DIR (this folder by default), and will not overwrite an
earlier result.

The classes are those of ../thermochimica/PROTOCOL.md, where a value printed with fewer
significant figures is compared to the digits printed. Read here as follows (fixed 18 November
2026, before any sealed value was read; only the file's layout, with every digit masked, was
looked at to write this):

- Tabulated temperatures (cases A and B) are printed to the kelvin: agree if the prediction is
  within 0.5 K. A tabulated liquid composition agrees within half a unit of its last printed
  decimal. JSON drops trailing zeros, so a composition stored with fewer than three decimals is
  held to three (0.0005), the precision of the other rows; the looser reading is reported beside it.
  A composition printed as a fraction (n/m) is the compound's and is not scored.
- A condition with a temperature and a composition takes the worse class of the two. Only the
  quantities conditions.json names under "compute" are scored (A02 is T only).
- close: relative difference below 1e-4 but outside the printed digits. disagree: anything else,
  and a reaction the engine does not find in the scanned range ("not found"). failed: the
  prediction failed.
- Digitized values (case C) agree within the read uncertainty the sealed file states, compared at
  the nominal composition the figure plots; the read composition's offset is reported.
"""
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = "factsage_published.json"
CLOSE = 1e-4
MIN_X_DECIMALS = 3


class SealError(RuntimeError):
    pass


def sealed_entries(folder):
    m = re.match(r"([0-9a-f]{64})\s+\S+", (HERE / "SEALED_HASHES.txt").read_text(encoding="utf-8"))
    path = Path(folder) / NAME
    if hashlib.sha256(path.read_bytes()).hexdigest() != m.group(1):
        raise SealError(f"{NAME} does not match its committed hash")
    return {e["id"]: e for e in json.loads(path.read_text(encoding="utf-8"))["entries"]}


def decimals(v):
    s = repr(v)
    return len(s.split(".")[1]) if "." in s else 0


def classify(pred, ref, half):
    d = pred - ref
    if abs(d) <= half + 1e-12:
        return "agree", d
    if ref != 0 and abs(d / ref) < CLOSE:
        return "close", d
    return "disagree", d


WORST = {"agree": 0, "close": 1, "disagree": 2, "failed": 3}


def score_invariant(cid, cond, pred, ref):
    row = {"id": cid, "reaction": cond["reaction"], "ref_T_K": ref["T_K"]}
    if pred["class"] != "computed":
        row.update({"class": "disagree" if pred["class"] == "not found" else "failed",
                    "reason": pred.get("reason", "")})
        return row
    row["pred_T_K"] = pred["T_K"]
    cls_t, row["dT_K"] = classify(pred["T_K"], ref["T_K"], 0.5)
    classes = [cls_t]
    xkey = "X_ThCl4" if "X_ThCl4" in ref else "x_trifluoride"
    xref = ref.get(xkey)
    if "X" in cond["compute"] or "x(" in cond["compute"]:
        if isinstance(xref, str) or xref is None:
            row["x_note"] = f"composition printed as {xref!r}, not scored"
        else:
            n = decimals(xref)
            row["ref_x"], row["pred_x"] = xref, pred.get("x_liquid")
            if row["pred_x"] is None:
                classes.append("failed")
            else:
                strict = 0.5 * 10.0 ** -max(n, MIN_X_DECIMALS)
                cls_x, row["dx"] = classify(row["pred_x"], xref, strict)
                if n < MIN_X_DECIMALS:
                    row["x_class_as_stored"] = classify(row["pred_x"], xref, 0.5 * 10.0 ** -n)[0]
                classes.append(cls_x)
    row["class"] = max(classes, key=WORST.get)
    return row


def score_digitized(cid, pred, ref):
    row = {"id": cid, "quantity": ref["quantity"], "ref": ref["value"],
           "read_uncertainty": ref["read_uncertainty"], "x_read_offset": ref["x_NiF2_read"] - ref["x_NiF2_nominal"]}
    if pred["class"] != "computed":
        row["class"] = "failed"
        return row
    row["pred"] = pred["value"]
    row["class"], row["diff"] = classify(pred["value"], ref["value"], ref["read_uncertainty"])
    row["diff_over_uncertainty"] = row["diff"] / ref["read_uncertainty"]
    return row


def render(rows, header):
    out = [header, ""]
    for case in "ABC":
        rs = [r for r in rows if r["id"].startswith(case)]
        out += [f"## Case {case}", "", "Class counts: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(r['class'] for r in rs).items())), ""]
        if case == "C":
            out += ["| id | FactSage (read) | Hephaestus | difference | read uncertainty | class |", "|---|---|---|---|---|---|"]
            for r in rs:
                out.append(f"| {r['id']} | {r['ref']} | {r.get('pred', float('nan')):.3f} | {r.get('diff', float('nan')):+.3f} | {r['read_uncertainty']} | {r['class']} |")
        else:
            out += ["| id | reaction | FactSage T (K) | Hephaestus T (K) | dT (K) | FactSage x | Hephaestus x | dx | class |",
                    "|---|---|---|---|---|---|---|---|---|"]
            for r in rs:
                dt = f"{r['dT_K']:+.3f}" if "dT_K" in r else r.get("reason", "")
                pt = f"{r['pred_T_K']:.3f}" if "pred_T_K" in r else "-"
                dx = f"{r['dx']:+.5f}" if "dx" in r else r.get("x_note", "")
                out.append(f"| {r['id']} | {r['reaction']} | {r['ref_T_K']} | {pt} | {dt} | {r.get('ref_x', '')} | {r.get('pred_x', '')} | {dx} | {r['class']} |")
        out.append("")
    return "\n".join(out)


def main(sealed_dir, out_dir=HERE):
    out_dir = Path(out_dir)
    if (out_dir / "comparison.json").exists():
        raise SystemExit("comparison.json exists; the comparison runs once")
    conds = {c["id"]: c for case in json.loads((HERE / "conditions.json").read_text(encoding="utf-8"))["cases"]
             for c in case["conditions"]}
    preds_file = json.loads((HERE / "predictions.json").read_text(encoding="utf-8"))
    preds = {k: v for case in preds_file["predictions"].values() for k, v in case.items()}
    missing = sorted(set(conds) - set(preds))
    if missing:
        raise SystemExit(f"no prediction for {missing}")
    ref = sealed_entries(sealed_dir)
    rows = []
    for cid in sorted(conds):
        if cid not in ref:
            raise SystemExit(f"{cid} has no sealed value")
        rows.append(score_digitized(cid, preds[cid], ref[cid]) if ref[cid]["digitized"]
                    else score_invariant(cid, conds[cid], preds[cid], ref[cid]))
    result = {"engine_by_case": preds_file["engine_by_case"], "rows": rows,
              "counts": dict(Counter(r["class"] for r in rows))}
    (out_dir / "comparison.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    header = ("# FactSage cases A, B and C: comparison run once after unsealing\n\n"
              f"Engines: {json.dumps(preds_file['engine_by_case'])}. Rules in compare.py.")
    (out_dir / "comparison.md").write_text(render(rows, header), encoding="utf-8")
    print(result["counts"])


if __name__ == "__main__":
    main(*sys.argv[1:])
