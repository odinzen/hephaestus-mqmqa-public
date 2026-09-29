"""Model liquidus against the quenching data of Bowen & Schairer 1935, Table I.

bs1935_table1.csv is Table I (a) to (f), pp. 155-157 of Bowen & Schairer, Am. J. Sci. 29
(1935) 151-217, read off the scan: liquid composition in weight percent, temperature of
completion of melting in degC (+-4), and the primary phase as they report it (sub-table a
gives it per row; b and c are olivine, d clinopyroxene, e tridymite, f cristobalite). Rows
are printed as analysed, so three of them sum to 99.8 and 101.0; each is normalized here.
The small Fe2O3 is counted as FeO, the total iron as they reduce their mixtures.

The model has one pyroxene (orthopyroxene) and one silica phase (cristobalite), so their
clinopyroxene is scored against orthopyroxene and tridymite against cristobalite.
Each liquidus comes from vis3d.liquidus_point on the refined hull. A validation target
only: nothing in the database is fitted to it.

Run: python data/feo-mgo-sio2/bs1935_liquidus.py   (seconds, on 8 processes)
"""
import csv
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))

DAT = HERE / "FeO-MgO-SiO2-combined.dat"
TABLE = HERE / "bs1935_table1.csv"
M = {"FeO": 71.844, "MgO": 40.304, "SiO2": 60.083, "Fe2O3": 159.688}
MODEL_PHASE = {"ol": "OLIVINE", "cpx": "ORTHOPYROXENE", "trid": "CRISTOBALITE",
               "crist": "CRISTOBALITE", "trid+cpx": None}
FIELDS = {"olivine": ("ol",), "pyroxene": ("cpx",), "silica": ("trid", "crist", "trid+cpx")}
T_LO, T_HI = 1350.0, 2300.0

_db = None


def cation_fractions(row):
    """(x_Fe, x_Mg, x_Si) per mole of cations."""
    feo = float(row["FeO"]) + float(row["Fe2O3"]) * 2 * M["FeO"] / M["Fe2O3"]
    n = np.array([feo / M["FeO"], float(row["MgO"]) / M["MgO"], float(row["SiO2"]) / M["SiO2"]])
    return n / n.sum()


def _init():
    global _db
    import mqmqa
    _db = mqmqa.Database.read(str(DAT))


def _liquidus(x):
    from mqmqa import vis3d
    return vis3d.liquidus_point(_db, x[1], x[2], T_LO, T_HI)


def main():
    rows = list(csv.DictReader(open(TABLE, encoding="ascii")))
    comps = [cation_fractions(r) for r in rows]
    with Pool(8, initializer=_init) as pool:
        model = pool.map(_liquidus, comps, chunksize=1)
    print(" tab   x_Fe   x_Mg   x_Si   meas K  primary    model K   dT  model primary")
    dT, hits, n = {}, 0, 0
    for r, x, (T, prim) in zip(rows, comps, model):
        Tm = float(r["T_C"]) + 273.15
        want = MODEL_PHASE[r["primary"]]
        if want:
            n += 1
            hits += prim == want
        dT.setdefault(r["primary"], []).append(T - Tm)
        print(f"  {r['table']}   {x[0]:.3f}  {x[1]:.3f}  {x[2]:.3f}  {Tm:7.1f}  {r['primary']:9s}"
              f"{T:8.1f}  {T - Tm:+5.0f}  {prim}")
    for name, keys in FIELDS.items():
        d = np.concatenate([dT[k] for k in keys if k in dT])
        print(f"{name:9s} field: {len(d):2d} points, mean {d.mean():+.0f} K, "
              f"mean absolute {np.abs(d).mean():.0f} K, worst {np.abs(d).max():.0f} K")
    print(f"primary phase as measured: {hits} of {n}")


if __name__ == "__main__":
    main()
