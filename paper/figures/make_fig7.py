"""Figure 7: the gas calculator as a steelmaking worked example.

The furnace atmosphere over a steel bath is a CO-CO2 gas, and its CO/CO2 ratio fixes
the oxygen partial pressure that decides whether carbon is removed (decarburization) or
iron is oxidized into the slag. Both panels are the equilibrium of a carbon-oxygen gas
computed by the Hephaestus gas engine (python/mqmqa/gas.py, the same element-potential
solver compiled into the browser), validated point for point against Cantera.

(a) Oxygen potential set by the CO/CO2 ratio at the 1873 K tap temperature.
(b) Oxygen potential against temperature for four fixed CO/CO2 buffers.

Greyscale, >=600 DPI, no baked text; the caption carries the description.
"""
import math
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "python"))
from mqmqa.gas import read_nasa_thermo, gas_equilibrium  # noqa: E402

SP = read_nasa_thermo(str(HERE.parent.parent / "data" / "gas" / "nasa_gas.dat"))
NAMES = ["CO", "CO2", "O2"]
P = 101325.0
T_TAP = 1873.0   # 1600 degC, steel tap temperature


def feed_for_ratio(R):
    """Element budget C,O for a gas that is CO:CO2 = R (O2 is a trace product)."""
    return R + 1.0, R + 2.0


def pO2(T, C, O):
    f = gas_equilibrium(SP, NAMES, T, P, {"C": C, "O": O})
    return f["O2"] * P / P, f  # x_O2 (== pO2/P in atm since P=1 atm)


def try_cantera():
    try:
        import cantera as ct
        return ct.Solution("gri30.yaml")
    except Exception:
        return None


def main():
    g = try_cantera()
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(9.2, 4.0))

    # ---- panel (a): log10 pO2 vs CO/CO2 ratio at the tap temperature ----
    ratios = np.logspace(-1, 2, 60)   # 0.1 .. 100
    y = []
    for R in ratios:
        C, O = feed_for_ratio(R)
        f = gas_equilibrium(SP, NAMES, T_TAP, P, {"C": C, "O": O})
        y.append(math.log10(max(f["O2"], 1e-30)))
    axA.plot(ratios, y, color="black", lw=1.8, zorder=3)
    # Cantera validation markers
    if g is not None:
        rr = [0.2, 0.5, 1, 3, 10, 40]
        yy = []
        for R in rr:
            C, O = feed_for_ratio(R)
            g.TPX = T_TAP, P, {"CO": 2 * C - O, "CO2": O - C}
            g.equilibrate("TP")
            yy.append(math.log10(max(g.X[g.species_index("O2")], 1e-30)))
        axA.scatter(rr, yy, s=34, facecolors="none", edgecolors="0.35",
                    linewidths=1.3, zorder=4, label="Cantera")
        axA.plot([], [], color="black", lw=1.8, label="Hephaestus")
        axA.legend(frameon=False, fontsize=9, loc="lower left",
                   bbox_to_anchor=(0.0, 0.0), handletextpad=0.5)
    axA.set_xscale("log")
    axA.set_xlabel("CO / CO$_2$ ratio")
    axA.set_ylabel(r"log$_{10}$ ( $p_{\mathrm{O_2}}$ / atm )")
    axA.set_title("(a)  Oxygen potential at 1873 K", fontsize=11)
    # oxygen-potential direction: up is oxidizing, down is reducing (short cues; the
    # metallurgical consequence lives in the caption to keep the panel uncrowded)
    ylo, yhi = axA.get_ylim()
    axA.annotate("more oxidizing", xy=(30, yhi - 0.05 * (yhi - ylo)),
                 ha="center", va="top", fontsize=9, color="0.3", style="italic")
    axA.annotate("more reducing", xy=(4.5, ylo + 0.14 * (yhi - ylo)),
                 ha="center", va="bottom", fontsize=9, color="0.3", style="italic")

    # ---- panel (b): log10 pO2 vs T for fixed CO/CO2 buffers ----
    # steelmaking range; below ~1600 K the trace O2 falls under the solver floor and wobbles
    Ts = np.linspace(1600, 2100, 70)
    styles = {10: ("-", "10 : 1"), 3: ("--", "3 : 1"), 1: ("-.", "1 : 1"),
              1 / 3: (":", "1 : 3")}
    for R, (ls, lab) in styles.items():
        C, O = feed_for_ratio(R)
        yy = [math.log10(max(gas_equilibrium(SP, NAMES, T, P, {"C": C, "O": O})["O2"], 1e-30))
              for T in Ts]
        axB.plot(Ts, yy, color="black", lw=1.6, ls=ls, label="CO/CO$_2$ = " + lab)
    if g is not None:
        for R in (10, 1):
            C, O = feed_for_ratio(R)
            for T in (1600, 1800, 2000):
                g.TPX = T, P, {"CO": 2 * C - O, "CO2": O - C}
                g.equilibrate("TP")
                axB.scatter([T], [math.log10(max(g.X[g.species_index("O2")], 1e-30))],
                            s=30, facecolors="none", edgecolors="0.35", linewidths=1.2, zorder=4)
    axB.axvline(T_TAP, color="0.55", lw=1.0, ls=(0, (2, 2)))
    axB.annotate("1873 K tap", xy=(T_TAP, axB.get_ylim()[0]), xytext=(T_TAP - 20, axB.get_ylim()[0] + 0.4),
                 ha="right", va="bottom", fontsize=8.5, color="0.3", rotation=90)
    axB.set_xlabel("Temperature (K)")
    axB.set_ylabel(r"log$_{10}$ ( $p_{\mathrm{O_2}}$ / atm )")
    axB.set_title("(b)  Fixed-buffer oxygen potential", fontsize=11)
    axB.legend(frameon=False, fontsize=8.5, loc="lower right")

    for ax in (axA, axB):
        ax.tick_params(labelsize=9)
        for sp_ in ax.spines.values():
            sp_.set_linewidth(0.8)

    fig.tight_layout()
    out = HERE / "fig7_gas_steel.png"
    fig.savefig(out, dpi=600, facecolor="white")
    print("fig7_gas_steel.png written", out.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
