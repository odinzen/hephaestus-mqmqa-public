"""The model against measured M-S-H solubility (Nied et al. 2016) and BOF slag leachates (Stewart et
al. 2018), tables in validation/.

Nied 2016, Table 5 (20 C, 1 year): at each measured solution (Si, Mg, pH as measured) our saturation
indices of amorphous silica and brucite against the authors' own (GEMS, Cemdata), and the M-S-H solid
solution's saturation, log10(sum of 10^SI over its endmembers), 0 for an ideal solid solution at
equilibrium.

Stewart 2018, SI Table S2 (BOF slag in water, about 20 C, open to air, 0-73 days): saturation of
portlandite and of the CSHQ C-S-H at each measured leachate, and the Ca/Si of the C-S-H that would be
in equilibrium with it (endmember fractions proportional to 10^SI), against the C-S-H they measured
by SEM-EDS after 73 days (Table 2).

Run in the calphad env after derive_logk.py.
"""
import csv
import math
from pathlib import Path

from phreeqpython import PhreeqPython

HERE = Path(__file__).resolve().parent
VAL = HERE / "validation"
pp = PhreeqPython(database=str(HERE / "phreeqc_slag.dat"))
CSHQ = {"CSHQ_TobH": (2 / 3, 1), "CSHQ_TobD": (5 / 6, 2 / 3), "CSHQ_JenH": (4 / 3, 1), "CSHQ_JenD": (1.5, 2 / 3)}
MSH = ["MSH_0_75", "MSH_1_5"]


def rows(name):
    with open(VAL / name, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(line for line in fh if not line.startswith("#")))


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0                                          # "DL" (below detection) and blanks


def ss_saturation(sol, members):
    si = {m: sol.si(m) for m in members}
    return math.log10(sum(10 ** v for v in si.values())), si


def nied():
    print("Nied et al. 2016, M-S-H at 20 C (SI ours / authors')")
    for r in rows("nied2016_msh_table5.csv"):
        sol = pp.add_solution({"temp": 20, "units": "mmol/kgw", "pH": num(r["pH"]),
                               "Si": num(r["Si_mM"]), "Mg": num(r["Mg_mM"])})
        ss, _ = ss_saturation(sol, MSH)
        print(f"  Mg/Si solid {r['Mg_Si_solid_MSH']:>4s}  pH {r['pH']:>4s}  SiO2(am) {sol.si('SiO2(am)'):+5.2f} / "
              f"{r['SI_SiO2am']:>4s}   brucite {sol.si('Brucite'):+5.2f} / {r['SI_brucite']:>4s}   "
              f"M-S-H solid solution {ss:+5.2f}   ({r['solid_phases']})")
        sol.forget()


def stewart():
    print("\nStewart et al. 2018, BOF slag leachates (~20 C, open to air, not at equilibrium)")
    print(f"  {'fraction':28s} {'day':>3s} {'pH':>5s} {'Ca mM':>6s} {'Si mM':>6s}  SI(CH)  SI(C-S-H)  C-S-H Ca/Si in eq.")
    eq_ratio = {}
    for r in rows("stewart2018_bof_leachate_tableS2.csv"):
        if not r["pH"] or num(r["Si_mmol_per_L"]) <= 0 or num(r["Ca_mmol_per_L"]) <= 0:
            continue
        sol = pp.add_solution({"temp": 20, "units": "mmol/kgw", "pH": num(r["pH"]),
                               **{el: num(r[f"{el}_mmol_per_L"]) for el in ("Ca", "Si", "Al", "Mg", "Na", "K")}})
        ss, si = ss_saturation(sol, CSHQ)
        w = {m: 10 ** v for m, v in si.items()}
        ratio = sum(w[m] * CSHQ[m][0] for m in w) / sum(w[m] * CSHQ[m][1] for m in w)
        if int(float(r["day"])) >= 14:
            eq_ratio.setdefault(r["size_fraction"].split()[0], []).append(ratio)
        print(f"  {r['size_fraction']:28s} {r['day']:>3s} {r['pH']:>5s} {num(r['Ca_mmol_per_L']):6.3f} "
              f"{num(r['Si_mmol_per_L']):6.3f}  {sol.si('Portlandite'):+5.2f}   {ss:+5.2f}      {ratio:.2f}")
        sol.forget()
    print("\n  C-S-H Ca/Si: model, in equilibrium with the day >= 14 leachates, vs measured by SEM-EDS at 73 d")
    measured = {r["size_fraction"].split()[0]: r for r in rows("stewart2018_bof_ca_si_ratios_table2.csv")
                if r["phase"] == "Ca-Si-H surface layer"}
    for frac, vals in eq_ratio.items():
        m = measured.get(frac)
        mtxt = f"{m['Ca_Si']} +- {m['Ca_Si_1SD']}" if m else "n/a"
        print(f"  {frac:8s} model {sum(vals) / len(vals):.2f} (n={len(vals)})   measured surface layer {mtxt}")


if __name__ == "__main__":
    nied()
    stewart()
