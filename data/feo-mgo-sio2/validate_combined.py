"""End-to-end validation of the 2-D FeO-MgO-SiO2 minimizer against pycalphad `equilibrium`.

Both sides run the SAME model: pycalphad reads the combined ChemSage .dat
(`build_combined_dat.py` - liquid SUBQ + olivine/opx SUBL + the three stoichiometric oxide
solids), and our minimizer pools the same phases and takes the lower convex hull. For each bulk
cation composition we compare the stable phase SET, the equilibrium Gibbs energy GM, and the
per-phase cation compositions.

The opx enstatite high-T entropy correction lives in the .dat as a second Gibbs interval on
the Mg endmember, so both sides carry the FULL model - this validation now covers the
corrected physics end to end.

Bases: our GM is per mole cation; with one cation per oxide and charge-slaved O the atoms per
cation are (2 + x_Si), so GM_atom = G_cation / (2 + x_Si) matches pycalphad's per-mole-atom GM.
"""
import importlib.util
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))
from mqmqa import ternary as tern

_spec = importlib.util.spec_from_file_location("td", HERE / "ternary_diagram.py")
td = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(td)
_bc = importlib.util.spec_from_file_location("bc", HERE / "build_combined_dat.py")
bc = importlib.util.module_from_spec(_bc); _bc.loader.exec_module(bc)

DAT = HERE / "FeO-MgO-SiO2-combined.dat"
PHASES = ["FEO-MGO-SIO2-LIQUID", "OLIVINE", "ORTHOPYROXENE", "CRISTOBALITE", "PERICLASE", "WUSTITE"]

# bulk cation compositions (x_fe, x_si), chosen off the olivine/opx x_Si lines to avoid hull
# degeneracy and to sample distinct assemblages across the diagram
POINTS = [
    (0.20, 0.30), (0.10, 0.28), (0.35, 0.28), (0.55, 0.30),
    (0.12, 0.46), (0.06, 0.52), (0.08, 0.12), (0.30, 0.10),
]


def our_equilibrium(pts, facets, x_fe, x_si):
    a = tern.assemblage(pts, facets, x_fe, x_si)
    if a is None:
        return None
    agg = defaultdict(lambda: [0.0, 0.0, 0.0])
    for ph, amt, xf, xs in a:
        agg[ph][0] += amt; agg[ph][1] += amt * xf; agg[ph][2] += amt * xs
    phases = {ph: (amt, sf / amt, ss / amt) for ph, (amt, sf, ss) in agg.items() if amt > 1e-3}
    gm_atom = tern.hull_g(pts, facets, x_fe, x_si) / (2.0 + x_si)
    return phases, gm_atom


def pycalphad_equilibrium(dbf, equilibrium, v, T, x_fe, x_si):
    x_mg = 1.0 - x_fe - x_si
    O = x_fe + x_mg + 2 * x_si
    tot = 1.0 + O
    eq = equilibrium(dbf, ["FE", "MG", "SI", "O"], PHASES,
                     {v.T: T, v.P: 1e5, v.N: 1,
                      v.X("FE"): x_fe / tot, v.X("MG"): x_mg / tot, v.X("SI"): x_si / tot})
    Ph = np.ravel(eq.Phase.values.squeeze())
    NP = np.ravel(eq.NP.values.squeeze())
    X = eq.X.values.squeeze().reshape(len(Ph), -1)
    comp = list(eq.component.values)
    phases = {}
    for i, p in enumerate(Ph):
        name = str(p)
        if not name or name == "nan":
            continue
        d = dict(zip(comp, X[i]))
        cat = d["FE"] + d["MG"] + d["SI"]
        phases[name] = (float(NP[i]), d["FE"] / cat, d["SI"] / cat)
    return phases, float(eq.GM.values.squeeze())


def _phase_key(name):
    return "LIQUID" if name.startswith("FEO-MGO-SIO2") else name


def run(temps=(1700.0, 1600.0), nsamp=16000, n_cef=161, verbose=True):
    from pycalphad import Database, equilibrium, variables as v
    bc.build()
    dbf = Database(str(DAT))
    rows = []
    for T in temps:
        pts, facets = td.build(T, nsamp=nsamp, n_cef=n_cef)
        for x_fe, x_si in POINTS:
            ours = our_equilibrium(pts, facets, x_fe, x_si)
            pyc = pycalphad_equilibrium(dbf, equilibrium, v, T, x_fe, x_si)
            if ours is None:
                continue
            our_ph, our_gm = ours
            pyc_ph, pyc_gm = pyc
            our_set = {_phase_key(k) for k in our_ph}
            pyc_set = {_phase_key(k) for k in pyc_ph}
            dgm = our_gm - pyc_gm
            # worst per-phase cation-composition mismatch over shared phases
            dcomp = 0.0
            for k in our_set & pyc_set:
                ok = next(kk for kk in our_ph if _phase_key(kk) == k)
                pk = next(kk for kk in pyc_ph if _phase_key(kk) == k)
                dcomp = max(dcomp, abs(our_ph[ok][1] - pyc_ph[pk][1]),
                            abs(our_ph[ok][2] - pyc_ph[pk][2]))
            rows.append(dict(T=T, x_fe=x_fe, x_si=x_si, match=our_set == pyc_set,
                             our=sorted(our_set), pyc=sorted(pyc_set),
                             dgm=dgm, dcomp=dcomp))
            if verbose:
                flag = "OK " if our_set == pyc_set else "XX "
                print(f"{flag}T={T:.0f} ({x_fe:.2f},{x_si:.2f}) ours={sorted(our_set)} "
                      f"pyc={sorted(pyc_set)} dGM={dgm:+.1f} J/mol-atom  dcomp={dcomp:.3f}")
    n_match = sum(r["match"] for r in rows)
    print(f"\nphase-set match: {n_match}/{len(rows)}")
    finite = [r for r in rows if np.isfinite(r["dgm"])]
    if finite:
        print(f"|dGM| max = {max(abs(r['dgm']) for r in finite):.1f} J/mol-atom, "
              f"rms = {np.sqrt(np.mean([r['dgm']**2 for r in finite])):.1f}")
        shared = [r["dcomp"] for r in rows if r["match"]]
        if shared:
            print(f"worst per-phase cation-composition mismatch (matched pts) = {max(shared):.3f}")
    return rows


if __name__ == "__main__":
    run()
