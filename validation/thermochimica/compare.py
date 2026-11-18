"""Score the committed predictions against the sealed Thermochimica results, once.

    python compare.py SEALED_DIR [OUT_DIR]

Before reading any sealed value it checks the SHA-256 of expected.json and
thermochimica_results.json against SEALED_HASHES.txt, and of every raw output file it reads
against RAW_OUTPUT_MANIFEST.txt; any mismatch stops it. It writes comparison.json and
comparison.md to OUT_DIR (this folder by default) and will not overwrite an earlier result.

Classes and tolerances are the ones fixed in PROTOCOL.md; the reading of each quantity is
fixed in the note of 15 November 2026 there.
"""
import hashlib
import itertools
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent

G_AGREE, G_CLOSE = 1e-6, 1e-4
REL, ABS_MOL, ABS_MU = 1e-4, 1e-6, 1.0
SAME_SET_DX = 2e-3
COMPARED = ("integral_gibbs_energy", "phase_moles", "element_chemical_potential")


class SealError(RuntimeError):
    pass


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_hashes(path):
    """name -> sha256 from lines '<hash>  <name>' or '<hash> *./<name>'."""
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"([0-9a-f]{64})\s+\*?(?:\./)?(\S+)", line)
        if m:
            out[m.group(2)] = m.group(1)
    return out


class Sealed:
    """The sealed folder, read only through hash checks."""

    def __init__(self, folder, hashes=HERE / "SEALED_HASHES.txt", manifest=HERE / "RAW_OUTPUT_MANIFEST.txt"):
        self.folder = Path(folder)
        top = read_hashes(hashes)
        self.manifest = read_hashes(manifest)
        if "RAW_OUTPUT_MANIFEST.txt" in top and sha256(manifest) != top["RAW_OUTPUT_MANIFEST.txt"]:
            raise SealError("RAW_OUTPUT_MANIFEST.txt does not match its committed hash")
        for name in ("expected.json", "thermochimica_results.json"):
            if name not in top:
                raise SealError(f"no committed hash for {name}")
            if sha256(self.folder / name) != top[name]:
                raise SealError(f"{name} does not match its committed hash")
        self.expected = json.loads((self.folder / "expected.json").read_text(encoding="utf-8"))
        self.results = json.loads((self.folder / "thermochimica_results.json").read_text(encoding="utf-8"))
        self.raw_checked = 0

    def raw(self, rid):
        """Thermochimica's own JSON output for one run, or None if it wrote none."""
        name = f"{rid}.json"
        path = self.folder / "thermochimica_raw" / name
        if name not in self.manifest:
            return None
        if sha256(path) != self.manifest[name]:
            raise SealError(f"thermochimica_raw/{name} does not match RAW_OUTPUT_MANIFEST.txt")
        self.raw_checked += 1
        d = json.loads(path.read_text(encoding="utf-8"))
        return d.get("1") if isinstance(d, dict) else None


def base(name):
    """Phase name with case, spaces and underscores folded and any '#n' dropped, so both codes match."""
    return re.sub(r"[\s_]+", "_", str(name).split("#")[0].strip()).upper()


def within(a, b, abs_tol):
    d = abs(a - b)
    return d <= abs_tol or d <= REL * abs(b)


def rel_g(g, ref):
    return abs(g - ref) / abs(ref) if ref else (0.0 if g == ref else math.inf)


def reference_phases(raw):
    """Stable phases in a raw Thermochimica result, as [(name, moles, {element: moles in phase}, group)]."""
    out = []
    for group in ("solution phases", "pure condensed phases"):
        for name, ph in (raw.get(group) or {}).items():
            if ph.get("moles", 0) > 0:
                els = ph.get("elements")
                el_moles = None
                if isinstance(els, dict) and all("moles of element in phase" in v for v in els.values()):
                    el_moles = {e: v["moles of element in phase"] for e, v in els.items()}
                out.append((name, ph["moles"], el_moles, group))
    return out


def merge_copies(ref):
    """Instances of one phase within SAME_SET_DX of each other in every element fraction are one
    set. A ChemSage file lists a phase twice for a possible miscibility gap; where none opens both
    copies can carry an amount at one composition. Hephaestus merges them the same way."""
    out = []
    for name, moles, el, group in ref:
        x = {e.upper(): v / sum(el.values()) for e, v in el.items()} if el and sum(el.values()) else None
        for i, (n2, m2, el2, g2) in enumerate(out):
            if base(n2) != base(name) or x is None or not el2:
                continue
            x2 = {e.upper(): v / sum(el2.values()) for e, v in el2.items()}
            if max(abs(x.get(e, 0.0) - x2.get(e, 0.0)) for e in set(x) | set(x2)) < SAME_SET_DX:
                merged = {e: el2.get(e, 0.0) + el.get(e, 0.0) for e in set(el2) | set(el)}
                out[i] = (n2, m2 + moles, merged, g2)
                break
        else:
            out.append((name, moles, el, group))
    return out


