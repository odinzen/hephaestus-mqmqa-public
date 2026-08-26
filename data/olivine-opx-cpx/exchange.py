"""Fe-Mg exchange (K_D) among coexisting olivine, orthopyroxene and clinopyroxene.

Fe and Mg partition between any two of the three solid solutions. At equilibrium the
Fe-Mg exchange potential per mixing site is equal in both phases:

    mu_ex(phase) = (dG_formula/dX_Fe) / n_sites,

n_sites = mixing cations per formula (olivine 2, orthopyroxene 2, clinopyroxene 1). For
each pair this fixes the coexisting compositions and the distribution coefficient

    K_D = (X_Fe/X_Mg)_A / (X_Fe/X_Mg)_B.

All G(X_Fe) come from the C CEF kernel on the combined .dat. Each pair is checked against
pycalphad's own equilibrium() on the same file (independent oracle). ol-opx additionally
carries the measured cross-check from data/olivine-opx (von Seckendorff & O'Neill 1993).
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq
from pycalphad import Database as PDB, equilibrium, variables as v

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))
import mqmqa

# phase -> (n mixing sites per formula, Y builder with mixing X_Fe = x)
PH = {
    "OLIVINE": (2, lambda x: [x, 1 - x, 1.0, 1.0]),
    "ORTHOPYROXENE": (2, lambda x: [x, 1 - x, 1.0, 1.0]),
    "CLINOPYROXENE": (1, lambda x: [1.0, x, 1 - x, 1.0, 1.0]),   # CA, FE, MG, SI, O
}


def _load():
    spec = importlib.util.spec_from_file_location("oox_build", HERE / "build_dat.py")
    bd = importlib.util.module_from_spec(spec); spec.loader.exec_module(bd)
    dat = bd.build()
    db = mqmqa.Database.read(str(dat))
    return db, PDB(str(dat)), dat


def mu_ex(db, ph, x, T, h=1e-5):
    n, Y = PH[ph]
    a, b = max(x - h, 1e-9), min(x + h, 1 - 1e-9)
    ga = db.cef_gibbs(db.phase_index(ph), Y(a), T, per_mole_atoms=False)
    gb = db.cef_gibbs(db.phase_index(ph), Y(b), T, per_mole_atoms=False)
    return (gb - ga) / (b - a) / n


def coexist(db, phA, phB, xB, T):
    """X_Fe in phA coexisting with phB at X_Fe = xB (equal exchange potential)."""
    tgt = mu_ex(db, phB, xB, T)
    f = lambda xa: mu_ex(db, phA, xa, T) - tgt
    if f(1e-6) * f(1 - 1e-6) > 0:
        return None
    return brentq(f, 1e-6, 1 - 1e-6, xtol=1e-10)


def kd(xA, xB):
    return (xA / (1 - xA)) / (xB / (1 - xB))


def pyc_pair(pdb, phA, phB, T, bulk, restrict=True):
    """pycalphad equilibrium at a bulk (dict of element mole fractions); returns
    {phase: X_Fe} for the stable phases. restrict=True limits the phase set to
    {phA, phB}; restrict=False lets any phase win (to report the true assemblage). When
    Ca is absent (olivine-opx) the equilibrium runs in the Ca-free subsystem, since the
    Ca dimension at X(Ca)=0 sits on a boundary where the global solver fails."""
    if bulk["CA"] < 1e-9:
        comps, cond_el = ["FE", "MG", "SI", "O"], ("FE", "MG", "SI")
        s = 1.0 - bulk["CA"]
        conds = {v.X(e): bulk[e] / s for e in cond_el}
    else:
        comps, cond_el = ["CA", "FE", "MG", "SI", "O"], ("CA", "FE", "MG", "SI")
        conds = {v.X(e): bulk[e] for e in cond_el}
    phase_set = [phA, phB] if restrict else list(pdb.phases.keys())
    res = equilibrium(pdb, comps, phase_set, {v.T: T, v.P: 101325, v.N: 1, **conds})
    phase = res.Phase.values.reshape(-1)
    XFE = res.X.sel(component="FE").values.reshape(-1)
    XMG = res.X.sel(component="MG").values.reshape(-1)
    out = {}
    for k in range(phase.size):
        keep = phase[k] in (phA, phB) if restrict else bool(phase[k])
        if keep and (XFE[k] + XMG[k]) > 1e-9:
            out[phase[k]] = XFE[k] / (XFE[k] + XMG[k])
    return out


def _bulk(ca, fe_frac, si, mtot=1.0):
    """Element mole fractions for Ca, (Fe+Mg)=mtot metals, Si; O by charge/stoichiometry."""
    m = mtot; fe = fe_frac * m; mg = m - fe
    o = ca + m + 2 * si          # CaO + MO + SiO2 oxygens
    tot = ca + fe + mg + si + o
    return {"CA": ca / tot, "FE": fe / tot, "MG": mg / tot, "SI": si / tot, "O": o / tot}


def main():
    db, pdb, _ = _load()
    T = 1000.0
    print(f"Fe-Mg exchange at {T:.0f} K (engine equal-mu_ex vs pycalphad tie-line)\n")

    # bulk levers: cpx+opx -> Ca:M:Si = f:(2-f):2; cpx+ol -> f:(2-f):(1+f), f = cpx fraction.
    pairs = [
        ("OLIVINE", "ORTHOPYROXENE", _bulk(0.0, 0.35, 0.9, mtot=1.2)),
        ("CLINOPYROXENE", "ORTHOPYROXENE", _bulk(0.5, 0.35, 2.0, mtot=1.5)),
        ("CLINOPYROXENE", "OLIVINE", _bulk(0.5, 0.35, 1.5, mtot=1.5)),
    ]
    for phA, phB, bulk in pairs:
        got = pyc_pair(pdb, phA, phB, T, bulk)
        if phA not in got or phB not in got:
            allph = pyc_pair(pdb, phA, phB, T, bulk, restrict=False)
            print(f"{phA[:3]}-{phB[:3]}: requested pair not the stable assemblage "
                  f"(pycalphad gives {allph}); engine isotherm:")
            xB = 0.3
            xA = coexist(db, phA, phB, xB, T)
            print(f"   at X_Fe({phB[:3]})={xB}, X_Fe({phA[:3]})={xA:.3f}, K_D={kd(xA, xB):.3f}")
            continue
        xA_p, xB_p = got[phA], got[phB]
        xA_e = coexist(db, phA, phB, xB_p, T)      # engine phA at pycalphad's phB
        print(f"{phA[:3]}-{phB[:3]}: pycalphad X_Fe {phA[:3]}={xA_p:.3f} {phB[:3]}={xB_p:.3f} "
              f"K_D={kd(xA_p, xB_p):.3f} | engine {phA[:3]}={xA_e:.3f} (dX={abs(xA_e-xA_p):.1e})")


if __name__ == "__main__":
    main()
