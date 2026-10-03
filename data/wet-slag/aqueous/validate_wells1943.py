"""The model against the measured CaO-Al2O3-H2O solubility curves of Wells, Clarke & McMurdie 1943
(J Res NBS 30:367, doi:10.6028/jres.030.027), tables in validation/.

For each measured solution (Ca and Al as measured, pH by charge balance) the saturation index of the
solid the authors identified: 0 means the model agrees the solution is at equilibrium with it. Our log K are 25 C values without a temperature term, run at the 21 C of
the experiments. Hexagonal hydrates (Tables 1-2) were a metastable C2AH8 + C4AH13 mixture, so both
model curves are reported.

Run in the calphad env after derive_logk.py.
"""
import csv
import math
from pathlib import Path

from phreeqpython import PhreeqPython

HERE = Path(__file__).resolve().parent
VAL = HERE / "validation"
pp = PhreeqPython(database=str(HERE / "phreeqc_slag.dat"))


def rows(name, keep=lambda r: True):
    with open(VAL / name, newline="", encoding="utf-8") as fh:
        return [r for r in csv.DictReader(line for line in fh if not line.startswith("#")) if keep(r)]


def al_at_saturation(ca_mm, phase, temp):
    """Dissolved Al (mmol/kgw) at which the solution saturates in `phase`, at the measured Ca with pH
    from charge balance: a bisection on log Al (PHREEQC does not converge with both adjustments)."""
    def si(log_al):
        sol = pp.add_solution({"temp": temp, "units": "mmol/kgw", "pH": "12 charge",
                               "Ca": ca_mm, "Al": 10 ** log_al})
        out = sol.si(phase), sol.pH
        sol.forget()
        return out
    lo, hi = -6.0, math.log10(2 * ca_mm) - 1e-6       # Al(OH)4- cannot outrun the Ca charge
    if si(lo)[0] > 0 or si(hi)[0] < 0:
        return float("nan"), float("nan")
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        lo, hi = (lo, mid) if si(mid)[0] > 0 else (mid, hi)
    return 10 ** lo, si(lo)[1]


def compare(title, data, phases):
    """Saturation index of each phase at every measured solution (Ca, Al as measured, pH by charge
    balance): 0 means the model agrees the solution is at equilibrium with that solid."""
    print(f"\n{title}")
    stats = {p: [] for p in phases}
    for r in data:
        ca, al = float(r["final_Ca_mmol_per_L"]), float(r["final_Al_mmol_per_L"])
        if ca <= 0 or al <= 0:
            continue
        sol = pp.add_solution({"temp": float(r["temperature_C"]), "units": "mmol/kgw",
                               "pH": "12 charge", "Ca": ca, "Al": al})
        sis = {p: sol.si(p) for p in phases}
        ph = sol.pH
        sol.forget()
        for p in phases:
            stats[p].append(sis[p])
        print(f"  Ca {ca:7.3f}  Al {al:8.3f}  pH {ph:5.2f}   SI " +
              "  ".join(f"{p} {sis[p]:+6.2f}" for p in phases))
    for p, d in stats.items():
        if d:
            mean = sum(d) / len(d)
            rms = math.sqrt(sum(x * x for x in d) / len(d))
            print(f"  {p:12s} n={len(d):2d}  SI at the measured solutions: mean {mean:+.2f}, rms {rms:.2f}")


def main():
    compare("C3AH6 at 21 C (Table 7)", rows("wells1943_table7_C3AH6_21C.csv"), ["C3AH6"])
    compare("Gibbsite at 21 C (Table 8, authors' equilibrium points)",
            rows("wells1943_table8_gibbsite_21C.csv", lambda r: r["equilibrium_per_authors"] == "yes"),
            ["Gibbsite", "Gibbsite_C18", "Al(OH)3(mic)"])
    compare("Hexagonal C2AH8 + C4AH13 at 21 C, metastable (Table 2, from undersaturation)",
            rows("wells1943_table2_hexagonal_CAH_undersaturation_21C.csv"), ["C2AH7_5", "C4AH13"])


if __name__ == "__main__":
    main()
