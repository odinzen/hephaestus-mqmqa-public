"""Turn the ESPEI posterior into an uncertainty band on the Al-Zn liquidus.

For a set of posterior draws of the LIQUID excess parameters (VV0001, VV0002), rebuild
the Al-Zn database with each draw and compute the liquidus; the spread of liquidus
curves is the uncertainty band. Greyscale, house style; the median line is the drawn
liquidus, the shaded envelope its 5-95 percentile across the posterior.

Run after the MCMC has written output/trace.npy.
"""
import numpy as np
import matplotlib.pyplot as plt
from pycalphad import Database, equilibrium, variables as v

BASE = open("alzn_espei.tdb", encoding="utf-8").read()
NSAMP = 60
XS = np.linspace(0.04, 0.96, 24)          # x_Zn grid
TSCAN = np.arange(945.0, 645.0, -3.0)     # top-down T scan for the liquidus


def db_for(vv1, vv2):
    txt = BASE.replace(" FUNCTION VV0001 298.15 +10465.5; 6000 N !",
                       f" FUNCTION VV0001 298.15 {vv1:+.6f}; 6000 N !")
    txt = txt.replace(" FUNCTION VV0002 298.15 -3.39259; 6000 N !",
                      f" FUNCTION VV0002 298.15 {vv2:+.8f}; 6000 N !")
    return Database(txt)


def liquidus(dbf):
    """Liquidus temperature at each x_Zn: the highest T at which a non-liquid phase
    is stable (top-down scan)."""
    Tl = np.full(len(XS), np.nan)
    for i, x in enumerate(XS):
        eq = equilibrium(dbf, ["AL", "ZN", "VA"], ["LIQUID", "FCC_A1", "HCP_A3"],
                         {v.T: TSCAN, v.P: 1e5, v.N: 1, v.X("ZN"): float(x)})
        phases = eq.Phase.values.squeeze()      # (nT, nvertex)
        for k, T in enumerate(TSCAN):
            row = [str(p) for p in np.ravel(phases[k]) if str(p) and str(p) != "nan"]
            if any(p != "LIQUID" for p in row):  # a solid appeared -> at/below liquidus
                Tl[i] = T
                break
    return Tl


def main():
    trace = np.load("output/trace.npy")
    burn = trace.shape[1] // 2
    flat = trace[:, burn:, :].reshape(-1, trace.shape[2])
    rng = np.random.default_rng(0)
    draws = flat[rng.choice(len(flat), size=min(NSAMP, len(flat)), replace=False)]

    curves = []
    for n, (vv1, vv2) in enumerate(draws):
        try:
            Tl = liquidus(db_for(vv1, vv2))
            if np.isfinite(Tl).sum() > len(XS) // 2:
                curves.append(Tl)
        except Exception:
            pass
    curves = np.array(curves)
    print(f"{len(curves)} liquidus curves from the posterior")

    lo = np.nanpercentile(curves, 5, axis=0)
    hi = np.nanpercentile(curves, 95, axis=0)
    med = np.nanpercentile(curves, 50, axis=0)

    fig, ax = plt.subplots(figsize=(5.2, 4.0))
    ax.fill_between(XS, lo - 273.15, hi - 273.15, color="0.75", lw=0,
                    label="90% posterior band")
    ax.plot(XS, med - 273.15, color="black", lw=1.6, label="median liquidus")
    ax.plot([0.887], [654 - 273.15], "o", mfc="white", mec="black", ms=6,
            label="eutectic (Massalski)")
    ax.set_xlabel("x(Zn)")
    ax.set_ylabel("Temperature (°C)")
    ax.set_title("Al–Zn liquidus with ESPEI parameter uncertainty", fontsize=11)
    ax.legend(frameon=False, fontsize=8.5, loc="upper right")
    ax.tick_params(labelsize=9)
    fig.tight_layout()
    fig.savefig("output/alzn_uq_band.png", dpi=600, facecolor="white")
    band = float(np.nanmax(hi - lo))
    print(f"widest band {band:.1f} K; figure at output/alzn_uq_band.png")


if __name__ == "__main__":
    main()
