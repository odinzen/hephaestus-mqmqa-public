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
NGRID = 60           # triangular grid over the remaining CaO-MgO-SiO2 (step 1/NGRID)

# solid phases, ordered; index becomes the field digit
PHASES = ["OLIVINE", "ORTHOPYROXENE", "CLINOPYROXENE", "WOLLASTONITE", "RANKINITE", "LARNITE",
          "HATRURITE", "CRISTOBALITE", "LIME", "MAGNESIOWUSTITE"]

# Cooling scan in 20 K steps. A cell still holding a solid at the top of T_LOW is scanned again
# over T_HIGH: until 2026-10-07 the scan stopped at 2130 K, and in about half the section (the
# periclase and calcium-silicate side, where the liquidus runs up to the oxide melting points
# near 3100-3200 K) it reported whatever solid was stable at 2130 K as the primary phase.
T_LOW = np.arange(1250.0, 2150.0, 20.0)       # K
T_HIGH = np.arange(2150.0, 3250.0, 20.0)


def _first_solid(pdb, el, grid):
    """(phases, T) at the highest grid temperature that holds a solid, or (None, None)."""
    from pycalphad import equilibrium, variables as v
    tot = sum(el.values())
    r = equilibrium(pdb, ["CA", "FE", "MG", "SI", "O"], list(pdb.phases.keys()),
                    {v.T: grid, v.P: 101325, v.N: 1, v.X("CA"): el["CA"] / tot,
                     v.X("FE"): el["FE"] / tot, v.X("MG"): el["MG"] / tot,
                     v.X("SI"): el["SI"] / tot})
    for t in range(len(grid) - 1, -1, -1):
        ph = set(str(x) for x in r.Phase.isel(T=t).values.ravel()
                 if x and str(x) != "CAO-FEO-MGO-SIO2-LIQUID")
        if ph:
            return ph, float(grid[t])
    return None, None


def primary(pdb, el, idx):
    """Primary phase digit and liquidus (degC) at one bulk composition: cool from the top,
    the first solid is primary. None for the liquidus when the cell never melts in range."""
    ph, T = _first_solid(pdb, el, T_LOW)
    if ph is None:
        return ".", None
    if T == T_LOW[-1]:
        hi, Th = _first_solid(pdb, el, T_HIGH)
        if hi is not None:
            ph, T = hi, Th
    return idx.get(sorted(ph)[0], "."), round(T - 273.15, 1)


def build():
    from pycalphad import Database
    bc = importlib.util.spec_from_file_location("bc", HERE / "build_combined_dat.py")
    m = importlib.util.module_from_spec(bc); bc.loader.exec_module(m)
    pdb = Database(str(m.build()))
    idx = {p: str(i) for i, p in enumerate(PHASES)}

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
            prim, tl = primary(pdb, el, idx)
            field[(i, j)] = prim
            if tl is not None:
                tliq[(i, j)] = tl
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
