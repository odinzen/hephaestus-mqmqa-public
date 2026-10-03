"""Magnesiowustite (Fe,Mg)O: the rock-salt solid solution between iron-saturated wustite and
periclase, which are fully miscible at slag temperatures.

Per mole of (Fe,Mg)O, one metal site mixing Fe and Mg, the endmembers the binaries use (FeO from
data/feo-sio2/build_dat.py, MgO from data/mgo-sio2/build_dat.py) and a subregular excess

    G_ex = y_Fe y_Mg [L0 + L1 (y_Fe - y_Mg)]

assessed in data/magnesiowustite/assessment against the FeO and MgO activities and the
olivine tie-lines Nafziger & Muan (1967) report at 1473 K.
"""
import importlib.util
import math
from pathlib import Path

_D = Path(__file__).resolve().parents[1]


def _load(name, rel):
    s = importlib.util.spec_from_file_location(name, _D / rel)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


_feo = _load("mw_feo_bd", "feo-sio2/build_dat.py")
_mgo = _load("mw_mgo_bd", "mgo-sio2/build_dat.py")

R = 8.3145
# assessed 2026-09-30 (assessment/assess.py; total cost 9.43, RMS 0.95)
L0 = 12965.2      # J per mole of (Fe,Mg)O
L1 = 1158.7


def coeffs(name):
    """Six Gibbs coefficients (1, T, TlnT, T^2, T^3, 1/T) of FEO or MGO, the solid oxides."""
    ox = _feo.OXIDES["FeO"] if name == "FEO" else _mgo.OXIDES["MgO"]
    return list(_feo.solid_gibbs_coeffs(ox["dHf"], ox["S298"], ox["a"], ox["b"], ox["c"]))


def g_end(name, T):
    c = coeffs(name)
    return c[0] + c[1] * T + c[2] * T * math.log(T) + c[3] * T * T + c[4] * T ** 3 + c[5] / T


def gibbs(x, T):
    """G per mole of (Fe,Mg)O at y_Fe = x."""
    ideal = sum(v * math.log(v) for v in (x, 1 - x) if v > 0.0)
    return (x * g_end("FEO", T) + (1 - x) * g_end("MGO", T) + R * T * ideal
            + x * (1 - x) * (L0 + L1 * (2 * x - 1)))


def ln_gamma(x, T):
    """(ln gamma_FeO, ln gamma_MgO) at y_Fe = x."""
    ex = x * (1 - x) * (L0 + L1 * (2 * x - 1))
    d = (1 - 2 * x) * (L0 + L1 * (2 * x - 1)) + 2 * L1 * x * (1 - x)
    return (ex + (1 - x) * d) / (R * T), (ex - x * d) / (R * T)


def subl_block(elements, name="MAGNESIOWUSTITE"):
    """ChemSage SUBL lines for a file whose element order is `elements` (upper case)."""
    fmt = lambda v: f"{v:.10E}"
    L = [f" {name}", " SUBL"]
    for em, cat in (("FEO", "FE"), ("MGO", "MG")):
        st = [1.0 if e in (cat, "O") else 0.0 for e in elements]
        L += [f" {em}", "   1   1   " + "   ".join(f"{v:.1f}" for v in st),
              "   6000.0000   " + "   ".join(fmt(v) for v in coeffs(em))]
    L += ["   2", "   1.000000   1.000000", "   2   1", "   FE   MG", "   O", "   1   2", "   1   1",
          "   3   1   2   3", "   2"]
    L += ["   " + "   ".join(fmt(v) for v in (Lv, 0, 0, 0, 0, 0)) for Lv in (L0, L1)]
    L.append("   0")
    return L
