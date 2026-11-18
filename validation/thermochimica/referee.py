"""Referee the disagreements of the unsealed comparison, each code judged by its own model.

Run after compare.py, so this is analysis, not a blind test. For every point compare.py classed
as disagree or close, the two answers are split into their phases and each phase's element
amounts are handed back to the other code as a problem of its own:

  A  Thermochimica on each Hephaestus phase, summed: Hephaestus's answer priced by Thermochimica.
  B  Hephaestus on each Thermochimica phase, summed: Thermochimica's answer priced by Hephaestus.

The pieces add up to the original bulk, so a sum is a state the pricing code's own model allows.
A below Thermochimica's own G means Thermochimica missed a lower state of its own model; B below
Hephaestus's own G means Hephaestus missed. A equal to Hephaestus's G (or B to Thermochimica's)
means the two read the database the same way on that state; otherwise they read it differently.

    python referee.py SEALED_DIR THERMOCHIMICA_DATA_DIR [ids...]

Writes referee.json and referee.md here; the Thermochimica runs go to referee_runs/.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "run"))
sys.path.insert(0, str(HERE))
from run_thermochimica import TC_WSL, Z, wsl_path  # noqa: E402
import predict  # noqa: E402
from mqmqa import gem  # noqa: E402

RUNS = HERE / "referee_runs"
DROP = 1e-12          # mol; an element below this in a piece is left out of that piece
ATM = 101325.0


def tol(G):
    return 1e-6 * abs(G) + 0.01


def tc_input(db, T, P, amounts, out):
    lines = [f"temperature       = {T!r}", f"pressure          = {P!r}"]
    lines += [f"mass({Z[el.capitalize()]})".ljust(18) + f"= {amt!r}" for el, amt in amounts.items()]
    lines += ["temperature unit  = K", "pressure unit     = atm", "mass unit         = moles",
              f"data file         = {TC_WSL}/data/{db}", "print mode        = 0",
              "heat capacity     = .FALSE.", "write json        = .TRUE.", f"output            = {out}"]
    return "\n".join(lines) + "\n"


def run_tc(jobs):
    """jobs: run id -> (database, T, P atm, amounts). Returns run id -> (integral G in J, stable
    phase names), or (None, []) when the run gave no result."""
    RUNS.mkdir(exist_ok=True)
    for rid, (db, T, P, amt) in jobs.items():
        (RUNS / f"{rid}.ti").write_text(tc_input(db, T, P, amt, f"{wsl_path(RUNS)}/{rid}.json"), newline="\n")
    script = f"""#!/usr/bin/env bash