def merge_ours(sets):
    """The same rule on Hephaestus's sets."""
    out = []
    for st in sets:
        x = {e.upper(): v for e, v in st["x"].items()}
        for o in out:
            xo = {e.upper(): v for e, v in o["x"].items()}
            near = max(abs(x.get(e, 0.0) - xo.get(e, 0.0)) for e in set(x) | set(xo)) < SAME_SET_DX
            if base(o["phase"]) == base(st["phase"]) and near:
                a0, a1 = o["moles_of_atoms"], st["moles_of_atoms"]
                o["x"] = {e: (xo.get(e, 0.0) * a0 + x.get(e, 0.0) * a1) / (a0 + a1) for e in set(x) | set(xo)}
                o["moles_of_atoms"] = a0 + a1
                break
        else:
            out.append({"phase": st["phase"], "moles_of_atoms": st["moles_of_atoms"],
                        "x": {e.upper(): v for e, v in st["x"].items()}})
    return out


def pair_sets(ours, ref):
    """Match our sets to the reference's phase by phase; within one phase, by closest composition."""
    pairs = []
    for b in sorted({base(r[0]) for r in ref}):
        mine = [s for s in ours if base(s["phase"]) == b]
        theirs = [r for r in ref if base(r[0]) == b]
        if len(mine) != len(theirs):
            return None
        best = None
        for perm in itertools.permutations(mine):
            cost = sum(_xdist(s, r) for s, r in zip(perm, theirs))
            if best is None or cost < best[0]:
                best = (cost, list(zip(perm, theirs)))
        pairs += best[1]
    return pairs


def _xdist(s, r):
    if r[2] is None:
        return 0.0
    tot = sum(r[2].values())
    if not tot:
        return 0.0
    els = {e.upper() for e in s["x"]} | {e.upper() for e in r[2]}
    xs = {e.upper(): v for e, v in s["x"].items()}
    xr = {e.upper(): v / tot for e, v in r[2].items()}
    return sum(abs(xs.get(e, 0.0) - xr.get(e, 0.0)) for e in els)


def rank(rows, tol=1e-9):
    m = [list(r) for r in rows]
    k = 0
    for c in range(len(m[0]) if m else 0):
        p = max(range(k, len(m)), key=lambda i: abs(m[i][c]), default=None)
        if p is None or abs(m[p][c]) <= tol:
            continue
        m[k], m[p] = m[p], m[k]
        for i in range(len(m)):
            if i != k:
                f = m[i][c] / m[k][c]
                m[i] = [a - f * b for a, b in zip(m[i], m[k])]
        k += 1
        if k == len(m):
            break
    return k


def potentials_undetermined(pred, ref):
    """Compounds alone, with fewer independent compositions than elements: the stable phases fix
    only mu.x at each of them, and any split of the rest is as good (solid CsI fixes mu(Cs) + mu(I))."""
    if not ref or any(r[3] != "pure condensed phases" for r in ref):
        return False
    els = sorted(e.upper() for e in (pred.get("amounts") or pred["mu_J_per_mol"]))
    rows = [[{k.upper(): v for k, v in s["x"].items()}.get(e, 0.0) for e in els] for s in pred["phases"]]
    return rank(rows) < len(els)


def plane_at(mu, x):
    return sum(v * (mu_lookup(mu, e) or 0.0) for e, v in x.items())


def mu_lookup(mu, element):
    for k, v in mu.items():
        if k.upper() == str(element).upper():
            return v
    return None


def score(same_assemblage, g_rel, amounts_ok, mu_ok):
    if not same_assemblage or g_rel is None:
        return "disagree"
    if g_rel < G_AGREE and amounts_ok and mu_ok:
        return "agree"
    if g_rel < G_CLOSE:
        return "close"
    return "disagree"


