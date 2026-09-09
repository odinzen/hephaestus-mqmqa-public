"""Figure 8: the gas-flux coupling as a molten-salt worked example.

A molten chloride flux fumes because its own components evaporate, each at its activity
times its pure-component vapour pressure. The engine supplies the activities (python/mqmqa/
gas_flux.py: partial molar on the C equilibrium solver, checked against the pure limit and
the near-ideal NaCl-KCl binary); measured data supply the pure-component vapour pressures
(NaCl, KCl NIST Antoine; MgCl2 NIST-JANAF), each reproducing its boiling point.

(a) Fume partial pressures over the NaCl-KCl-MgCl2 = 40/40/20 mol% flux against temperature.
(b) Flux composition against fume composition at 1200 K: MgCl2 is a fifth of the flux but a
    few percent of the fume, because chlorocomplexing holds its activity below its mole fraction.

Greyscale, >=600 DPI, no baked text; the caption carries the description.
"""
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "python"))
from mqmqa import gas_flux  # noqa: E402

FLUX = {"NaCl": 0.4, "KCl": 0.4, "MgCl2": 0.2}
ORDER = ["NaCl", "KCl", "MgCl2"]
LABEL = {"NaCl": "NaCl", "KCl": "KCl", "MgCl2": "MgCl$_2$"}


def main():
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(9.2, 4.0))

    # ---- panel (a): fume partial pressures p_i = a_i p_i^o against temperature ----
    Ts = np.arange(1000.0, 1401.0, 20.0)
    series = {k: [] for k in ORDER}
    total = []
    for T in Ts:
        v = gas_flux.flux_vapor(T, FLUX)
        for k in ORDER:
            series[k].append(v[k])
        total.append(v["total"])
    axA.plot(Ts, total, color="black", lw=2.4, label="total", zorder=4)
    linestyles = {"NaCl": "-", "KCl": "--", "MgCl2": (0, (1, 1.2))}
    grey = {"NaCl": "0.0", "KCl": "0.30", "MgCl2": "0.30"}
    for k in ORDER:
        axA.plot(Ts, series[k], color=grey[k], lw=1.5, ls=linestyles[k], label=LABEL[k])
    axA.set_yscale("log")
    axA.set_xlabel("Temperature (K)")
    axA.set_ylabel("fume partial pressure (bar)")
    axA.set_title("(a)  Fume over the flux", fontsize=11)
    axA.legend(frameon=False, fontsize=9, loc="lower right")

    # ---- panel (b): flux composition vs fume composition at a tap temperature ----
    T_B = 1200.0
    v = gas_flux.flux_vapor(T_B, FLUX)
    flux_pct = [100 * FLUX[k] for k in ORDER]
    fume_pct = [100 * v[k] / v["total"] for k in ORDER]
    x = np.arange(len(ORDER))
    w = 0.38
    axB.bar(x - w / 2, flux_pct, w, color="0.72", edgecolor="black", linewidth=0.8, label="in the flux")
    axB.bar(x + w / 2, fume_pct, w, color="0.28", edgecolor="black", linewidth=0.8, label="in the fume")
    for xi, (fl, fu) in enumerate(zip(flux_pct, fume_pct)):
        axB.text(xi - w / 2, fl + 1.2, f"{fl:.0f}", ha="center", va="bottom", fontsize=8.5)
        axB.text(xi + w / 2, fu + 1.2, f"{fu:.0f}", ha="center", va="bottom", fontsize=8.5)
    axB.set_xticks(x)
    axB.set_xticklabels([LABEL[k] for k in ORDER])
    axB.set_ylabel("mole per cent")
    axB.set_ylim(0, max(fume_pct + flux_pct) * 1.18)
    axB.set_title(f"(b)  Flux vs fume at {T_B:.0f} K", fontsize=11)
    axB.legend(frameon=False, fontsize=9, loc="upper right")

    for ax in (axA, axB):
        ax.tick_params(labelsize=9)
        for sp_ in ax.spines.values():
            sp_.set_linewidth(0.8)

    fig.tight_layout()
    out = HERE / "fig8_gas_flux.png"
    fig.savefig(out, dpi=600, facecolor="white")
    print("fig8_gas_flux.png written", out.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
