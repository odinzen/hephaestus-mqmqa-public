"""Build the open FeO-MgO-SiO2 ternary liquid-slag MQMQA database (ChemSage SUBQ .dat).

The iron-magnesium-silicate melt of the steel-slag / olivine family, assembled from the
two shipped binary liquids plus a near-ideal FeO-MgO edge - no new ternary fit:

  - MgO-SiO2 excess: the assessed 5-term silica-weighted set (data/mgo-sio2, Y-basis
    (0,q) = chi_Si^q, q = 0,1,3,5,7 each a + b*T), on (Mg,Si,O,O).
  - FeO-SiO2 excess: the assessed v0.4 set (data/feo-sio2, [0,0] a + b*T plus [1,0],
    [0,3], [0,5]), on (Fe,Si,O,O), AND the FeO(l) below-1650 K correction assessed with it
    (a second temperature interval on the FeO endmember).
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

# FeO(l) below-melting correction, assessed with the FeO-SiO2 liquid (data/feo-sio2/assessment)
FEO_LIQ_BETA = _feo.FEO_LIQ_BETA
# MgO(l) carries the liquid heat capacity assessed with the MgO-SiO2 liquid (data/mgo-sio2,
# MGO_LIQ_DCP), inside _mgo.liquid_gibbs_coeffs; nothing to add here.
MGO_LIQ_DCP = _mgo.MGO_LIQ_DCP

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
# FeO-SiO2 assessed, on (Fe,Si,O,O):
EX_FEO_SIO2 = _feo.assessed_excess(li=(1, 3, 4, 4))
# MgO-SiO2 assessed (silica-weighted (0,q)=chi_Si^q), on (Mg,Si,O,O); q is on Si (position 2):
EX_MGO_SIO2 = _mgo.assessed_excess(li=(2, 3, 4, 4))
# Ternary-level terms, assessed in assessment/assess.py: the Fe-Si interaction with Mg as the
# additional cation, the Mg-Si interaction with Fe (Poschmann Eq. 25-26, r = 1), and the FeO-MgO
# interaction, J. Zero terms are not written.
# assessed 2026-10-05 together with the MgO-SiO2 liquid (three-way fit N1, data/mgo-sio2/assessment/
# joint3.py; FMS cost 150.6; B&S 1935 liquidus 21/19/11 K mean absolute in the olivine/pyroxene/silica
# fields, 29 of 37 primary; N&M solidus 36 K (ol+px) and 42 K (ol+mw) low)
TERNARY_EXCESS = (-6604.273460398276, 16774.796051303405, 9064.532993952309)


def ternary_excess(vals=None):
    t_fesi_mg, t_mgsi_fe, a_femg = TERNARY_EXCESS if vals is None else vals
    q = lambda li, add, c: dict(code="Q", li=li, exp=[0, 0, 1 if add else 0, 0],
                                coeffs=[c, 0, 0, 0, 0, 0], add=add)
    return [t for t in (q([1, 3, 4, 4], 2, t_fesi_mg), q([2, 3, 4, 4], 1, t_mgsi_fe),
                        q([1, 2, 4, 4], 0, a_femg)) if t["coeffs"][0]]


EXCESS = EX_FEO_SIO2 + EX_MGO_SIO2 + ternary_excess()


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
    """Endmember Gibbs intervals. FeO carries the assessed below-1650 K correction; MgO's liquid
    heat capacity is already in its fusion coefficients."""
    d = OXIDES[name]
    base = d["src"].liquid_gibbs_coeffs(d["ox"])
    if name == "FeO":
        return _below_tm_intervals(base, _feo.FEO_TM, FEO_LIQ_BETA)
    return [(6000.0, base)]


def _mqmx_block(excess):
    out = []
    for ex in excess:
        out.append("   1")
        out.append(" " + ex["code"] + "   " + "   ".join(str(i) for i in ex["li"])
                   + "   " + "   ".join(str(e) for e in ex["exp"]))
        out.append("  " + "   ".join("0.00000000" for _ in range(6)))
        out.append("  " + "   ".join("0.00000000" for _ in range(6)))
        # a ternary term names its additional cation (1-based; exp[2] is its exponent r)
        out.append(f"   {ex.get('add', 0)}   0   " + "   ".join(_fmt(c) for c in ex["coeffs"]))
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
    z_mgsi = _mgo.mgsi_mixed_z()                          # the binary's Mg-Si ordering, if not default
    ap(f"   3   {3 if z_mgsi is None else 4}")            # n_pairs, n_quads (MQMZ rows)
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
    # Si in its own group: the two basic oxides extrapolate the silicate binaries
    # asymmetrically (Toop-like). With all three in one group the ternary grew a two-liquid
    # region near the orthosilicate join that neither binary has.
    ap("   1   1   2")                                    # cation groups
    ap("  2.00000")                                       # anion charge magnitude
    ap("   1")                                            # anion group
    ap("   1   2   3")                                    # pair cation indices
    ap("   1   1   1")                                    # pair anion indices
    for i, name in enumerate(ORDER, start=1):
        z_cat = OXIDES[name]["charge"] * Z_PER_CHARGE
        z_o = 2 * Z_PER_CHARGE
        ap(f"   {i}   {i}   {an_idx}   {an_idx}   "
           f"{z_cat:.7f}   {z_cat:.7f}   {z_o:.7f}   {z_o:.7f}")
    if z_mgsi is not None:
        mg, si = ORDER.index("MgO") + 1, ORDER.index("SiO2") + 1
        ap(f"   {mg}   {si}   {an_idx}   {an_idx}   " + "   ".join(f"{z:.7f}" for z in z_mgsi))
    L.extend(_mqmx_block(excess))
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    out = HERE / "FeO-MgO-SiO2-liquid.dat"
    out.write_text(build(), encoding="ascii")
    print(f"wrote {out}")