def against_run(pred, res, raw, category):
    """One point against Thermochimica's own run at the same condition."""
    if pred["class"] in ("refused", "failed"):
        return {"class": pred["class"], "reason": pred["reason"],
                "as_the_test_requires": category == "input_validation" and pred["class"] == "refused"}
    if category == "input_validation":
        return {"class": "disagree", "reason": "Hephaestus computed an input the test requires to be refused"}
    if res is None or res.get("status") != "ok" or raw is None:
        return {"class": "no reference", "reason": "Thermochimica returned no result for this point"}
    ref = merge_copies(reference_phases(raw))
    pred = dict(pred, phases=merge_ours(pred["phases"]))
    ours = [base(s["phase"]) for s in pred["phases"]]
    theirs = [base(r[0]) for r in ref]
    same = Counter(ours) == Counter(theirs)
    g_ref = raw.get("integral Gibbs energy")
    g_rel = rel_g(pred["G_total_J"], g_ref) if g_ref is not None else None
    rec = {"same_assemblage": same, "phases": sorted(ours), "reference_phases": sorted(theirs),
           "G_J": pred["G_total_J"], "reference_G_J": g_ref, "G_relative_difference": g_rel}
    amounts_ok, phase_rows = True, []
    pairs = pair_sets(pred["phases"], ref) if same else None
    for s, r in pairs or []:
        if r[2] is None:
            amounts_ok = False
            phase_rows.append({"phase": r[0], "note": "reference gives no element amounts in this phase"})
            continue
        atoms = sum(r[2].values())
        ok = within(s["moles_of_atoms"], atoms, ABS_MOL)
        amounts_ok &= ok
        phase_rows.append({"phase": r[0], "moles_of_atoms": s["moles_of_atoms"], "reference_moles_of_atoms": atoms,
                           "within_tolerance": ok, "composition_difference": _xdist(s, r)})
    rec["phase_amounts"] = phase_rows
    mu_ok, mu_rows = True, []
    if same and potentials_undetermined(pred, ref):
        rec["potentials_undetermined"] = True
        ref_mu = {e: v.get("element potential") for e, v in (raw.get("elements") or {}).items()}
        for s, r in pairs or []:
            ours_g, ref_g = plane_at(pred["mu_J_per_mol"], s["x"]), plane_at(ref_mu, s["x"])
            ok = within(ours_g, ref_g, ABS_MU)
            mu_ok &= ok
            mu_rows.append({"phase": r[0], "mu_dot_x_J_per_mol": ours_g, "reference_mu_dot_x_J_per_mol": ref_g,
                            "within_tolerance": ok})
    elements = () if rec.get("potentials_undetermined") else (raw.get("elements") or {}).items()
    for el, v in elements:
        ref_mu = v.get("element potential")
        if not v.get("moles"):
            continue
        ours_mu = mu_lookup(pred["mu_J_per_mol"], el)
        ok = ours_mu is not None and ref_mu is not None and within(ours_mu, ref_mu, ABS_MU)
        mu_ok &= ok
        mu_rows.append({"element": el, "mu_J_per_mol": ours_mu, "reference_mu_J_per_mol": ref_mu, "within_tolerance": ok})
    rec["chemical_potentials"] = mu_rows
    # Thermochimica's own consistency, so a unit slip on its side is visible rather than scored
    if g_ref is not None:
        gd = sum(v.get("moles", 0.0) * (v.get("element potential") or 0.0) for v in (raw.get("elements") or {}).values())
        rec["reference_G_minus_sum_n_mu_J"] = g_ref - gd
    rec["class"] = score(same, g_rel, amounts_ok, mu_ok)
    return rec


def against_expected(test, pred, res_raw, category):
    """One test against the reference values held in Thermochimica's test program."""
    checks = test.get("checks") or []
    if category == "parse_only":
        return {"class": "agree" if pred["class"] == "read" else pred["class"],
                "reason": pred.get("reason"), "checks": [{"quantity": "data_file_parses", "result": pred["class"]}]}
    if pred["class"] in ("refused", "failed"):
        return {"class": pred["class"], "reason": pred["reason"],
                "as_the_test_requires": category == "input_validation" and pred["class"] == "refused"}
    if category == "input_validation":
        return {"class": "disagree", "reason": "Hephaestus computed an input the test requires to be refused"}
    pred = dict(pred, phases=merge_ours(pred["phases"]))
    present = {base(s["phase"]) for s in pred["phases"]}
    undetermined = bool(res_raw) and potentials_undetermined(pred, merge_copies(reference_phases(res_raw)))
    ratio = {}
    for name, moles, el, _ in merge_copies(reference_phases(res_raw)) if res_raw else []:
        if el:
            ratio.setdefault(base(name), moles / sum(el.values()))
    rows, same, g_rel, amounts_ok, mu_ok = [], True, None, True, True
    for ch in checks:
        q = ch.get("quantity")
        row = {k: ch.get(k) for k in ("quantity", "phase", "element", "species", "constituent", "unit") if ch.get(k)}
        row["reference"] = ch.get("value")
        if q == "integral_gibbs_energy":
            g_rel = rel_g(pred["G_total_J"], ch["value"])
            row.update(value=pred["G_total_J"], relative_difference=g_rel)
        elif q == "element_chemical_potential" and undetermined:
            row["note"] = "not compared: the stable compounds fix only sums of potentials, not this one"
        elif q == "element_chemical_potential":
            v = mu_lookup(pred["mu_J_per_mol"], ch.get("element"))
            ok = v is not None and within(v, ch["value"], ABS_MU)
            mu_ok &= ok
            row.update(value=v, within_tolerance=ok)
        elif q == "phase_moles":
            b = base(ch.get("phase") or "")
            sets = [s for s in pred["phases"] if base(s["phase"]) == b]
            if not sets:
                same = False
                row["note"] = "phase not present in Hephaestus's result"
            elif len(sets) > 1 or b not in ratio:
                amounts_ok = False
                row["note"] = ("phase appears more than once" if len(sets) > 1
                               else "Thermochimica's run gives no moles-to-atoms ratio for this phase")
            else:
                v = sets[0]["moles_of_atoms"] * ratio[b]
                ok = within(v, ch["value"], ABS_MOL)
                amounts_ok &= ok
                row.update(value=v, within_tolerance=ok, moles_per_atom_from_thermochimica_run=ratio[b])
        else:
            row["note"] = "not compared: not one of the protocol's four quantities"
        rows.append(row)
    for q in test.get("presence_checks", []):
        same &= base(q) in present
    if g_rel is None:
        return {"class": "not compared", "reason": "the test checks none of the protocol's quantities with a value",
                "checks": rows}
    return {"class": score(same, g_rel, amounts_ok, mu_ok), "checks": rows, "G_relative_difference": g_rel}


