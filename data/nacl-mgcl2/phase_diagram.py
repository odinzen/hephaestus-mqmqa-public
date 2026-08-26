"""Draw the NaCl-MgCl2 v0.1 phase diagram from the fitted model (illustrative).

Simple eutectic: NaCl and MgCl2 liquidus branches meeting at the fitted eutectic
(718.1 K, x_MgCl2 = 0.42), with the eutectic horizontal below. The liquidus is the
common tangent from each pure solid to the liquid free-energy curve, evaluated with the
same C engine the tests validate against pycalphad.
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))
_spec = importlib.util.spec_from_file_location("nm_bd", HERE / "build_dat.py")
bd = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(bd)
_spec2 = importlib.util.spec_from_file_location("nm_vf", HERE / "v01_fit.py")
vf = importlib.util.module_from_spec(_spec2); _spec2.loader.exec_module(vf)


def liquidus_x(model, T, solid):
    """Liquid composition on the liquidus at T (tangent from the pure solid point)."""
    g_s, x_s = model.g_solid(solid, T)
    xs = np.linspace(1e-3, 1 - 1e-3, 400)
    slope = np.array([(model.g_liq(float(x), T) - g_s) / (x - x_s) for x in xs])
    # tangent from x_s=0 -> minimum secant slope; from x_s=1 -> maximum
    return float(xs[slope.argmin()]) if x_s == 0.0 else float(xs[slope.argmax()])


def main():
    m = vf.Model(bd.build(liq_terms=bd.liquid_terms()))
    T_eut, x_eut = vf.eutectic(m)

    Tn = np.linspace(T_eut + 0.5, bd.NACL.Tm, 60)
    xn = [liquidus_x(m, float(T), "NaCl_solid") for T in Tn]
    Tm = np.linspace(T_eut + 0.5, bd.MGCL2.Tm, 60)
    xm = [liquidus_x(m, float(T), "MgCl2_solid") for T in Tm]

    fig, ax = plt.subplots(figsize=(6.2, 4.6))
    C = "#1a1a1a"
    ax.plot(xn, Tn - 273.15, color=C, lw=1.8)
    ax.plot(xm, Tm - 273.15, color=C, lw=1.8)
    ax.plot([0, 1], [T_eut - 273.15] * 2, color=C, lw=1.4)
    ax.plot(x_eut, T_eut - 273.15, "o", color="#b00000", ms=6, zorder=5)
    ax.annotate(f"eutectic  {T_eut - 273.15:.0f} degC,  {x_eut*100:.0f} mol% MgCl2",
                (x_eut, T_eut - 273.15), textcoords="offset points", xytext=(8, -16),
                fontsize=9, color="#b00000")

    ax.text(0.02, bd.NACL.Tm - 273.15 - 8, "L + NaCl(s)", fontsize=9, color="#444")
    ax.text(0.72, bd.MGCL2.Tm - 273.15 - 30, "L + MgCl2(s)", fontsize=9, color="#444")
    ax.text(0.42, 380, "NaCl(s) + MgCl2(s)", fontsize=9, color="#444", ha="center")
    ax.text(0.42, 640, "liquid", fontsize=11, color="#222", ha="center")

    ax.set_xlim(0, 1); ax.set_ylim(360, 820)
    ax.set_xlabel("x(MgCl$_2$), salt mole fraction")
    ax.set_ylabel("Temperature (degC)")
    ax.set_title("NaCl-MgCl$_2$ Open Database v0.1 (Hephaestus)", fontsize=11)
    sec = ax.secondary_xaxis("top", functions=(lambda x: x, lambda x: x))
    sec.set_xticks([0, 0.42, 1]); sec.set_xticklabels(["NaCl", "0.42", "MgCl$_2$"])
    ax.grid(alpha=0.15)
    fig.tight_layout()
    out = HERE / "nacl_mgcl2_diagram.png"
    fig.savefig(out, dpi=160)
    print("wrote", out, "| eutectic", round(T_eut, 1), "K at x", round(x_eut, 3))


if __name__ == "__main__":
    main()
