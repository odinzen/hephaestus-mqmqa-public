"""Precompute isothermal sections of the FeO-MgO-SiO2 diagram at several temperatures and
export them for the browser app's isothermal-section view. At each temperature every bulk
cation composition is classified by its stable phase assemblage on the refined hull of
vis3d (the same equilibrium the 3D view draws); the app colours the assemblage regions and a
slider switches temperature. A liquid split in two is listed as LIQUID twice.

Packed compactly: per section, the list of distinct assemblages plus one character per grid
cell indexing into it (base-36 digit; '.' outside the domain)."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "web" / "ternary_isothermal_feo_mgo_sio2.json"
DAT = HERE / "FeO-MgO-SiO2-combined.dat"

sys.path.insert(0, str(HERE.parents[1] / "python"))
import mqmqa                    # noqa: E402
from mqmqa import vis3d         # noqa: E402

SECTIONS_C = [1300, 1400, 1500, 1600, 1700, 1800]   # degC
NGRID = 110
B36 = "0123456789abcdefghijklmnopqrstuvwxyz"


def section(db, TK):
    h = vis3d.Hull(db, TK)
    assemblages, order = {}, []
    rows = []
    for i in range(NGRID + 1):
        row = []
        for j in range(NGRID + 1 - i):
            a = h.assemblage((NGRID - i - j) / NGRID, j / NGRID)   # (x_Mg, x_Si); x_Fe = i/NGRID
            key = tuple(sorted(("LIQUID" if ph.startswith("FEO") else ph)
                               for ph, amt, x2, x3 in a if amt > 1e-3))
            if key not in assemblages:
                assemblages[key] = len(order); order.append(list(key))
            row.append(B36[assemblages[key]])
        rows.append("".join(row))
    return order, rows


def build():
    db = mqmqa.Database.read(str(DAT))
    out = {"system": "FeO-MgO-SiO2", "ngrid": NGRID, "sections": []}
    for c in SECTIONS_C:
        TK = c + 273.15
        order, rows = section(db, TK)
        out["sections"].append({"degC": c, "assemblages": order, "field_rows": rows})
        print(f"  section {c} degC: {len(order)} distinct assemblages")
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB)")
    return OUT


if __name__ == "__main__":
    build()
