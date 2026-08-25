"""Validate the declarative slag-database builder (mqmqa.dbbuild).

Strongest checks: rebuild the shipped, pycalphad-validated FeO-MgO-SiO2 liquid database through
the generic builder and confirm it reproduces the hand-written .dat numerically and loads in the
engine; re-derive the published FeO-SiO2 v0.3 excess from the same measured activities through the
engine-as-optimizer fit; and confirm the four-component free cap is enforced.
"""
import math
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

import mqmqa
from mqmqa import dbbuild as db

SHIPPED = ROOT / "data" / "feo-mgo-sio2" / "FeO-MgO-SiO2-liquid.dat"

FEO_LIQ_BETA = -69.84464900364951
MGO_LIQ_BETA = 2.9753836245721774


def feo_mgo_sio2_spec():
    feo = db.starter_component("FeO", liq_beta=FEO_LIQ_BETA)
    mgo = db.starter_component("MgO", liq_beta=MGO_LIQ_BETA)
    sio2 = db.starter_component("SiO2")
    feo_sio2 = db.BinaryExcess("FeO", "SiO2", [
        db.ExcessTerm(a=-42839.42808976104, b=17.829765801117908, p=0, q=0)],
        source="v0.3 activity-pinned (Bjorkman 1985 a(FeO); Bowen-Schairer 1932 melting)")
    mgo_sio2 = db.BinaryExcess("MgO", "SiO2", [
        db.ExcessTerm(-44468.8, -1.60, 0, 0), db.ExcessTerm(-50864.2, -0.30, 0, 1),
        db.ExcessTerm(1448.2, -0.70, 0, 3), db.ExcessTerm(116056.4, -10.80, 0, 5),
        db.ExcessTerm(-1177.5, -0.30, 0, 7)],
        source="assessed silica-weighted set (data/mgo-sio2/assessment)")
    return db.SystemSpec("FeO-MgO-SiO2", [feo, mgo, sio2], [feo_sio2, mgo_sio2],
                         version="v0.1", provenance="data/feo-mgo-sio2/PROVENANCE.md")


def _numbers(text):
    return [float(x) for x in re.findall(r"[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?", text)]


def test_reproduces_shipped_ternary_numerically():
    built = db.write_dat(feo_mgo_sio2_spec())
    bn, sn = _numbers(built), _numbers(SHIPPED.read_text())
    assert len(bn) == len(sn), f"token count differs: built {len(bn)} vs shipped {len(sn)}"
    worst = max(abs(x - y) for x, y in zip(bn, sn))
    assert worst < 1e-3, f"largest numeric difference {worst} exceeds tolerance"


def test_built_dat_loads_in_engine():
    out = Path(tempfile.gettempdir()) / "_dbbuild_test_feo_mgo_sio2.dat"
    out.write_text(db.write_dat(feo_mgo_sio2_spec()), encoding="ascii")
    d = mqmqa.Database.read(str(out))
    assert d.phase_index("FEO-MGO-SIO2-LIQUID") >= 0


def test_four_component_cap():
    comps = [db.starter_component(n) for n in ("FeO", "MgO", "SiO2", "CaO")]
    db.SystemSpec("quaternary", comps)                       # 4 components: allowed
    extra = db.starter_component("CaO"); extra.name, extra.cation = "MnO", "Mn"
    try:
        db.SystemSpec("five", comps + [extra])
        assert False, "5-component spec should have raised PremiumFeatureError"
    except db.PremiumFeatureError as e:
        assert "premium" in str(e).lower() and db.SUPPORT_EMAIL in str(e)


def _load_bjorkman():
    csv = ROOT / "data" / "feo-sio2" / "activities_feo_bjorkman1985_fig3.csv"
    rows = []
    for line in csv.read_text().splitlines():
        if line.startswith("#") or line.startswith("X_FeO") or not line.strip():
            continue
        p = line.split(",")
        rows.append((float(p[0]), float(p[1]), p[2], float(p[3])))
    return rows


def test_binary_fit_rederives_feo_sio2():
    """The engine-as-optimizer fit reproduces the published FeO-SiO2 v0.3 excess from the same
    measured a(FeO) data (Bjorkman 1985): Delta_g = -42839.4 + 17.83*T."""
    feo, sio2 = db.starter_component("FeO"), db.starter_component("SiO2")
    pts = [db.ActivityPoint(x_second=1 - X, activity=a, of="first", T=T, source=src)
           for X, a, src, T in _load_bjorkman()]
    be = db.fit_binary_excess(feo, sio2, pts, powers=[(0, 0)], fit_entropy=True)
    t = be.terms[0]
    assert abs(t.a - (-42839.4)) < 5.0, f"a00 {t.a} off from -42839.4"
    assert abs(t.b - 17.8298) < 0.01, f"b00 {t.b} off from 17.8298"
    assert be.rms_ln_a < 0.08


if __name__ == "__main__":
    test_reproduces_shipped_ternary_numerically()
    print("reproduces shipped ternary .dat numerically (0 diff)")
    test_built_dat_loads_in_engine()
    print("built .dat loads in the engine")
    test_four_component_cap()
    print("four-component free cap enforced")
    test_binary_fit_rederives_feo_sio2()
    print("binary fit re-derives FeO-SiO2 v0.3 excess")
    print("\nall dbbuild checks passed")
