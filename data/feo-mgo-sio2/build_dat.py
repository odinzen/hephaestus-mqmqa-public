"""Build the open FeO-MgO-SiO2 ternary liquid-slag MQMQA database (ChemSage SUBQ .dat).

The iron-magnesium-silicate melt of the steel-slag / olivine family, assembled from the
two shipped binary liquids plus a near-ideal FeO-MgO edge - no new ternary fit:

  - MgO-SiO2 excess: the assessed 5-term silica-weighted set (data/mgo-sio2, Y-basis
    (0,q) = chi_Si^q, q = 0,1,3,5,7 each a + b*T), on (Mg,Si,O,O).
  - FeO-SiO2 excess: the v0.3 activity-pinned symmetric term (data/feo-sio2,
    Delta_g(Fe,Si)/O = -42839.4 + 17.83*T), on (Fe,Si,O,O), AND the FeO(l) below-1650 K
    phase-diagram recalibration (a second temperature interval on the FeO endmember).
  - FeO-MgO edge: IDEAL. Molten (Fe,Mg)O is a near-ideal solution of two similar divalent
    oxides (complete miscibility, magnesiowustite is nearly ideal); no excess term is added
    for v0.1. A small interaction from a full assessment is a documented v0.2 target.

Ternary (3-cation) excess is taken as zero (Muggianu extrapolation from the binaries), the
standard MQMQA default when no ternary data force a correction. Everything here is reused
verbatim from the binary builders (single source of truth); build_ternary_validation.py
proves the ternary reduces to each shipped binary .dat exactly in its binary limit.

Cation indexing in the .dat: Fe=1, Mg=2, Si=3; the single anion O=4 (anions are numbered
after the cations). So the excess quadruplets are (Fe,Si,O,O)=[1,3,4,4],
(Mg,Si,O,O)=[2,3,4,4], and an FeO-MgO term would be [1,2,4,4].
"""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, HERE.parent / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# reuse the binary builders' oxide data + endmember Gibbs assembly (no re-derivation)
_feo = _load("bd_feo_sio2", "feo-sio2/build_dat.py")
_mgo = _load("bd_mgo_sio2", "mgo-sio2/build_dat.py")

# FeO(l) v0.3 below-melting correction (from data/feo-sio2/v03_fit.py)
FEO_LIQ_BETA = -69.84464900364951
# MgO(l) below-melting correction, fit so the MgO-SiO2 liquid melts the measured (Robie-
# Hemingway) forsterite - the olivine CEF endmember, data/olivine - congruently at 2163 K
# (Bowen & Schairer 1935). Analytic single-point fit, verified to reproduce 2163 K exactly;
# see olivine_join.py::fit_mgo_beta. Orthogonal to the MgO-SiO2 activities (a pure MgO
# endmember shift), so it moves only the absolute stability / forsterite liquidus.
MGO_LIQ_BETA = 2.9753836245721774

Z_PER_CHARGE = _feo.Z_PER_CHARGE  # 1.3774438 / 2, identical in both binaries
assert Z_PER_CHARGE == _mgo.Z_PER_CHARGE

ELEMENTS = [("Fe", 55.845), ("Mg", 24.305), ("Si", 28.085), ("O", 15.9994)]

# name -> (oxide dict source module, stoich {el: n}, quad (a,b), n_intervals-source)
CATIONS = ["Fe", "Mg", "Si"]  # cation order fixes the excess indices below
OXIDES = {
    "FeO": dict(ox=_feo.OXIDES["FeO"], src=_feo, stoich={"Fe": 1.0, "O": 1.0}, quad=(1.0, 1.0),
                charge=2.0, cation="Fe"),
    "MgO": dict(ox=_mgo.OXIDES["MgO"], src=_mgo, stoich={"Mg": 1.0, "O": 1.0}, quad=(1.0, 1.0),
                charge=2.0, cation="Mg"),
    "SiO2": dict(ox=_feo.OXIDES["SiO2"], src=_feo, stoich={"Si": 1.0, "O": 2.0}, quad=(1.0, 2.0),
                 charge=4.0, cation="Si"),
}
ORDER = ["FeO", "MgO", "SiO2"]

# --- excess terms, remapped to ternary indices (Fe=1, Mg=2, Si=3, O=4) ---
# FeO-SiO2 v0.3 (activity-pinned symmetric), on (Fe,Si,O,O):
EX_FEO_SIO2 = [
    dict(code="Q", li=[1, 3, 4, 4], exp=[0, 0, 0, 0],
         coeffs=[-42839.42808976104, 17.829765801117908, 0, 0, 0, 0]),
]
# MgO-SiO2 assessed (silica-weighted (0,q)=chi_Si^q), on (Mg,Si,O,O); q is on Si (position 2):
EX_MGO_SIO2 = [
    dict(code="Q", li=[2, 3, 4, 4], exp=[0, 0, 0, 0], coeffs=[-44468.8, -1.60, 0, 0, 0, 0]),
    dict(code="Q", li=[2, 3, 4, 4], exp=[0, 1, 0, 0], coeffs=[-50864.2, -0.30, 0, 0, 0, 0]),
    dict(code="Q", li=[2, 3, 4, 4], exp=[0, 3, 0, 0], coeffs=[1448.2, -0.70, 0, 0, 0, 0]),
    dict(code="Q", li=[2, 3, 4, 4], exp=[0, 5, 0, 0], coeffs=[116056.4, -10.80, 0, 0, 0, 0]),
    dict(code="Q", li=[2, 3, 4, 4], exp=[0, 7, 0, 0], coeffs=[-1177.5, -0.30, 0, 0, 0, 0]),
]
EXCESS = EX_FEO_SIO2 + EX_MGO_SIO2  # FeO-MgO edge is ideal (no term)


