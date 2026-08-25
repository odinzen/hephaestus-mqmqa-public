"""Export the computed FeO-MgO-SiO2 ternary diagram (primary-phase fields + liquidus isotherms)
to a compact JSON the browser app embeds and renders. This is the ASSESSED result of the 2-D
minimizer, precomputed offline; the app displays it while the live in-browser ternary solver is
still on the roadmap."""
import importlib.util
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PROJ = HERE / "_liquidus_projection.npz"
OUT = HERE.parents[1] / "web" / "ternary_feo_mgo_sio2.json"

_spec = importlib.util.spec_from_file_location("bs", HERE / "bs_comparison.py")
bs = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(bs)

PHASES = ["CRISTOBALITE", "OLIVINE", "ORTHOPYROXENE", "PERICLASE", "WUSTITE"]


def build():
    d = np.load(PROJ, allow_pickle=True)
    comps = d["comps"]; prim = d["prim"].astype(str)
    idx = {p: str(i) for i, p in enumerate(PHASES)}

    # infer the regular triangular grid step, then pack the primary-phase field as one digit
    # per cell (row i = x_Fe = i/ngrid; column j = x_Si = j/ngrid), '.' where nothing crystallizes
    xs = np.unique(comps[:, 0])
    ngrid = int(round(1.0 / np.min(np.diff(xs))))
    grid = {}
    for xf, xs_, p in zip(comps[:, 0], comps[:, 1], prim):
        grid[(round(xf * ngrid), round(xs_ * ngrid))] = idx.get(p, ".")
    rows = []
    for i in range(ngrid + 1):
        rows.append("".join(grid.get((i, j), ".") for j in range(ngrid + 1 - i)))

    isos = bs._isotherm_segments()
    isotherms = []
    for c in bs.LEVELS_C:
        arcs = [[[round(float(x), 4), round(float(y), 4)] for x, y in seg] for seg in isos.get(c, [])]
        if arcs:
            isotherms.append({"degC": c, "arcs": arcs})

    payload = {
        "system": "FeO-MgO-SiO2",
        "basis": "cation mole fraction (x_Fe, x_Si; x_Mg = 1 - x_Fe - x_Si)",
        "note": "Assessed open-database result from the 2-D minimizer, validated against pycalphad.",
        "phases": PHASES,
        "ngrid": ngrid,
        "field_rows": rows,
        "isotherms": isotherms,
    }
    OUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB, ngrid={ngrid}, "
          f"{len(isotherms)} isotherms)")
    return OUT


if __name__ == "__main__":
    build()
