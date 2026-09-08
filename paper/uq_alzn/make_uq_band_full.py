"""Uncertainty band on the Al-Zn diagram: the liquidus AND the fcc (Al-rich) solvus,
both propagated from the ESPEI posterior of the liquid and fcc excess parameters.

For each posterior draw, rebuild the database and compute (a) the liquidus and (b) the
fcc composition in equilibrium with hcp; the spread of each is its band. Greyscale.
"""
import numpy as np
import matplotlib.pyplot as plt
from pycalphad import Database, equilibrium, variables as v

BASE = open("alzn_espei.tdb", encoding="utf-8").read()
NSAMP = 40
XS = np.linspace(0.04, 0.96, 22)
TSCAN = np.arange(945.0, 645.0, -3.0)
TSOL = np.arange(648.0, 398.0, -15.0)        # sub-eutectic fcc solvus, down toward room T


def db_for(v1, v2, v3):
    t = BASE.replace(" FUNCTION VV0001 298.15 +10465.5; 6000 N !",
                     f" FUNCTION VV0001 298.15 {v1:+.4f}; 6000 N !")
    t = t.replace(" FUNCTION VV0002 298.15 -3.39259; 6000 N !",
                  f" FUNCTION VV0002 298.15 {v2:+.6f}; 6000 N !")
    t = t.replace(" FUNCTION VV0003 298.15 +7297.5; 6000 N !",
                  f" FUNCTION VV0003 298.15 {v3:+.4f}; 6000 N !")
    return Database(t)


def liquidus(dbf):
    Tl = np.full(len(XS), np.nan)
    for i, x in enumerate(XS):
        eq = equilibrium(dbf, ["AL", "ZN", "VA"], ["LIQUID", "FCC_A1", "HCP_A3"],
                         {v.T: TSCAN, v.P: 1e5, v.N: 1, v.X("ZN"): float(x)})
        ph = eq.Phase.values.squeeze()
        for k in range(len(TSCAN)):
            row = [str(p) for p in np.ravel(ph[k]) if str(p) and str(p) != "nan"]
            if any(p != "LIQUID" for p in row):
                Tl[i] = TSCAN[k]; break
    return Tl


def fcc_solvus(dbf):
    """fcc (Al-rich) Zn content in equilibrium with hcp, vs T (the solvus branch)."""
    xs = np.full(len(TSOL), np.nan)
    for i, T in enumerate(TSOL):
        eq = equilibrium(dbf, ["AL", "ZN", "VA"], ["FCC_A1", "HCP_A3"],
                         {v.T: float(T), v.P: 1e5, v.N: 1, v.X("ZN"): 0.85})
        ph = np.ravel(eq.Phase.values.squeeze())
        X = eq.X.values.squeeze().reshape(len(ph), -1)
        comp = list(eq.component.values); iZn = comp.index("ZN")
        fcc = [X[j][iZn] for j, p in enumerate(ph) if str(p) == "FCC_A1"]
        if fcc:
            xs[i] = min(fcc)          # Al-rich fcc solvus
    return xs


def main():
    trace = np.load("output/trace.npy")
    burn = trace.shape[1] // 2
    flat = trace[:, burn:, :].reshape(-1, trace.shape[2])
    rng = np.random.default_rng(0)
    draws = flat[rng.choice(len(flat), size=min(NSAMP, len(flat)), replace=False)]

    liq, sol = [], []
    for d in draws:
        try:
            dbf = db_for(*d)
            liq.append(liquidus(dbf))
            sol.append(fcc_solvus(dbf))
        except Exception:
            pass
    liq = np.array(liq); sol = np.array(sol)
    print(f"{len(liq)} liquidus + {len(sol)} solvus curves")

    fig, ax = plt.subplots(figsize=(5.4, 4.2))
    # liquidus band
    lo, hi = np.nanpercentile(liq, 5, 0), np.nanpercentile(liq, 95, 0)
    ax.fill_between(XS, lo - 273.15, hi - 273.15, color="0.78", lw=0)
    ax.plot(XS, np.nanpercentile(liq, 50, 0) - 273.15, "k-", lw=1.6, label="liquidus")
    # solvus band (x on the composition axis varies with T here, so band in x)
    slo, shi = np.nanpercentile(sol, 5, 0), np.nanpercentile(sol, 95, 0)
    ax.fill_betweenx(TSOL - 273.15, slo, shi, color="0.78", lw=0, label="90% posterior band")
    ax.plot(np.nanpercentile(sol, 50, 0), TSOL - 273.15, "k--", lw=1.4, label="fcc solvus")
    ax.plot([0.887], [654 - 273.15], "o", mfc="white", mec="black", ms=6, label="eutectic (Massalski)")
    ax.text(0.09, 620, "LIQUID", fontsize=9, color="0.35")
    ax.text(0.05, 330, "FCC", fontsize=9, color="0.35")
    ax.text(0.85, 300, "FCC\n+ HCP", fontsize=9, color="0.35", ha="center")
    ax.set_xlabel("x(Zn)"); ax.set_ylabel("Temperature (°C)")
    ax.set_xlim(0, 1); ax.set_ylim(120, 665)
    ax.set_title("Al–Zn diagram with ESPEI parameter uncertainty", fontsize=11)
    ax.legend(frameon=False, fontsize=8, loc="lower center", ncol=2)
    ax.tick_params(labelsize=9)
    fig.tight_layout()
    fig.savefig("output/alzn_uq_band_full.png", dpi=600, facecolor="white")
    print("figure at output/alzn_uq_band_full.png")


if __name__ == "__main__":
    main()
