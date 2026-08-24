"""Olivine <-> orthopyroxene Fe-Mg exchange equilibrium - two CEF phases in equilibrium.

The exchange reaction (SiO2-conserving) is
    Mg2SiO4(ol) + 2 FeSiO3(opx) = Fe2SiO4(ol) + 2 MgSiO3(opx),
i.e. Fe and Mg partition between coexisting olivine and orthopyroxene. At equilibrium the
Fe-Mg exchange chemical potential is equal in both phases. Per two-cation formula that is
just equal slopes of the molar Gibbs curves:

    dG_ol/dX_Fe |_{X_Fe,ol}  =  dG_opx/dX_Fe |_{X_Fe,opx}.

Both G(X_Fe) come from the C CEF kernel (mqmqa.Database.cef_gibbs, per formula unit) on the
combined SUBL .dat. For each orthopyroxene composition this fixes the coexisting olivine
composition, giving the exchange isotherm and the distribution coefficient

    K_D = (X_Fe/X_Mg)_olivine / (X_Fe/X_Mg)_orthopyroxene.

Validation: pycalphad's own equilibrium() on the same .dat (independent oracle), plus a
cross-check against the measured K_D of von Seckendorff & O'Neill 1993.

Run from the repo root:
  C:/Users/busta/miniforge3/envs/calphad/python.exe data/olivine-opx/exchange.py
"""
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq
from pycalphad import Database as PycDatabase, equilibrium, variables as v

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "python"))

import mqmqa

DAT = HERE / "Olivine-Opx-CEF.dat"


def _load():
    import build_dat
    DAT.write_text(build_dat.build(), encoding="ascii")
    cdb = mqmqa.Database.read(str(DAT))
    return cdb, cdb.phase_index("OLIVINE"), cdb.phase_index("ORTHOPYROXENE")


def dG_dXfe(cdb, p, x_fe, T, h=1e-5):
    """Slope of the molar Gibbs curve wrt X_Fe (per two-cation formula), central diff.
    Constituent order on the metal sublattice is [Fe, Mg]; Si and O sublattices are 1.0."""
    a = max(x_fe - h, 1e-9)
    b = min(x_fe + h, 1 - 1e-9)
    ga = cdb.cef_gibbs(p, [a, 1 - a, 1.0, 1.0], T, per_mole_atoms=False)
    gb = cdb.cef_gibbs(p, [b, 1 - b, 1.0, 1.0], T, per_mole_atoms=False)
    return (gb - ga) / (b - a)


def exchange_x_ol(cdb, p_ol, p_opx, x_opx, T):
    """Olivine X_Fe coexisting with orthopyroxene at X_Fe = x_opx: the root of
    dG_ol/dX_Fe(x_ol) = dG_opx/dX_Fe(x_opx)."""
    target = dG_dXfe(cdb, p_opx, x_opx, T)
    f = lambda x_ol: dG_dXfe(cdb, p_ol, x_ol, T) - target
    lo, hi = 1e-6, 1 - 1e-6
    if f(lo) * f(hi) > 0:
        return None
    return brentq(f, lo, hi, xtol=1e-10)


def K_D(x_ol, x_opx):
    return (x_ol / (1 - x_ol)) / (x_opx / (1 - x_opx))


def pyc_tieline(pdb, T, x_sio2_bulk, fe_frac_bulk):
    """pycalphad two-phase equilibrium at a bulk composition in the ol+opx field.
    Returns (X_Fe,ol, X_Fe,opx) or None if not two-phase."""
    n_mo, n_si = 1.0 - x_sio2_bulk, x_sio2_bulk
    n_o = n_mo + 2 * n_si
    tot = n_mo + n_si + n_o
    xsi, xo = n_si / tot, n_o / tot
    xfe = fe_frac_bulk * n_mo / tot
    res = equilibrium(pdb, ["FE", "MG", "SI", "O"], ["OLIVINE", "ORTHOPYROXENE"],
                      {v.T: T, v.P: 101325, v.X("SI"): xsi, v.X("O"): xo, v.X("FE"): xfe})
    phase = res.Phase.values.reshape(-1)
    XFE = res.X.sel(component="FE").values.reshape(-1)
    XMG = res.X.sel(component="MG").values.reshape(-1)
    out = {}
    for k in range(phase.size):
        ph = phase[k]
        if ph in ("OLIVINE", "ORTHOPYROXENE") and (XFE[k] + XMG[k]) > 0:
            out[ph] = XFE[k] / (XFE[k] + XMG[k])
    if "OLIVINE" in out and "ORTHOPYROXENE" in out:
        return out["OLIVINE"], out["ORTHOPYROXENE"]
    return None


def main():
    cdb, p_ol, p_opx = _load()
    pdb = PycDatabase(str(DAT))
    print("phases in engine:", cdb.phase_names)

    print("\n1) Exchange isotherm vs pycalphad equilibrium (K_D at 1000 K)")
    print(f"{'x_opx(bulk)':>11} | {'engine X_Fe ol/opx':>20} | {'pycalphad ol/opx':>20} | K_D e/p")
    print("-" * 78)
    T = 1000.0
    worst = 0.0
    for fe_bulk in (0.15, 0.3, 0.5, 0.7):
        tie = pyc_tieline(pdb, T, x_sio2_bulk=0.42, fe_frac_bulk=fe_bulk)
        if not tie:
            print(f"  bulk Fe={fe_bulk}: not two-phase")
            continue
        x_ol_p, x_opx_p = tie
        x_ol_e = exchange_x_ol(cdb, p_ol, p_opx, x_opx_p, T)  # my olivine at pycalphad's opx
        d = abs(x_ol_e - x_ol_p)
        worst = max(worst, d)
        print(f"{x_opx_p:11.4f} | {x_ol_e:8.4f} {x_opx_p:8.4f}   | "
              f"{x_ol_p:8.4f} {x_opx_p:8.4f}   | {K_D(x_ol_e, x_opx_p):.3f}/{K_D(x_ol_p, x_opx_p):.3f}")
    print("-" * 78)
    print(f"worst olivine X_Fe disagreement vs pycalphad = {worst:.2e}  -> "
          f"{'PASS' if worst < 1e-3 else 'FAIL'}")

    print("\n2) K_D vs composition and temperature (engine exchange isotherm)")
    print(f"{'X_Fe,opx':>9} | " + " | ".join(f"K_D({int(T)}K)" for T in (900, 1100, 1300)))
    for x_opx in (0.1, 0.3, 0.5, 0.7, 0.9):
        row = []
        for T in (900.0, 1100.0, 1300.0):
            x_ol = exchange_x_ol(cdb, p_ol, p_opx, x_opx, T)
            row.append(f"  {K_D(x_ol, x_opx):.3f}  ")
        print(f"{x_opx:9.2f} | " + " | ".join(row))

    print("\n3) Cross-check vs von Seckendorff & O'Neill 1993 (measured, near-ideal):")
    print("   they report K_D ~ 1 and nearly T-independent, with the ol/opx exchange")
    print("   deviations cancelling near Fe/(Mg+Fe) ~ 0.1 (mantle compositions).")
    x_ol_01 = exchange_x_ol(cdb, p_ol, p_opx, 0.1, 1273.0)
    print(f"   engine at X_Fe,opx=0.10, 1273 K:  X_Fe,ol={x_ol_01:.3f}, K_D={K_D(x_ol_01, 0.1):.3f}")


if __name__ == "__main__":
    main()
