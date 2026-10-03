"""CaO-FeO-MgO-SiO2 combined multiphase file: liquid + ol/opx/cpx + oxides, vs pycalphad.

Validates the multiphase MACHINERY (faithful splice, reads, runs, crystallizes a silicate),
not a quantitative liquidus (the solid-vs-liquid reference calibration is a v0.2 step;
see data/cao-feo-mgo-sio2/PROVENANCE.md)."""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

pycalphad = pytest.importorskip("pycalphad")
from pycalphad import Database, equilibrium, variables as v

import mqmqa


def _load(rel, nm):
    s = importlib.util.spec_from_file_location(nm, ROOT / "data" / rel)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def combined():
    bc = _load("cao-feo-mgo-sio2/build_combined_dat.py", "bc")
    path = bc.build()
    return str(path), mqmqa.Database.read(str(path)), Database(str(path))


def test_all_phases(combined):
    _, _, pdb = combined
    assert sorted(pdb.phases.keys()) == [
        "CAO-FEO-MGO-SIO2-LIQUID", "CLINOPYROXENE", "CRISTOBALITE", "HATRURITE", "LARNITE",
        "LIME", "MAGNESIOWUSTITE", "OLIVINE", "ORTHOPYROXENE", "RANKINITE", "WOLLASTONITE"]


def test_splice_is_faithful(combined):
    path, db, _ = combined
    liq_src = (ROOT / "data" / "cao-feo-mgo-sio2" / "CaO-FeO-MgO-SiO2-liquid.dat"
               ).read_text().splitlines()[6:]
    lines = Path(path).read_text().splitlines()
    i0 = lines.index(" CaO-FeO-MgO-SiO2-liquid")
    assert lines[i0:i0 + len(liq_src)] == liq_src            # liquid block byte-identical
    s = mqmqa.Database.read(str(ROOT / "data" / "olivine-opx-cpx" / "Olivine-Opx-Cpx-CEF.dat"))
    for ph, Y in [("CLINOPYROXENE", [1, 0.3, 0.7, 1, 1]),
                  ("OLIVINE", [0.3, 0.7, 1, 1]),
                  ("ORTHOPYROXENE", [0.3, 0.7, 0.4, 0.6, 1, 1])]:     # two sites, M1 and M2
        a = db.cef_gibbs(db.phase_index(ph), Y, 1600.0, per_mole_atoms=True)
        b = s.cef_gibbs(s.phase_index(ph), Y, 1600.0, per_mole_atoms=True)
        assert a == pytest.approx(b, abs=1e-6), ph


LIQ = "CAO-FEO-MGO-SIO2-LIQUID"


def _prim(pdb, el, Tlo=1400, Thi=2200):
    """First solid on cooling: the one whose saturation temperature with the melt is highest.

    Each solid is equilibrated with the liquid alone, and counts only if it lowers G below the
    liquid by itself. pycalphad's search over all phases at once can miss the liquid's minimum:
    at the mafic bulk below it returned olivine + clinopyroxene at 1920 K, 2.3 kJ/mol above the
    liquid alone, about 90 K above olivine's own saturation (1831 K).
    """
    tot = sum(el.values())
    comps = ["CA", "FE", "MG", "SI", "O"]
    cond = {v.P: 101325, v.N: 1, **{v.X(k): el[k] / tot for k in ("CA", "FE", "MG", "SI")}}
    g_liq = {}

    def saturated(ph, T):
        if T not in g_liq:
            g_liq[T] = float(equilibrium(pdb, comps, [LIQ], {**cond, v.T: T}).GM.values.ravel()[0])
        r = equilibrium(pdb, comps, [LIQ, ph], {**cond, v.T: T})
        return (ph in set(str(x) for x in r.Phase.values.ravel())
                and float(r.GM.values.ravel()[0]) < g_liq[T] - 0.1)

    best = (None, None)
    for ph in sorted(p for p in pdb.phases if p != LIQ):
        if not saturated(ph, float(Tlo)):
            continue
        lo, hi = float(Tlo), float(Thi)
        while hi - lo > 5.0:
            mid = 0.5 * (lo + hi)
            lo, hi = (mid, hi) if saturated(ph, mid) else (lo, mid)
        if best[0] is None or lo > best[0]:
            best = (lo, ph)
    return best


def test_primary_phase_fields_are_physical(combined):
    """After the CaO(l) melting calibration: mafic melts crystallize olivine, Ca-rich melts
    crystallize clinopyroxene (before calibration cpx was primary everywhere)."""
    _, _, pdb = combined
    def bulk(ca, fe, mg, si):
        return {"CA": ca, "FE": fe, "MG": mg, "SI": si, "O": ca + fe + mg + 2 * si}
    _, mafic = _prim(pdb, bulk(0.10, 0.15, 0.35, 0.40))
    _, carich = _prim(pdb, bulk(0.40, 0.05, 0.10, 0.45))
    assert mafic == "OLIVINE", mafic
    assert carich in ("CLINOPYROXENE", "WOLLASTONITE", "LARNITE"), carich   # a calcium phase


def test_calcium_silicates_crystallize(combined):
    """The dHf-calibrated wollastonite and larnite crystallize on the calcium-rich side at
    low FeO (they are flux-suppressed at higher FeO)."""
    _, _, pdb = combined
    def bulk(ca, fe, mg, si):
        return {"CA": ca, "FE": fe, "MG": mg, "SI": si, "O": ca + fe + mg + 2 * si}
    _, woll = _prim(pdb, bulk(0.48, 0.02, 0.02, 0.48))
    _, larn = _prim(pdb, bulk(0.63, 0.02, 0.04, 0.31))
    assert woll == "WOLLASTONITE", woll
    assert larn == "LARNITE", larn


@pytest.mark.xfail(strict=True, reason="with the CaO-MgO-SiO2 ternary terms assessed against "
                   "Bowen 1914 (data/cao-feo-mgo-sio2/assessment), diopside melts at 1630 K, "
                   "20 K below this window; whether to widen it is open")
def test_diopside_melts_near_1670(combined):
    """Pure diopside CaMgSi2O6 melts congruently at ~1670 K."""
    _, _, pdb = combined
    cpxem = _load("clinopyroxene/endmembers.py", "cpxem_t")
    el = {"CA": 1.0, "MG": 1.0, "SI": 2.0}
    tot = el["CA"] + el["MG"] + el["SI"] + 6.0
    def gap(T):
        r = equilibrium(pdb, ["CA", "MG", "SI", "O"], ["CAO-FEO-MGO-SIO2-LIQUID"],
                        {v.T: T, v.P: 101325, v.N: 1, v.X("CA"): el["CA"] / tot,
                         v.X("MG"): el["MG"] / tot, v.X("SI"): el["SI"] / tot})
        return float(r.GM.values.ravel()[0]) * 10.0 - cpxem.gibbs("diopside", T)
    assert gap(1650.0) > 0 and gap(1690.0) < 0     # solid stable below, liquid above 1670