source ~/miniforge3/etc/profile.d/conda.sh
conda activate thermochimica
cd {TC_WSL}
for f in {wsl_path(RUNS)}/*.ti; do
  id=$(basename "$f" .ti)
  if [ ! -f "{wsl_path(RUNS)}/$id.json" ]; then
    timeout 120 ./bin/InputScriptMode "$f" > "{wsl_path(RUNS)}/$id.log" 2>&1
  fi
done
"""
    (RUNS / "run.sh").write_text(script, newline="\n")
    r = subprocess.run(["wsl", "bash", wsl_path(RUNS / "run.sh")], capture_output=True, text=True)
    if r.returncode:
        print("Thermochimica runs:", r.returncode, r.stderr[-500:])
    out = {}
    for rid in jobs:
        p = RUNS / f"{rid}.json"
        try:
            d = json.loads(p.read_text())["1"]
            out[rid] = (d["integral Gibbs energy"], [n for n, _ in tc_pieces(d)])
        except Exception:
            out[rid] = (None, [])
    return out


def tc_pieces(raw):
    """Element amounts of each stable phase of a Thermochimica result."""
    pieces = []
    for kind in ("solution phases", "pure condensed phases"):
        for name, ph in raw.get(kind, {}).items():
            if ph.get("moles", 0) > 0:
                amt = {el: v["moles of element in phase"] for el, v in ph["elements"].items()
                       if v["moles of element in phase"] > DROP}
                pieces.append((name, amt))
    return pieces


def base(name):
    return name.split("#")[0].upper()


def exact(phase, returned):
    """A piece's price is the phase's own energy when the run gave back that phase alone."""
    return len(returned) == 1 and base(returned[0]) == base(phase)


def main():
    sealed, data = Path(sys.argv[1]), Path(sys.argv[2])
    only = set(sys.argv[3:])
    comp = json.loads((HERE / "comparison.json").read_text(encoding="utf-8"))["against_thermochimica_runs"]
    pred = json.loads((HERE / "predictions.json").read_text(encoding="utf-8"))["points"]
    cond = json.loads((HERE / "conditions.json").read_text(encoding="utf-8"))
    cs = {c["id"]: c for c in cond["conditions"] + cond["extended_grid"]}
    ids = [k for k, v in comp.items() if v.get("class") in ("disagree", "close") and "G_J" in v
           and (not only or k in only)]

    jobs, plan = {}, {}
    for pid in ids:
        p = pred[pid]
        raw = json.loads((sealed / "thermochimica_raw" / f"{pid}.json").read_text())["1"]
        T, P = p["T_K"], p["P_atm"]
        db = cs[pid]["database"]
        a = []
        for k, s in enumerate(p["phases"]):
            amt = {el: f * s["moles_of_atoms"] for el, f in s["x"].items() if f * s["moles_of_atoms"] > DROP}
            rid = f"{pid}__A{k}"
            jobs[rid] = (db, T, P, amt)
            a.append((rid, s["phase"], amt))
        plan[pid] = dict(db=db, T=T, P=P, a=a, b=tc_pieces(raw),
                         G_hep=p["G_total_J"], G_tc=raw["integral Gibbs energy"])
    tc = run_tc(jobs)

    out = {}
    for pid, q in plan.items():
        A = [tc[rid][0] for rid, _, _ in q["a"]]
        A_ph = [tc[rid][1] for rid, _, _ in q["a"]]
        dbh = predict.load(data, q["db"])
        B, B_ph = [], []
        for name, amt in q["b"]:
            try:
                r = gem.equilibrium(dbh, q["T"], amt, P=q["P"] * ATM)
                B.append(r.G * sum(amt.values()))
                B_ph.append([s.phase for s in r.sets if s.amount > 1e-12])
            except Exception as e:
                B.append(None)
                B_ph.append([])
                print(pid, name, "Hephaestus refused the piece:", e)
        rec = dict(T_K=q["T"], P_atm=q["P"], G_hephaestus=q["G_hep"], G_thermochimica=q["G_tc"],
                   A_hephaestus_state_in_thermochimica=None if None in A else sum(A),
                   B_thermochimica_state_in_hephaestus=None if None in B else sum(B),
                   A_pieces=[dict(phase=ph, amounts=amt, G=g, returned=r)
                             for (_, ph, amt), g, r in zip(q["a"], A, A_ph)],
                   B_pieces=[dict(phase=ph, amounts=amt, G=g, returned=r)
                             for (ph, amt), g, r in zip(q["b"], B, B_ph)])
        A_exact = all(exact(p["phase"], p["returned"]) for p in rec["A_pieces"])
        B_exact = all(exact(p["phase"], p["returned"]) for p in rec["B_pieces"])
        Gh, Gt = q["G_hep"], q["G_tc"]
        At, Bt = rec["A_hephaestus_state_in_thermochimica"], rec["B_thermochimica_state_in_hephaestus"]
        verdict = []
        if At is not None and At < Gt - tol(Gt):
            verdict.append("Thermochimica missed a lower state of its own model")
        if Bt is not None and Bt < Gh - tol(Gh):
            verdict.append("Hephaestus missed a lower state of its own model")
        for label, price, own, ok in (("Hephaestus's", At, Gh, A_exact), ("Thermochimica's", Bt, Gt, B_exact)):
            if price is None:
                verdict.append(f"{label} state not priced")
            elif not ok:
                verdict.append(f"{label} state priced only as a bound (a piece came back as other phases)")
            else:
                d = price - own
                verdict.append(f"same reading on {label} state" if abs(d) <= tol(own)
                               else f"readings differ on {label} state by {d:+.3f} J")
        rec["verdict"] = verdict
        out[pid] = rec

    (HERE / "referee.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    rows = ["# Referee of the disagreements", "",
            "A = Hephaestus's answer priced by Thermochimica; B = Thermochimica's answer priced by Hephaestus. "
            "J, for the whole system.", "",
            "| Point | G Hephaestus | G Thermochimica | A | B | Verdict |", "|---|---|---|---|---|---|"]
    f = lambda v: "n/a" if v is None else f"{v:.3f}"
    for pid, r in out.items():
        rows.append(f"| {pid} | {f(r['G_hephaestus'])} | {f(r['G_thermochimica'])} | "
                    f"{f(r['A_hephaestus_state_in_thermochimica'])} | {f(r['B_thermochimica_state_in_hephaestus'])} | "
                    f"{'; '.join(r['verdict'])} |")
    (HERE / "referee.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print("\n".join(rows))


if __name__ == "__main__":
    main()
