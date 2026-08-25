"""Worked example: build an open slag database from literature data, end to end.

The workflow for someone who has published measurements but no ChemSage database:

  1. Describe each oxide component with its endmember thermodynamics + a provenance note
     (use the starter library for common oxides, or supply your own sourced Component).
  2. Fit each binary's liquid excess to your measured activities (the engine optimizes it).
  3. Assemble the components + binary excesses into a system and emit a .dat the app loads.

Free self-assessment covers up to four components; five and up is the premium tier.

Run:  PYTHONPATH=python python examples/build_slag_db.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))            # python/

import mqmqa
from mqmqa import dbbuild as db

DATA = HERE.parents[1] / "data"


def load_activity_csv(path, of, x_is_first=True):
    """Read measured activities from a simple CSV (col0 = mole fraction, col1 = activity,
    col2 = source, col3 = T). `of` names which component the activity is for; x_is_first
    flags whether col0 is the mole fraction of the first or second component."""
    pts = []
    for line in Path(path).read_text().splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s[0].isalpha():
            continue
        c = s.split(",")
        x = float(c[0])
        pts.append(db.ActivityPoint(x_second=(1 - x) if x_is_first else x,
                                    activity=float(c[1]), of=of, T=float(c[3]),
                                    source=c[2] if len(c) > 2 else ""))
    return pts


def main():
    print("=" * 70)
    print("STEP 1  components (open endmember data + provenance)")
    feo = db.starter_component("FeO")
    sio2 = db.starter_component("SiO2")
    mgo = db.starter_component("MgO")
    for c in (feo, sio2, mgo):
        print(f"  {c.name:5s}  Tm={c.Tm:.0f} K  dHf={c.dHf/1000:+.0f} kJ/mol   [{c.source[:48]}]")

    print("\n" + "=" * 70)
    print("STEP 2  fit each binary excess to measured activities (engine as optimizer)")
    feo_pts = load_activity_csv(DATA / "feo-sio2" / "activities_feo_bjorkman1985_fig3.csv",
                                of="first", x_is_first=True)   # a(FeO) vs X_FeO
    feo_sio2 = db.fit_binary_excess(feo, sio2, feo_pts, powers=[(0, 0)], fit_entropy=True,
                                    source="Bjorkman 1985 Fig 3 a(FeO), iron-saturated")
    t = feo_sio2.terms[0]
    print(f"  FeO-SiO2:  Delta_g = {t.a:.1f} {t.b:+.4f}*T J/mol   "
          f"(from {len(feo_pts)} points, RMS ln a = {feo_sio2.rms_ln_a:.3f})")
    # MgO-SiO2 here reuses the already-assessed set (its fit needs invariants+immiscibility,
    # beyond a pure activity fit); a user would fit their own the same way as FeO-SiO2.
    mgo_sio2 = db.BinaryExcess("MgO", "SiO2", [
        db.ExcessTerm(-44468.8, -1.60, 0, 0), db.ExcessTerm(-50864.2, -0.30, 0, 1),
        db.ExcessTerm(1448.2, -0.70, 0, 3), db.ExcessTerm(116056.4, -10.80, 0, 5),
        db.ExcessTerm(-1177.5, -0.30, 0, 7)], source="data/mgo-sio2 assessed set")

    print("\n" + "=" * 70)
    print("STEP 3  assemble the system and emit a .dat")
    spec = db.SystemSpec("FeO-MgO-SiO2", [feo, mgo, sio2], [feo_sio2, mgo_sio2],
                         version="user", provenance="user literature compilation")
    out = HERE / "my_slag_db.dat"
    out.write_text(db.write_dat(spec), encoding="ascii")
    d = mqmqa.Database.read(str(out))
    p = d.phase_index("FEO-MGO-SIO2-LIQUID")
    print(f"  wrote {out.name} ({len(spec.components)} components); engine loads it, "
          f"liquid phase index = {p}")

    print("\n" + "=" * 70)
    print("STEP 4  the free cap: five components is premium")
    try:
        db.SystemSpec("five", [db.starter_component(n) for n in ("FeO", "MgO", "SiO2", "CaO")]
                      + [db.starter_component("CaO")])
    except db.PremiumFeatureError as e:
        print(f"  {e}")


if __name__ == "__main__":
    main()
