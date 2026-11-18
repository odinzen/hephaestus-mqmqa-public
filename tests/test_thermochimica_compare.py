"""The Thermochimica comparison script, on made-up sealed files with planted differences.

Nothing here reads the real sealed folder; every reference value is invented so that each
class in PROTOCOL.md is hit once and the hash checks are seen to refuse tampered files."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("tc_compare", HERE.parent / "validation" / "thermochimica" / "compare.py")
cmp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cmp)

MU = {"O": -227985.0, "C": -1722.0}


def ours(G, phases, mu=MU, cls="computed"):
    return {"class": cls, "G_total_J": G, "mu_J_per_mol": dict(mu),
            "phases": [{"phase": n, "moles_of_atoms": a, "x": x} for n, a, x in phases]}


def raw(G, phases, mu=MU, amounts=(("O", 1.0), ("C", 1.0))):
    """Thermochimica-shaped output, with phases given as (group, name, moles, {element: moles in phase})."""
    d = {"solution phases": {}, "pure condensed phases": {}, "integral Gibbs energy": G,
         "elements": {e: {"moles": n, "element potential": mu[e]} for e, n in amounts}}
    for group, name, moles, els in phases:
        d[group][name] = {"moles": moles, "elements": {e: {"moles of element in phase": v} for e, v in els.items()}}
    return {"1": d}


GAS = ("solution phases", "gas_ideal")
GR = ("pure condensed phases", "C_Graphite(s)")
G0 = -229707.8


def base_point():
    p = ours(G0, [("GAS_IDEAL", 1.5, {"O": 2 / 3, "C": 1 / 3}), ("C_GRAPHITE(S)", 0.5, {"C": 1.0})])
    r = raw(G0, [(*GAS, 0.75, {"O": 1.0, "C": 0.5}), (*GR, 0.5, {"C": 0.5})])
    return p, r


def build(tmp_path):
    preds, raws, results = {}, {}, {}

    def add(pid, p, r, status="ok"):
        preds[pid] = p
        if r is not None:
            raws[pid] = r
        results[pid] = {"status": status}

    p, r = base_point()
    add("same", p, r)
    p, r = base_point()
    p["G_total_J"] = G0 * (1 + 5e-6)
    add("g_close", p, r)
    p, r = base_point()
    p["G_total_J"] = G0 * (1 + 5e-4)
    add("g_far", p, r)
    p, r = base_point()
    p["phases"][1]["phase"] = "C_DIAMOND(S2)"
    add("other_phase", p, r)
    p, r = base_point()
    p["mu_J_per_mol"]["O"] += 50.0
    add("mu_off", p, r)
    p, r = base_point()
    p["phases"][0]["moles_of_atoms"] *= 1 + 1e-3
    add("amount_off", p, r)
    # a miscibility gap listed in the other order on each side, paired by composition
    p = ours(G0, [("LIQN", 1.2, {"O": 0.9, "C": 0.1}), ("LIQN", 0.8, {"O": 0.1, "C": 0.9})])
    r = raw(G0, [("solution phases", "LIQN", 0.8, {"O": 0.08, "C": 0.72}),
                 ("solution phases", "LIQN#2", 1.2, {"O": 1.08, "C": 0.12})])
    add("gap", p, r)
    add("we_refuse", {"class": "refused", "reason": "phase SUBM is not read"}, base_point()[1])
    add("they_fail", base_point()[0], None, status="failed")
    add("TestBad", {"class": "refused", "reason": "input not accepted"}, None, status="failed")
    p, r = base_point()
    add("TestPhase", p, r)
    # two copies of one phase at one composition are one set, on either side
    p = ours(G0, [("HCPN", 2.0, {"O": 0.5, "C": 0.5})])
    r = raw(G0, [("solution phases", "HCPN", 0.4, {"O": 0.2, "C": 0.2}),
                 ("solution phases", "HCPN#2", 1.6, {"O": 0.8, "C": 0.8})])
    add("copies", p, r)
    p = ours(G0, [("HCPN", 0.5, {"O": 0.5, "C": 0.5}), ("HCPN", 1.5, {"O": 0.5, "C": 0.5})])
    add("our_copies", p, raw(G0, [("solution phases", "HCPN", 2.0, {"O": 1.0, "C": 1.0})]))
    # solid CsI alone fixes mu(Cs) + mu(I) only; the codes may split the sum differently
    gc = -441869.33
    csi = ours(gc, [("CSI_CSI_B2(S)", 2.0, {"CS": 0.5, "I": 0.5})], mu={"CS": -349328.28, "I": -92541.05})
    csi_amounts = (("Cs", 1.0), ("I", 1.0))
    add("TestCompound", csi, raw(gc, [("pure condensed phases", "CsI_CsI_B2(s)", 1.0, {"Cs": 1.0, "I": 1.0})],
                                 mu={"Cs": -300000.0, "I": -141869.33}, amounts=csi_amounts))
    add("compound_sum_off", csi, raw(gc, [("pure condensed phases", "CsI_CsI_B2(s)", 1.0, {"Cs": 1.0, "I": 1.0})],
                                     mu={"Cs": -300000.0, "I": -141769.33}, amounts=csi_amounts))

    sealed = tmp_path / "sealed"
    (sealed / "thermochimica_raw").mkdir(parents=True)
    manifest_lines = []
    for pid, r in raws.items():
        f = sealed / "thermochimica_raw" / f"{pid}.json"
        f.write_text(json.dumps(r), encoding="utf-8")
        manifest_lines.append(f"{hashlib.sha256(f.read_bytes()).hexdigest()} *./{pid}.json")
    manifest = tmp_path / "RAW_OUTPUT_MANIFEST.txt"
    manifest.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    expected = {"tests": [
        {"test": "TestPhase", "checks": [
            {"quantity": "integral_gibbs_energy", "unit": "J", "value": G0},
            # graphite is one atom per formula unit; the gas holds 1.5 atoms in 0.75 mol of species
            {"quantity": "phase_moles", "unit": "mol", "phase": "gas_ideal", "value": 0.75},
            {"quantity": "phase_moles", "unit": "mol", "phase": "C_Graphite(s)", "value": 0.5},
            {"quantity": "element_chemical_potential", "unit": "J/mol", "element": "O", "value": MU["O"]},
            {"quantity": "mole_fraction", "unit": "", "phase": "gas_ideal", "species": "CO", "value": 0.5}]},
        {"test": "g_far", "checks": [{"quantity": "integral_gibbs_energy", "unit": "J", "value": G0}]},
        {"test": "TestBad", "checks": []},
        {"test": "TestCompound", "checks": [
            {"quantity": "integral_gibbs_energy", "unit": "J", "value": gc},
            {"quantity": "element_chemical_potential", "unit": "J/mol", "element": "Cs", "value": -300000.0}]}]}
    (sealed / "expected.json").write_text(json.dumps(expected), encoding="utf-8")
    (sealed / "thermochimica_results.json").write_text(json.dumps({"results": results}), encoding="utf-8")
    hashes = tmp_path / "SEALED_HASHES.txt"
    hashes.write_text("".join(f"{hashlib.sha256((sealed / n).read_bytes()).hexdigest()}  {n}\n"
                              for n in ("expected.json", "thermochimica_results.json"))
                      + f"{hashlib.sha256(manifest.read_bytes()).hexdigest()}  RAW_OUTPUT_MANIFEST.txt\n",
                      encoding="utf-8")
    pred_path = tmp_path / "predictions.json"
    pred_path.write_text(json.dumps({"engine": {"commit": "test"}, "points": preds}), encoding="utf-8")
    cond = {"conditions": [{"id": k, "category": "input_validation" if k == "TestBad" else "equilibrium"}
                           for k in preds], "extended_grid": []}
    cond_path = tmp_path / "conditions.json"
    cond_path.write_text(json.dumps(cond), encoding="utf-8")
    return dict(sealed_dir=sealed, out_dir=tmp_path / "out", predictions=pred_path, conditions=cond_path,
                hashes=hashes, manifest=manifest)


def test_each_class_is_reached(tmp_path):
    out = cmp.run(**build(tmp_path))
    runs = {k: v["class"] for k, v in out["against_thermochimica_runs"].items()}
    assert runs == {"same": "agree", "g_close": "close", "g_far": "disagree", "other_phase": "disagree",
                    "mu_off": "close", "amount_off": "close", "gap": "agree", "we_refuse": "refused",
                    "they_fail": "no reference", "TestBad": "refused", "TestPhase": "agree",
                    "TestCompound": "agree", "compound_sum_off": "close", "copies": "agree", "our_copies": "agree"}
    assert out["against_thermochimica_runs"]["TestCompound"]["potentials_undetermined"]
    # a single potential the compound leaves open is listed, not scored
    rows = out["against_test_reference_values"]["TestCompound"]["checks"]
    assert out["against_test_reference_values"]["TestCompound"]["class"] == "agree"
    assert "not compared" in next(r for r in rows if r["quantity"] == "element_chemical_potential")["note"]
    assert out["against_thermochimica_runs"]["TestBad"]["as_the_test_requires"]
    assert out["against_thermochimica_runs"]["we_refuse"]["as_the_test_requires"] is False
    assert out["raw_files_checked"] > 0
    assert (tmp_path / "out" / "comparison.md").exists()


def test_reference_values_convert_phase_moles_with_thermochimicas_own_ratio(tmp_path):
    out = cmp.run(**build(tmp_path))["against_test_reference_values"]
    assert out["TestPhase"]["class"] == "agree"
    rows = {(r["quantity"], r.get("phase")): r for r in out["TestPhase"]["checks"]}
    assert rows[("phase_moles", "gas_ideal")]["value"] == pytest.approx(0.75, rel=1e-12, abs=0)
    assert "not compared" in rows[("mole_fraction", "gas_ideal")]["note"]
    assert out["g_far"]["class"] == "disagree"
    assert out["TestBad"]["class"] == "refused" and out["TestBad"]["as_the_test_requires"]


def test_a_wrong_phase_amount_against_the_test_is_not_agree(tmp_path):
    paths = build(tmp_path)
    e = json.loads((paths["sealed_dir"] / "expected.json").read_text())
    e["tests"][0]["checks"][1]["value"] = 0.76
    (paths["sealed_dir"] / "expected.json").write_text(json.dumps(e))
    paths["hashes"].write_text(paths["hashes"].read_text().replace(
        paths["hashes"].read_text().split()[0], hashlib.sha256((paths["sealed_dir"] / "expected.json").read_bytes()).hexdigest()))
    assert cmp.run(**paths)["against_test_reference_values"]["TestPhase"]["class"] == "close"


@pytest.mark.parametrize("victim", ["expected.json", "thermochimica_results.json", "thermochimica_raw/same.json"])
def test_tampered_sealed_files_are_refused(tmp_path, victim):
    paths = build(tmp_path)
    f = paths["sealed_dir"] / victim
    f.write_text(f.read_text() + " ", encoding="utf-8")
    with pytest.raises(cmp.SealError):
        cmp.run(**paths)
    assert not (paths["out_dir"] / "comparison.json").exists()


def test_it_runs_once(tmp_path):
    paths = build(tmp_path)
    cmp.run(**paths)
    with pytest.raises(SystemExit):
        cmp.run(**paths)
