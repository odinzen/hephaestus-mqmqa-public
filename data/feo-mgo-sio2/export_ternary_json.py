"""Export the computed FeO-MgO-SiO2 ternary diagram (primary-phase fields + liquidus isotherms)
to a compact JSON the browser app embeds and renders. Both come from the vis3d refined hull,
the equilibrium the 3D view draws: the fields are read off its liquidus surface (one patch per
primary-phase field), the isotherms are contours of the equilibrium liquid fraction at each
level (bs_comparison.compute_isotherm_fields, recomputed on every export so no stale cache is
carried over)."""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "web" / "ternary_feo_mgo_sio2.json"
DAT = HERE / "FeO-MgO-SiO2-combined.dat"

_spec = importlib.util.spec_from_file_location("bs", HERE / "bs_comparison.py")
bs = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(bs)

sys.path.insert(0, str(HERE.parents[1] / "python"))
import mqmqa                    # noqa: E402
from mqmqa import vis3d         # noqa: E402

PHASES = ["CRISTOBALITE", "OLIVINE", "ORTHOPYROXENE", "MAGNESIOWUSTITE"]
NGRID = 150
T_LO, T_HI = 1300.0, 3200.0     # below every liquidus of the system, above MgO melting


def field_rows(ngrid=NGRID, lattice_n=45):
    """One digit per grid node (row i = x_Fe = i/ngrid, column j = x_Si = j/ngrid): the index
    in PHASES of the liquidus-surface patch covering it, '.' where none does."""
    db = mqmqa.Database.read(str(DAT))
    s = vis3d.liquidus_surface(db, T_LO, T_HI, lattice_n=lattice_n)
    lab = s.tri_label
    t = s.comp[:, 1:][s.tri]                     # (n_tri, 3, 2) corners as (x2, x3)
    a, b, c = t[:, 0], t[:, 1], t[:, 2]
    det = (a[:, 0] - c[:, 0]) * (b[:, 1] - c[:, 1]) - (b[:, 0] - c[:, 0]) * (a[:, 1] - c[:, 1])
    rows = []
    for i in range(ngrid + 1):
        j = np.arange(ngrid + 1 - i)
        q = np.stack([(ngrid - i - j) / ngrid, j / ngrid], axis=1)[:, None, :]   # (x_Mg, x_Si)
        l1 = ((b[:, 1] - c[:, 1]) * (q[..., 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (q[..., 1] - c[:, 1])) / det
        l2 = ((c[:, 1] - a[:, 1]) * (q[..., 0] - c[:, 0]) + (a[:, 0] - c[:, 0]) * (q[..., 1] - c[:, 1])) / det
        inside = (l1 >= -1e-9) & (l2 >= -1e-9) & (1.0 - l1 - l2 >= -1e-9)
        first = inside.argmax(axis=1)
        rows.append("".join(str(PHASES.index(s.labels[lab[f]])) if ok else "."
                            for f, ok in zip(first, inside.any(axis=1))))
    return rows


def build():
    rows = field_rows()
    bs.compute_isotherm_fields()
    isos = bs._isotherm_segments()
    isotherms = []
    for c in bs.LEVELS_C:
        arcs = [[[round(float(x), 4), round(float(y), 4)] for x, y in seg] for seg in isos.get(c, [])]
        if arcs:
            isotherms.append({"degC": c, "arcs": arcs})

    payload = {
        "system": "FeO-MgO-SiO2",
        "basis": "cation mole fraction (x_Fe, x_Si; x_Mg = 1 - x_Fe - x_Si)",
        "note": "Open-database result on the refined hull (vis3d); the model is validated "
                "against pycalphad.",
        "phases": PHASES,
        "ngrid": NGRID,
        "field_rows": rows,
        "isotherms": isotherms,
    }
    OUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB, ngrid={NGRID}, "
          f"{len(isotherms)} isotherms)")
    return OUT


if __name__ == "__main__":
    build()
