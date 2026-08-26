"""Validate the assembled CAS ternary against the 45 KEMS silica activities.

Pure prediction test: nothing ternary was fitted, the liquid is the Muggianu
combination of the three shipped binaries. Measured a(SiO2) (Kay & Taylor 1960
gas-slag / KEMS; Zaitsev 1997 KEMS) are referred to silica saturation, i.e. the
cristobalite reference, which is what the model computes:

    a(SiO2) = exp[(mu_Si + 2*mu_O - G_cristobalite(T)) / RT]

with the element chemical potentials from a liquid-only pycalphad equilibrium on the
WRITTEN database file (judge the artifact on disk).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "python"))

import build_dat
from mqmqa.dbbuild import solid_gibbs_coeffs

R = 8.3145
MANIFEST = Path(r"C:\Users\busta\Code\odinzen_assessment_workspace\assessments"
                r"\CaO-Al2O3-SiO2\manifest.json")
M = {"CaO": 56.077, "Al2O3": 101.961, "SiO2": 60.084}


def parse_composition(text):
    """Oxide mole fractions from either manifest composition string."""
    import re
    vals = dict(re.findall(r"(CaO|Al2O3|SiO2)\)?=([0-9.]+)", text))
    vals = {k: float(v) for k, v in vals.items()}
    if "mass percent" in text:
        moles = {k: vals[k] / M[k] for k in vals}
        tot = sum(moles.values())
        return {k: v / tot for k, v in moles.items()}
    return vals


def g_cristobalite(T):
    cf = build_dat.SOLIDS["SiO2_cristobalite"][3]
    A, B, C, D, E, F = solid_gibbs_coeffs(cf["dHf"], cf["S298"], cf["a"], cf["b"], cf["c"])
    return A + B * T + C * T * math.log(T) + D * T * T + E * T ** 3 + F / T


def main():
    from pycalphad import Database as PDB, equilibrium, variables as v
    dat = build_dat.HERE / "CaO-Al2O3-SiO2.dat"
    if not dat.exists():
        build_dat.build()
    pdb = PDB(str(dat))

    arts = json.loads(MANIFEST.read_text(encoding="utf-8"))["artifacts"]
    pts = [a for a in arts if "aSiO2" in a.get("id", "") or a.get("quantity") == "activity"]
    rows = []
    for a in pts:
        cond = a.get("conditions", {})
        T = cond.get("temperature_K")
        x = parse_composition(cond.get("composition", ""))
        n = {"CA": x.get("CaO", 0.0), "AL": 2 * x.get("Al2O3", 0.0), "SI": x.get("SiO2", 0.0)}
        n["O"] = x.get("CaO", 0.0) + 3 * x.get("Al2O3", 0.0) + 2 * x.get("SiO2", 0.0)
        tot = sum(n.values())
        try:
            eqr = equilibrium(pdb, ["CA", "AL", "SI", "O"], ["CAO-ALO1.5-SIO2-LIQUID"],
                              {v.T: T, v.P: 101325, v.N: 1,
                               v.X("CA"): n["CA"] / tot, v.X("AL"): n["AL"] / tot,
                               v.X("SI"): n["SI"] / tot})
            comps = list(eqr.component.values)
            mu = {c: float(eqr.MU.sel(component=c).values.ravel()[0]) for c in comps}
        except Exception as e:
            rows.append((a["id"], T, None, a.get("value"), f"eq failed: {e}"))
            continue
        mu_sio2 = mu["SI"] + 2 * mu["O"]
        a_model = math.exp((mu_sio2 - g_cristobalite(T)) / (R * T))
        rows.append((a["id"], T, a_model, a.get("value"), ""))

    print(f"{'point':46s} {'T/K':>6s} {'a_meas':>10s} {'a_model':>10s} {'dln a':>7s}")
    devs = {"zaitsev": [], "kay": []}
    for pid, T, am, ax, err in rows:
        if am is None:
            print(f"{pid[:46]:46s} {T:6.0f}  {err}")
            continue
        d = math.log(am) - math.log(ax)
        key = "zaitsev" if "zaitsev" in pid else "kay"
        devs[key].append(d)
        print(f"{pid[:46]:46s} {T:6.0f} {ax:10.3e} {am:10.3e} {d:+7.2f}")
    for k, ds in devs.items():
        if ds:
            ds = np.array(ds)
            print(f"{k}: n={len(ds)}  RMS ln a = {np.sqrt(np.mean(ds**2)):.2f}  "
                  f"bias = {np.mean(ds):+.2f}")


if __name__ == "__main__":
    main()
