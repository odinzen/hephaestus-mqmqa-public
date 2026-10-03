"""The Ca-Fe-Mg-Si oxide liquid: the CaO-FeO-MgO-SiO2 slag melt (ChemSage SUBQ .dat).

The four-oxide silicate melt of the steel-slag / basalt family, assembled from the shipped
binary liquids with Ca, Fe and Mg in one chemical group and Si in its own, the grouping of the
FeO-MgO-SiO2 file, so each ternary face is its shipped ternary exactly:

  - CaO-SiO2  : the assessed v0.4 silica-weighted set (data/cao-sio2)
  - FeO-SiO2  : the assessed v0.4 set, plus the FeO(l) below-1650 K interval (data/feo-sio2)
  - MgO-SiO2  : the assessed silica-weighted set (data/mgo-sio2)
  - FeO-MgO and the Fe-Mg-Si ternary terms: data/feo-mgo-sio2 (assessed there)
  - CaO-MgO and the Ca-Mg-Si ternary terms: CMS_TERNARY below, assessed against Bowen (1914)
  - CaO-FeO : IDEAL, a near-ideal mixture of two divalent oxides (complete miscibility)

Everything is reused verbatim from the shipped binary builders (single source of truth);
in each binary limit this quaternary reduces to the corresponding shipped binary liquid.
Cation indexing: Ca=1, Fe=2, Mg=3, Si=4; the single anion O=5. So the excess quadruplets
are (Ca,Si,O,O)=[1,4,5,5], (Fe,Si,O,O)=[2,4,5,5], (Mg,Si,O,O)=[3,4,5,5].
"""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
D = HERE.parent


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, D / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_fms = _load("bd_fms", "feo-mgo-sio2/build_dat.py")   # FeO, MgO endmembers + excesses + betas
_cao = _load("bd_cao", "cao-sio2/build_dat.py")       # CaO endmember (+ shared SiO2)

Z_PER_CHARGE = _cao.Z_PER_CHARGE
assert Z_PER_CHARGE == _fms.Z_PER_CHARGE

ELEMENTS = [("Ca", 40.078), ("Fe", 55.845), ("Mg", 24.305), ("Si", 28.085), ("O", 15.9994)]
CATIONS = ["Ca", "Fe", "Mg", "Si"]                    # Ca=1, Fe=2, Mg=3, Si=4; O=5
ORDER = ["CaO", "FeO", "MgO", "SiO2"]
# Si alone in group 2 makes the extrapolation of the three silicate binaries Toop-like with
# the basic oxides as one family, as in data/feo-mgo-sio2 (PROVENANCE.md there).
GROUPS = {"Ca": 1, "Fe": 1, "Mg": 1, "Si": 2}

# No CaO(l) correction since 2026-09-29. v0.2 shifted CaO(l) below its melting point so
# diopside melted at 1670 K, then gave the calcium silicates their own enthalpy calibrations
# to undo that shift on the CaO-SiO2 face. With the binaries assessed on the measured solids,
# each face of this liquid is its binary exactly, and diopside melts near 1870 K: the
# CaO-MgO-SiO2 liquid lacks a ternary interaction worth about -19 kJ per CaMgSi2O6 at 1670 K.
# That belongs in a ternary term (PROVENANCE.md), not in the CaO endmember.
CAO_TM = _cao.OXIDES["CaO"]["Tm"]                     # 2845 K
CAO_LIQ_BETA = 0.0

OXIDES = {
    "CaO": dict(src=_cao, ox=_cao.OXIDES["CaO"], charge=2.0, quad=(1.0, 1.0),
                beta=(CAO_TM, CAO_LIQ_BETA) if CAO_LIQ_BETA else None),
    "FeO": dict(src=_fms._feo, ox=_fms._feo.OXIDES["FeO"], charge=2.0, quad=(1.0, 1.0),
                beta=(_fms._feo.FEO_TM, _fms.FEO_LIQ_BETA)),
    "MgO": dict(src=_fms._mgo, ox=_fms._mgo.OXIDES["MgO"], charge=2.0, quad=(1.0, 1.0),
                beta=None),                      # its liquid Cp is in the fusion coefficients
    "SiO2": dict(src=_cao, ox=_cao.OXIDES["SiO2"], charge=4.0, quad=(1.0, 2.0), beta=None),
}
STOICH = {"CaO": {"Ca": 1.0, "O": 1.0}, "FeO": {"Fe": 1.0, "O": 1.0},
          "MgO": {"Mg": 1.0, "O": 1.0}, "SiO2": {"Si": 1.0, "O": 2.0}}


def _remap(term, m):
    t = dict(term); t["li"] = [m.get(i, i) for i in term["li"]]
    if t.get("add"):
        t["add"] = m[t["add"]]
    return t


# FeO-SiO2 and MgO-SiO2 excesses from feo-mgo-sio2 (Fe=1,Mg=2,Si=3,O=4), remapped to the
# quaternary indices Fe=2, Mg=3, Si=4, O=5.
_M = {1: 2, 2: 3, 3: 4, 4: 5}
EX_CAO_SIO2 = _cao.assessed_excess(li=(1, 4, 5, 5))

# CaO-MgO-SiO2 ternary-level terms, assessed in assessment/assess.py against Bowen (1914): the
# Ca-Si interaction with Mg as the additional cation, the Mg-Si interaction with Ca (Poschmann
# Eq. 25-26, r = 1), and the CaO-MgO interaction, each a + bT in J. Zero terms are not written.
# assessed 2026-09-30 on the MgO-SiO2 v0.3 liquid (40 Bowen 1914 points, cost 72.1, 37 of 40
# primary phases; forsterite and pyroxene fields within 11-12 K on average, the silica field
# 43 K high, diopside congruent at 1630 K against 1664-1670 K measured)
CMS_TERNARY = ((-20354.6, 0.0), (491.0, 0.0), (-572.9, 0.0))


