"""Precompute the CaO-MgO-SiO2 crystallization diagram at a fixed FeO level and export a
compact JSON the browser embeds: the primary crystallizing phase across the section, plus
the liquidus temperature per cell. This is the assessed multiphase result (the calibrated
combined liquid+solids file, validated against pycalphad), precomputed offline like the
FeO-MgO-SiO2 diagram; the live in-browser 4-cation multiphase solver is on the roadmap.
"""
import importlib.util
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "web" / "crystallization_cao_mgo_sio2.json"
X_FE = 0.05          # fixed FeO level (cation fraction), a lean slag: shows both the
                     # Fe/Mg silicates and the calcium silicates (the latter are flux-
                     # suppressed at higher FeO)
NGRID = 20           # triangular grid over the remaining CaO-MgO-SiO2 (step 1/NGRID)

# solid phases, ordered; index becomes the field digit
PHASES = ["OLIVINE", "ORTHOPYROXENE", "CLINOPYROXENE", "WOLLASTONITE", "LARNITE",
          "CRISTOBALITE", "LIME", "PERICLASE", "WUSTITE"]


def build():
    from pycalphad import Database, equilibrium, variables as v
    bc = importlib.util.spec_from_file_location("bc", HERE / "build_combined_dat.py")
    m = importlib.util.module_from_spec(bc); bc.loader.exec_module(m)
    pdb = Database(str(m.build()))
    idx = {p: str(i) for i, p in enumerate(PHASES)}
    Tgrid = np.arange(1250.0, 2150.0, 20.0)      # K

    field = {}       # (i,j) -> primary phase digit
    tliq = {}        # (i,j) -> liquidus degC
    s = 1.0 - X_FE
    for i in range(NGRID + 1):                    # i = x_Ca index (of the CaO-MgO-SiO2 part)
        xca = s * i / NGRID
        for j in range(NGRID + 1 - i):            # j = x_Si index
            xsi = s * j / NGRID
            xmg = s - xca - xsi
            if xmg < -1e-9:
                continue
            el = {"CA": xca, "FE": X_FE, "MG": max(xmg, 0.0), "SI": xsi}
            el["O"] = el["CA"] + el["FE"] + el["MG"] + 2 * el["SI"]
            tot = sum(el.values())
            r = equilibrium(pdb, ["CA", "FE", "MG", "SI", "O"], list(pdb.phases.keys()),
                            {v.T: Tgrid, v.P: 101325, v.N: 1, v.X("CA"): el["CA"] / tot,
                             v.X("FE"): el["FE"] / tot, v.X("MG"): el["MG"] / tot,
                             v.X("SI"): el["SI"] / tot})
            prim, tl = ".", None
            for t in range(len(Tgrid) - 1, -1, -1):    # cool from the top; first solid = primary
                ph = set(str(x) for x in r.Phase.isel(T=t).values.ravel()
                         if x and str(x) != "CAO-FEO-MGO-SIO2-LIQUID")
                if ph:
                    prim = idx.get(sorted(ph)[0], ".")
                    tl = float(Tgrid[t]) - 273.15
                    break
            field[(i, j)] = prim
            if tl is not None:
                tliq[(i, j)] = round(tl, 1)
        print(f"row {i}/{NGRID} done", flush=True)

    rows = ["".join(field.get((i, j), ".") for j in range(NGRID + 1 - i))
            for i in range(NGRID + 1)]
    trows = [[tliq.get((i, j), None) for j in range(NGRID + 1 - i)]
             for i in range(NGRID + 1)]
    payload = {
        "system": "CaO-MgO-SiO2 at FeO = %d mol%% (cation)" % round(X_FE * 100),
        "corners": ["CaO", "MgO", "SiO2"],
        "basis": "cation mole fraction of CaO-MgO-SiO2 (x_Ca, x_Si; x_Mg = rest), FeO fixed",
        "note": "Assessed multiphase result: silicates crystallizing from the calibrated "
                "CaO-FeO-MgO-SiO2 melt, validated vs pycalphad.",
        "phases": PHASES, "ngrid": NGRID,
        "field_rows": rows, "liquidus_C": trows,
    }
    OUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB, ngrid={NGRID})")
    return OUT


if __name__ == "__main__":
    build()
