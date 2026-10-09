"""Chunked crystallization export: compute a row range per process (fresh numba JIT each),
then assemble. Works around a cumulative numba/LLVM JIT crash (~700 equilibria) on Windows."""
import importlib.util, json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
CHUNKS = HERE / "_chunks"; CHUNKS.mkdir(exist_ok=True)
OUT = HERE.parents[1] / "web" / "crystallization_cao_mgo_sio2.json"
X_FE, NGRID = 0.05, 60
PHASES = ["OLIVINE","ORTHOPYROXENE","CLINOPYROXENE","WOLLASTONITE","RANKINITE","LARNITE",
          "HATRURITE","CRISTOBALITE","LIME","MAGNESIOWUSTITE"]

def compute(lo, hi):
    from pycalphad import Database
    ex = importlib.util.spec_from_file_location("ex", HERE/"export_crystallization_json.py")
    xm = importlib.util.module_from_spec(ex); ex.loader.exec_module(xm)
    bc = importlib.util.spec_from_file_location("bc", HERE/"build_combined_dat.py")
    m = importlib.util.module_from_spec(bc); bc.loader.exec_module(m)
    pdb = Database(str(m.build())); idx = {p:str(i) for i,p in enumerate(PHASES)}
    s = 1.0 - X_FE; out = {}
    for i in range(lo, min(hi, NGRID)+1):
        xca = s*i/NGRID
        for j in range(NGRID+1-i):
            xsi = s*j/NGRID; xmg = s - xca - xsi
            if xmg < -1e-9: continue
            el = {"CA":xca,"FE":X_FE,"MG":max(xmg,0.0),"SI":xsi}
            el["O"] = el["CA"]+el["FE"]+el["MG"]+2*el["SI"]
            out[f"{i},{j}"] = list(xm.primary(pdb, el, idx))   # the one scan both exports share
        print(f"row {i} done", flush=True)
    (CHUNKS/f"chunk_{lo}.json").write_text(json.dumps(out))

def assemble():
    field, tliq = {}, {}
    for f in CHUNKS.glob("chunk_*.json"):
        for k,(prim,tl) in json.loads(f.read_text()).items():
            i,j = map(int,k.split(",")); field[(i,j)] = prim
            if tl is not None: tliq[(i,j)] = tl
    rows = ["".join(field.get((i,j),".") for j in range(NGRID+1-i)) for i in range(NGRID+1)]
    trows = [[tliq.get((i,j),None) for j in range(NGRID+1-i)] for i in range(NGRID+1)]
    payload = {"system":"CaO-MgO-SiO2 at FeO = %d mol%% (cation)"%round(X_FE*100),
        "corners":["CaO","MgO","SiO2"],
        "basis":"cation mole fraction of CaO-MgO-SiO2 (x_Ca, x_Si; x_Mg = rest), FeO fixed",
        "note":"Assessed multiphase result: silicates crystallizing from the calibrated "
               "CaO-FeO-MgO-SiO2 melt, validated vs pycalphad.",
        "phases":PHASES, "ngrid":NGRID, "field_rows":rows, "liquidus_C":trows}
    OUT.write_text(json.dumps(payload, separators=(",",":")), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB, ngrid={NGRID}, chunks={len(list(CHUNKS.glob('chunk_*.json')))})")

if __name__ == "__main__":
    # compute LO [HI]: rows LO..HI inclusive (default six rows)
    (assemble() if sys.argv[1]=="assemble"
     else compute(int(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else int(sys.argv[1])+5))