def _fmt(x):
    return f"{x:.12E}"


def _below_tm_intervals(base, Tm, beta):
    """Two Gibbs intervals: base + beta*(T-Tm) below Tm (continuous, zero at/above Tm)."""
    if not beta:
        return [(6000.0, base)]
    corr = list(base)
    corr[0] += -Tm * beta
    corr[1] += beta
    return [(Tm, corr), (6000.0, base)]


def _intervals(name):
    """Endmember Gibbs intervals. FeO carries the v0.3 below-1650 K activity/liquidus
    calibration; MgO carries the below-3098 K forsterite-liquidus calibration."""
    d = OXIDES[name]
    base = d["src"].liquid_gibbs_coeffs(d["ox"])
    if name == "FeO":
        return _below_tm_intervals(base, _feo.FEO_TM, FEO_LIQ_BETA)
    if name == "MgO":
        return _below_tm_intervals(base, _mgo.MGO_TM, MGO_LIQ_BETA)
    return [(6000.0, base)]


def _mqmx_block(excess):
    out = []
    for ex in excess:
        out.append("   1")
        out.append(" " + ex["code"] + "   " + "   ".join(str(i) for i in ex["li"])
                   + "   " + "   ".join(str(e) for e in ex["exp"]))
        out.append("  " + "   ".join("0.00000000" for _ in range(6)))
        out.append("  " + "   ".join("0.00000000" for _ in range(6)))
        out.append("   0   0   " + "   ".join(_fmt(c) for c in ex["coeffs"]))
    out.append("   0")
    return out


def build(excess=EXCESS, version="v0.1"):
    L = []
    ap = L.append
    ap(f" System FeO-MgO-SiO2  open iron-magnesium-silicate slag database {version} "
       f"(provenance: data/feo-mgo-sio2/PROVENANCE.md)")
    ap(f"    {len(ELEMENTS)}    1    3    0")            # n_el, n_soln, n_cat, n_stoich
    ap(" " + "                       ".join(e[0] for e in ELEMENTS))
    ap("   " + "              ".join(f"{m:.9f}" for _, m in ELEMENTS))
    ap("    6   1   2   3   4   5   6")
    ap("    6   1   2   3   4   5   6")

    ap(" FeO-MgO-SiO2-liquid")
    ap(" SUBQ")
    ap("   3   3")                                       # n_pairs, n_quads (MQMZ rows)
    for name in ORDER:
        d = OXIDES[name]
        stoich_el = [d["stoich"].get(el, 0.0) for el, _ in ELEMENTS]
        intervals = _intervals(name)
        ap(f" {name}")
        ap(f"   1   {len(intervals)}   " + "   ".join(f"{s:.1f}" for s in stoich_el))
        for t_max, coeffs in intervals:
            ap(f"  {t_max:.4f}   " + "   ".join(_fmt(v) for v in coeffs))
        ap("  " + "   ".join(f"{v:.5f}" for v in [d["quad"][0], d["quad"][1], 0.0, 0.0, 0.0]))
        ap("  1.3774438")

    n_cat = len(CATIONS)
    an_idx = n_cat + 1                                   # O is numbered after the cations
    ap(f"   {n_cat}   1")                                 # n_cat, n_an
    ap(" Fe+2                     Mg+2                     Si+4")
    ap(" O")
    ap("  2.00000      2.00000      4.00000")             # cation charges
    ap("   1   1   1")                                    # cation groups
    ap("  2.00000")                                       # anion charge magnitude
    ap("   1")                                            # anion group
    ap("   1   2   3")                                    # pair cation indices
    ap("   1   1   1")                                    # pair anion indices
    for i, name in enumerate(ORDER, start=1):
        z_cat = OXIDES[name]["charge"] * Z_PER_CHARGE
        z_o = 2 * Z_PER_CHARGE
        ap(f"   {i}   {i}   {an_idx}   {an_idx}   "
           f"{z_cat:.7f}   {z_cat:.7f}   {z_o:.7f}   {z_o:.7f}")
    L.extend(_mqmx_block(excess))
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    out = HERE / "FeO-MgO-SiO2-liquid.dat"
    out.write_text(build(), encoding="ascii")
    print(f"wrote {out}")