def run(sealed_dir, out_dir=HERE, predictions=HERE / "predictions.json", conditions=HERE / "conditions.json",
        hashes=HERE / "SEALED_HASHES.txt", manifest=HERE / "RAW_OUTPUT_MANIFEST.txt"):
    out_dir = Path(out_dir)
    if (out_dir / "comparison.json").exists():
        raise SystemExit("comparison.json already exists; the comparison runs once")
    sealed = Sealed(sealed_dir, hashes, manifest)
    pred = json.loads(Path(predictions).read_text(encoding="utf-8"))
    cond = json.loads(Path(conditions).read_text(encoding="utf-8"))
    category = {c["id"]: c["category"] for c in cond["conditions"]}
    for g in cond["extended_grid"]:
        category[g["id"]] = "equilibrium"
    results = sealed.results.get("results", {})

    runs = {}
    for pid, p in pred["points"].items():
        if category.get(pid) == "parse_only":
            continue
        runs[pid] = against_run(p, results.get(pid), sealed.raw(pid) if pid in results else None, category.get(pid))

    tests = {}
    for t in sealed.expected.get("tests", []):
        tid = t["test"]
        p = pred["points"].get(tid)
        if p is None:
            tests[tid] = {"class": "failed", "reason": "no prediction recorded for this test"}
            continue
        if tid == "TestThermo64":
            t = dict(t, presence_checks=["BCC_A2"])
        tests[tid] = against_expected(t, p, sealed.raw(tid) if tid in results else None, category.get(tid))

    out = {"engine": pred["engine"], "sealed_hashes_checked": True, "raw_files_checked": sealed.raw_checked,
           "summary": {"against_thermochimica_runs": dict(Counter(r["class"] for r in runs.values())),
                       "against_test_reference_values": dict(Counter(r["class"] for r in tests.values()))},
           "against_thermochimica_runs": runs, "against_test_reference_values": tests}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "comparison.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    (out_dir / "comparison.md").write_text(report(out), encoding="utf-8")
    return out


def report(out):
    lines = ["# Hephaestus against Thermochimica", "",
             f"Engine commit {out['engine']['commit']}; sealed hashes checked; "
             f"{out['raw_files_checked']} raw Thermochimica files checked against the manifest.", ""]
    for key, title in (("against_thermochimica_runs", "Against Thermochimica's runs (tests and extended grid)"),
                       ("against_test_reference_values", "Against the reference values in Thermochimica's tests")):
        lines += [f"## {title}", "", "| Class | Count |", "|---|---|"]
        lines += [f"| {k} | {v} |" for k, v in sorted(out["summary"][key].items())]
        lines += ["", "| Point | Class | Detail |", "|---|---|---|"]
        for pid, r in out[key].items():
            detail = r.get("reason") or ""
            if r.get("G_relative_difference") is not None:
                detail = f"G relative difference {r['G_relative_difference']:.2e}"
            if r.get("same_assemblage") is False:
                detail = f"phases {r['phases']} vs {r['reference_phases']}"
            lines.append(f"| {pid} | {r['class']} | {str(detail)[:160].replace('|', '/')} |")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    o = run(*sys.argv[1:])
    print(json.dumps(o["summary"], indent=1))
