"""The CaO-MgO-SiO2 crystallization section at 5% FeO computed with the engine's general
equilibrium solver, on the grid and with the rule of data/cao-feo-mgo-sio2/
export_crystallization_json.py (pycalphad): cool on a 20 K grid from 3230 K, and the first
temperature that holds a solid gives the primary phase (the alphabetically first if two
appear at once) and the liquidus. The highest such grid temperature is found by bisection,
which assumes a cell holds a solid at every grid temperature below its liquidus.

python data/cao-feo-mgo-sio2/crystallization_gem.py ENGINE_PYTHON_DIR RAW.json [workers] [rows LO HI]
    (an existing RAW.json is resumed: only its missing and failed cells are computed)
python data/cao-feo-mgo-sio2/crystallization_gem.py app RAW.json ENGINE_COMMIT

The second form writes the app's map, web/crystallization_cao_mgo_sio2.json, which Figure 3
draws, and the per-cell record crystallization_gem_5pctFeO.json. Since 16 November 2026 both come
from this script (Michael); the app's map was computed by pycalphad before
(export_chunked.py), which missed the stable liquid in most of the cells where the two differ.
"""
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DAT = ROOT / "data" / "cao-feo-mgo-sio2" / "CaO-FeO-MgO-SiO2-combined.dat"
X_FE, NGRID = 0.05, 60
PHASES = ["OLIVINE", "ORTHOPYROXENE", "CLINOPYROXENE", "WOLLASTONITE", "RANKINITE", "LARNITE",
          "HATRURITE", "CRISTOBALITE", "LIME", "MAGNESIOWUSTITE"]
GRID = [1250.0 + 20.0 * k for k in range(100)]        # 1250 ... 3230 K, as T_LOW + T_HIGH

_db = None


def _init(engine_dir):
    global _db, gem
    sys.path.insert(0, engine_dir)
    import mqmqa
    from mqmqa import gem as g
    gem = g
    _db = mqmqa.Database.read(str(DAT))


def _solids(T, el):
    r = gem.equilibrium(_db, T, el)
    return sorted({s.phase for s in r.sets if "LIQUID" not in s.phase and s.amount > 1e-9})


def cell(args):
    i, j = args
    s = 1.0 - X_FE
    xca, xsi = s * i / NGRID, s * j / NGRID
    xmg = max(s - xca - xsi, 0.0)
    # an oxide absent on the triangle's edges is given 1e-6 of the cations. At 1e-10 the solver
    # found no equilibrium in any edge cell, and with the element left out it loses the liquid
    # where MgO is absent (CaO-SiO2 edge solid at 3230 K); 1e-6 melts every edge cell and agrees
    # with its inner neighbours (16 November 2026).
    el = {"CA": xca, "FE": X_FE, "MG": xmg, "SI": xsi}
    el = {k: (v if v > 1e-12 else 1e-6) for k, v in el.items()}
    el["O"] = sum(v * (2 if k == "SI" else 1) for k, v in el.items())
    t0 = time.time()
    try:
        lo_ph = _solids(GRID[0], el)
        if not lo_ph:
            return i, j, ".", None, time.time() - t0, None
        hi_ph = _solids(GRID[-1], el)
        if hi_ph:
            return i, j, str(PHASES.index(hi_ph[0])), round(GRID[-1] - 273.15, 1), time.time() - t0, hi_ph
        lo, hi, ph = 0, len(GRID) - 1, lo_ph            # solid at lo, none at hi
        while hi - lo > 1:
            mid = (lo + hi) // 2
            p = _solids(GRID[mid], el)
            if p:
                lo, ph = mid, p
            else:
                hi = mid
        return i, j, str(PHASES.index(ph[0])), round(GRID[lo] - 273.15, 1), time.time() - t0, ph
    except Exception as exc:                            # a failed cell is reported, not hidden
        return i, j, "?", None, time.time() - t0, repr(exc)


def edge_neighbour(i, j):
    """The nearest interior cell of an edge cell (one oxide absent), one grid step in."""
    i2, j2 = max(i, 1), max(j, 1)
    while i2 + j2 > NGRID - 1:
        if i2 >= j2:
            i2 -= 1
        else:
            j2 -= 1
    return i2, j2


