"""Precompute isothermal sections of the FeO-MgO-SiO2 diagram at several temperatures and
export them for the browser app's isothermal-section view. At each temperature every bulk
cation composition is classified by its stable phase assemblage (the 2-D minimizer's covering
hull facet); the app colours the assemblage regions and a slider switches temperature.

Packed compactly: per section, the list of distinct assemblages plus one character per grid
cell indexing into it (base-36 digit; '.' outside the domain)."""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "web" / "ternary_isothermal_feo_mgo_sio2.json"

_spec = importlib.util.spec_from_file_location("td", HERE / "ternary_diagram.py")
td = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(td)
import sys
sys.path.insert(0, str(HERE.parents[1] / "python"))
from mqmqa import ternary as tern

SECTIONS_C = [1300, 1400, 1500, 1600, 1700, 1800]   # degC
NGRID = 110
B36 = "0123456789abcdefghijklmnopqrstuvwxyz"


def section(TK):
    pts, facets = td.build(TK, nsamp=9000)
    assemblages, order = {}, []
    rows = []
    for i in range(NGRID + 1):
        row = []
        for j in range(NGRID + 1 - i):
            x_fe, x_si = i / NGRID, j / NGRID
            if x_fe + x_si > 1.0:
                row.append(".")
                continue
            a = tern.assemblage(pts, facets, x_fe, x_si)
            if a is None:
                row.append(".")
                continue
            key = tuple(sorted({("LIQUID" if ph.startswith("FEO") else ph)
                                for ph, amt, xf, xs in a if amt > 1e-3}))
            if key not in assemblages:
                assemblages[key] = len(order); order.append(list(key))
            row.append(B36[assemblages[key]])
        rows.append("".join(row))
    return order, rows


def build():
    out = {"system": "FeO-MgO-SiO2", "ngrid": NGRID, "sections": []}
    for c in SECTIONS_C:
        TK = c + 273.15
        order, rows = section(TK)
        out["sections"].append({"degC": c, "assemblages": order, "field_rows": rows})
        print(f"  section {c} degC: {len(order)} distinct assemblages")
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB)")
    return OUT


if __name__ == "__main__":
    build()
