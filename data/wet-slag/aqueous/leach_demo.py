"""Each anhydrous slag solid in 1 kg of pure water at 25 C: up to 0.1 mol may dissolve, and the
hydrates that form at room temperature may precipitate, all in one equilibrium.

Secondary phases follow Cemdata18's guidance for 20-25 C: its slow formers (gibbsite, quartz, the
Si-hydrogarnets) are left out, and so are serpentine, talc and kaolinite. C-S-H is Cemdata18's
recommended CSHQ model (Kulik 2011), an ideal solid solution of four endmembers. (Its older CSH-II
model, taken as ideal mixing per formula unit, does not coexist with portlandite above Ca/Si 0.9.) With
--long-term the slow phases are allowed too. Equilibrium only: no dissolution rates.

Run in the calphad env after derive_logk.py.
"""
import sys
from pathlib import Path

from phreeqpython import PhreeqPython

HERE = Path(__file__).resolve().parent
SLAG = ["Lime", "Larnite", "Hatrurite", "Wollastonite", "Rankinite", "CaAl2O4", "CaAl4O7",
        "Ca3Al2O6", "Gehlenite", "Anorthite_H", "Forsterite_H", "Enstatite_H", "Diopside_H", "Spinel"]
FAST = ["Portlandite", "Al(OH)3(mic)", "SiO2(am)", "Brucite", "C3AH6", "C4AH13", "C4AH19",
        "C2AH7_5", "CAH10", "Straetlingite", "MSH_0_75", "MSH_1_5"]
SLOW = ["Gibbsite", "Quartz", "C3AS0_41H5_18", "C3AS0_84H4_32", "Chrysotile", "Talc", "Kaolinite"]
# CSHQ endmember: (Ca, Si) per formula
CSH = {"CSHQ_TobH": (2 / 3, 1), "CSHQ_TobD": (5 / 6, 2 / 3), "CSHQ_JenH": (4 / 3, 1), "CSHQ_JenD": (1.5, 2 / 3)}


def run(pp, slag, secondary):
    eq = "\n".join([f"    {slag} 0 0.1"] + [f"    {p} 0 0" for p in secondary])
    out = " ".join([slag] + secondary)
    pp.ip.run_string(f"""
KNOBS
    -iterations 400
    -diagonal_scale true
SOLUTION 1
    temp 25
EQUILIBRIUM_PHASES 1
{eq}
SOLID_SOLUTIONS 1
    CSHQ
{chr(10).join(f"        -comp {c} 0" for c in CSH)}
SELECTED_OUTPUT 1
    -reset false
    -pH true
    -totals Ca Al Si Mg
    -equilibrium_phases {out}
    -solid_solutions {' '.join(CSH)}
END
""")
    arr = pp.ip.get_selected_output_array()
    return dict(zip(arr[0], arr[-1]))


def main():
    secondary = FAST + (SLOW if "--long-term" in sys.argv else [])
    pp = PhreeqPython(database=str(HERE / "phreeqc_slag.dat"))
    print(f"{'solid':13s} {'pH':>6s} {'Ca mM':>8s} {'Al mM':>8s} {'Si mM':>8s} {'Mg mM':>7s} "
          f"{'dissolved':>9s}  formed (mmol)")
    for s in SLAG:
        r = run(pp, s, secondary)
        mm = lambda el: 1000 * float(r.get(f"{el}(mol/kgw)", 0.0))
        formed = [f"{p} {1000 * float(r[p]):.1f}" for p in secondary if float(r.get(p, 0.0)) > 1e-7]
        n = {c: 1000 * float(r.get(f"s_{c}", 0.0)) for c in CSH}
        si = sum(n[c] * CSH[c][1] for c in CSH)
        if si > 1e-4:
            ca = sum(n[c] * CSH[c][0] for c in CSH)
            formed.append(f"C-S-H {si:.1f} mmol Si (Ca/Si {ca / si:.2f})")
        print(f"{s:13s} {float(r['pH']):6.2f} {mm('Ca'):8.3f} {mm('Al'):8.4f} {mm('Si'):8.3f} "
              f"{mm('Mg'):7.3f} {-1000 * float(r.get(f'd_{s}', 0.0)):9.1f}  {', '.join(formed)}")


if __name__ == "__main__":
    main()