def cms_excess(vals=None):
    casi_mg, mgsi_ca, camg = CMS_TERNARY if vals is None else vals
    q = lambda li, add, ab: dict(code="Q", li=li, exp=[0, 0, 1 if add else 0, 0],
                                 coeffs=[ab[0], ab[1], 0, 0, 0, 0], add=add)
    return [t for t in (q([1, 4, 5, 5], 3, casi_mg), q([3, 4, 5, 5], 1, mgsi_ca),
                        q([1, 3, 5, 5], 0, camg)) if any(t["coeffs"])]


EXCESS = (EX_CAO_SIO2
          + [_remap(t, _M) for t in _fms.EX_FEO_SIO2]
          + [_remap(t, _M) for t in _fms.EX_MGO_SIO2]
          + [_remap(t, _M) for t in _fms.ternary_excess()]
          + cms_excess())                                     # CaO-FeO ideal


def _fmt(x):
    return f"{x:.12E}"


def _intervals(name):
    d = OXIDES[name]
    base = d["src"].liquid_gibbs_coeffs(d["ox"])
    if d["beta"] is None:
        return [(6000.0, base)]
    Tm, beta = d["beta"]
    corr = list(base); corr[0] += -Tm * beta; corr[1] += beta
    return [(Tm, corr), (6000.0, base)]


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


def _subset(excess, cations):
    """The excess terms of a sub-system, reindexed; a term naming an absent cation drops."""
    new = {CATIONS.index(c) + 1: k for k, c in enumerate(cations, start=1)}
    new[len(CATIONS) + 1] = len(cations) + 1
    out = []
    for ex in excess:
        if all(i in new for i in ex["li"]) and ex.get("add", 0) in (0, *new):
            out.append(_remap(ex, new))
    return out


def build(excess=EXCESS, version="v0.3", cations=CATIONS):
    """The liquid .dat; `cations` picks a sub-system (a face of the quaternary)."""
    assert set(cations) <= set(CATIONS) and "Si" in cations
    cations = [c for c in CATIONS if c in cations]
    excess = _subset(excess, cations) if cations != CATIONS else excess
    elements = [e for e in ELEMENTS if e[0] in cations or e[0] == "O"]
    order = [o for o, c in zip(ORDER, CATIONS) if c in cations]
    L = []
    ap = L.append
    ap(f" System {'-'.join(order)}  open calcium-iron-magnesium-silicate slag database "
       f"{version} (provenance: data/cao-feo-mgo-sio2/PROVENANCE.md)")
    ap(f"    {len(elements)}    1    {len(cations)}    0")
    ap(" " + "                       ".join(e[0] for e in elements))
    ap("   " + "              ".join(f"{m:.9f}" for _, m in elements))
    ap("    6   1   2   3   4   5   6")
    ap("    6   1   2   3   4   5   6")

    ap(f" {'-'.join(order)}-liquid")
    ap(" SUBQ")
    # the MgO-SiO2 binary's Mg-Si ordering, if not the default
    z_mgsi = _fms._mgo.mgsi_mixed_z() if {"Mg", "Si"} <= set(cations) else None
    ap(f"   {len(cations)}   {len(cations) + (z_mgsi is not None)}")   # n_pairs, n_quads
    for name in order:
        d = OXIDES[name]
        stoich_el = [STOICH[name].get(el, 0.0) for el, _ in elements]
        intervals = _intervals(name)
        ap(f" {name}")
        ap(f"   1   {len(intervals)}   " + "   ".join(f"{s:.1f}" for s in stoich_el))
        for t_max, coeffs in intervals:
            ap(f"  {t_max:.4f}   " + "   ".join(_fmt(v) for v in coeffs))
        ap("  " + "   ".join(f"{v:.5f}" for v in [d["quad"][0], d["quad"][1], 0.0, 0.0, 0.0]))
        ap("  1.3774438")

    n_cat = len(cations)
    an_idx = n_cat + 1
    ap(f"   {n_cat}   1")
    ap(" " + "                     ".join(f"{c}+{int(OXIDES[o]['charge'])}" for c, o in zip(cations, order)))
    ap(" O")
    ap("  " + "      ".join(f"{OXIDES[o]['charge']:.5f}" for o in order))
    ap("   " + "   ".join(str(GROUPS[c]) for c in cations))
    ap("  2.00000")
    ap("   1")
    ap("   " + "   ".join(str(i) for i in range(1, n_cat + 1)))    # pair cation indices
    ap("   " + "   ".join("1" for _ in range(n_cat)))              # pair anion indices
    for i, name in enumerate(order, start=1):
        z_cat = OXIDES[name]["charge"] * Z_PER_CHARGE
        z_o = 2 * Z_PER_CHARGE
        ap(f"   {i}   {i}   {an_idx}   {an_idx}   "
           f"{z_cat:.7f}   {z_cat:.7f}   {z_o:.7f}   {z_o:.7f}")
    if z_mgsi is not None:
        mg, si = cations.index("Mg") + 1, cations.index("Si") + 1
        ap(f"   {mg}   {si}   {an_idx}   {an_idx}   " + "   ".join(f"{z:.7f}" for z in z_mgsi))
    L.extend(_mqmx_block(excess))
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    out = HERE / "CaO-FeO-MgO-SiO2-liquid.dat"
    out.write_text(build(), encoding="ascii")
    print(f"wrote {out}")