def write_app(raw_path, commit):
    """The app's map (the layout of export_chunked.py) and the per-cell record, from RAW.json.

    Cells on the triangle's edges, where one oxide is absent, show their nearest interior cell:
    with an oxide absent or at a trace the solver fails or loses the liquid there (16 November
    2026). The record keeps each edge cell's own result and names the neighbour it shows."""
    raw = json.loads(Path(raw_path).read_text())
    want = {f"{i},{j}" for i in range(NGRID + 1) for j in range(NGRID + 1 - i)}
    edge = {k for k in want if 0 in map(int, k.split(",")) or sum(map(int, k.split(","))) == NGRID}
    shown = {k: (k if k not in edge else "%d,%d" % edge_neighbour(*map(int, k.split(",")))) for k in want}
    missing = want - set(raw)
    failed = [k for k in want - edge if raw.get(k, ["?"])[0] == "?"]
    if missing or failed:
        raise SystemExit(f"map incomplete: {len(missing)} cells missing, {len(failed)} failed {failed[:5]}")
    raw = {k: raw[k] for k in want}
    computed = raw
    raw = {k: computed[shown[k]] for k in want}
    rows, trows = [], []
    for i in range(NGRID + 1):
        rows.append("".join(raw[f"{i},{j}"][0] for j in range(NGRID + 1 - i)))
        trows.append([raw[f"{i},{j}"][1] for j in range(NGRID + 1 - i)])
    app = {"system": "CaO-MgO-SiO2 at FeO = %d mol%% (cation)" % round(X_FE * 100),
           "corners": ["CaO", "MgO", "SiO2"],
           "basis": "cation mole fraction of CaO-MgO-SiO2 (x_Ca, x_Si; x_Mg = rest), FeO fixed",
           "note": "Silicates crystallizing from the assessed CaO-FeO-MgO-SiO2 melt, computed by "
                   f"Hephaestus's general equilibrium solver (commit {commit}).",
           "phases": PHASES, "ngrid": NGRID, "field_rows": rows, "liquidus_C": trows}
    out = ROOT / "web" / "crystallization_cao_mgo_sio2.json"
    out.write_text(json.dumps(app, separators=(",", ":")), encoding="utf-8")
    cells = {k: {"primary_digit": v[0], "liquidus_C": v[1], "solids_at_liquidus": v[3]}
             for k, v in sorted(raw.items())}
    for k in edge:
        cells[k]["shows_neighbour"] = shown[k]
        cells[k]["own_result"] = computed[k]
    rec = {"system": app["system"], "engine": f"Hephaestus general solver (gem), commit {commit}",
           "rule": "cool on a 20 K grid from 3230 K; the first temperature with a solid gives the "
                   "primary phase (alphabetically first of those appearing) and the liquidus",
           "grid": "cell (i, j): x_Ca = 0.95 i/60, x_Si = 0.95 j/60, x_Fe = 0.05, x_Mg the rest "
                   "(cation fractions); an edge cell (one oxide absent) shows its nearest interior cell, "
                   "its own result (absent oxide at 1e-6) kept beside it",
           "cells": cells}
    (Path(__file__).parent / "crystallization_gem_5pctFeO.json").write_text(json.dumps(rec), encoding="utf-8")
    print(f"wrote {out} and the per-cell record ({len(cells)} cells, engine {commit})")


def main():
    if sys.argv[1] == "app":
        return write_app(sys.argv[2], sys.argv[3])
    engine_dir, out = sys.argv[1], Path(sys.argv[2])
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    lo_row, hi_row = (int(sys.argv[5]), int(sys.argv[6])) if len(sys.argv) > 6 else (0, NGRID)
    res = json.loads(out.read_text()) if out.exists() else {}
    # an existing RAW.json is resumed: only its missing and failed cells are computed
    cells = [(i, j) for i in range(lo_row, hi_row + 1) for j in range(NGRID + 1 - i)
             if res.get(f"{i},{j}", ["?"])[0] == "?"]
    t0 = time.time()
    with Pool(workers, initializer=_init, initargs=(engine_dir,)) as pool:
        for n, (i, j, prim, tl, dt, ph) in enumerate(pool.imap_unordered(cell, cells, chunksize=2), 1):
            res[f"{i},{j}"] = [prim, tl, round(dt, 2), ph]
            if n % 50 == 0:
                print(f"{n}/{len(cells)} cells, {time.time() - t0:.0f} s", flush=True)
                out.write_text(json.dumps(res))
    out.write_text(json.dumps(res))
    print(f"done {len(cells)} cells in {time.time() - t0:.0f} s -> {out}")


if __name__ == "__main__":
    main()
