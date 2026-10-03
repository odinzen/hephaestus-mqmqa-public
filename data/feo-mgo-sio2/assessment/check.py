"""Independent check of the assessed FeO-MgO-SiO2 file: the solidus (first liquid) at the bulk
compositions Nafziger & Muan 1967 (Am. Mineral. 52, 1364, open access) measured at 1 atm,
iron saturated. Table 6: olivine + pyroxene field; Table 10: olivine + magnesiowustite field.
Read from the scan; oxide mole fractions, solidus in degC. None of these is fitted.

Run:  python check.py [path to a combined .dat]
"""
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "python"))
DAT = HERE.parent / "FeO-MgO-SiO2-combined.dat"

# (N_FeO, N_MgO, N_SiO2, solidus degC)
TABLE6 = [(0.369, 0.278, 0.353, 1301), (0.277, 0.247, 0.478, 1308), (0.340, 0.303, 0.358, 1319),
          (0.319, 0.327, 0.353, 1325), (0.212, 0.308, 0.480, 1341), (0.291, 0.351, 0.358, 1344),
          (0.228, 0.419, 0.354, 1395), (0.128, 0.388, 0.485, 1443), (0.168, 0.478, 0.355, 1450)]
TABLE10 = [(0.563, 0.127, 0.310, 1199), (0.480, 0.214, 0.307, 1250), (0.394, 0.292, 0.314, 1285),
           (0.373, 0.318, 0.310, 1295), (0.258, 0.433, 0.309, 1360), (0.432, 0.334, 0.234, 1354),
           (0.543, 0.230, 0.227, 1288), (0.657, 0.114, 0.229, 1206), (0.838, 0.117, 0.045, 1354),
           (0.869, 0.085, 0.046, 1288), (0.902, 0.052, 0.046, 1241), (0.935, 0.018, 0.047, 1200)]
LIQ = "FEO-MGO-SIO2-LIQUID"
_db = None


def _init(path):
    global _db
    import mqmqa
    _db = mqmqa.Database.read(path)


def _solidus(row):
    from mqmqa import vis3d
    fe, mg, si, _ = row
    tot = fe + mg + si
    x2, x3 = mg / tot, si / tot
    has_liq = lambda T: any(p == LIQ and a > 1e-3 for p, a, *_ in vis3d.Hull(_db, T).assemblage(x2, x3))
    lo, hi = 1100.0, 2000.0
    if has_liq(lo) or not has_liq(hi):
        return float("nan")
    while hi - lo > 0.5:
        m = 0.5 * (lo + hi)
        lo, hi = (lo, m) if has_liq(m) else (m, hi)
    return 0.5 * (lo + hi)


def solidus_all(path):
    rows = TABLE6 + TABLE10
    with Pool(8, initializer=_init, initargs=(str(path),)) as pool:
        return rows, pool.map(_solidus, rows, chunksize=1)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else DAT
    rows, T = solidus_all(path)
    for tag, sl in (("olivine + pyroxene (Table 6)", slice(0, 9)),
                    ("olivine + magnesiowustite (Table 10)", slice(9, 21))):
        d = np.array([t - (r[3] + 273.15) for r, t in zip(rows[sl], T[sl])])
        for r, t in zip(rows[sl], T[sl]):
            print(f"    {r[0]:.3f} {r[1]:.3f} {r[2]:.3f}  measured {r[3] + 273.15:7.1f}  model {t:7.1f}  {t - r[3] - 273.15:+6.0f}")
        print(f"  {tag}: mean {np.nanmean(d):+.0f} K, mean absolute {np.nanmean(np.abs(d)):.0f} K")
