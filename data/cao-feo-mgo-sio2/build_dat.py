"""The Ca-Fe-Mg-Si oxide liquid: the CaO-FeO-MgO-SiO2 slag melt (ChemSage SUBQ .dat).

The four-oxide silicate melt of the steel-slag / basalt family, assembled from the shipped
binary liquids by Muggianu, no ternary term:

  - CaO-SiO2  : v0.3 deep liquid, Delta_g(Ca,Si)/O = (-189763.5 + 15.706 T) + 57170.8 chi_Ca
  - FeO-SiO2  : v0.3 activity-pinned symmetric term, plus the FeO(l) below-1650 K interval
  - MgO-SiO2  : the assessed 5-term silica-weighted set, plus the MgO(l) below-melting interval
  - CaO-FeO, CaO-MgO, FeO-MgO : IDEAL. All three are near-ideal mixtures of divalent oxides
    (complete miscibility). Small assessed interactions are a documented v0.2 target.

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

OXIDES = {
    "CaO": dict(src=_cao, ox=_cao.OXIDES["CaO"], charge=2.0, quad=(1.0, 1.0), beta=None),
    "FeO": dict(src=_fms._feo, ox=_fms._feo.OXIDES["FeO"], charge=2.0, quad=(1.0, 1.0),
                beta=(_fms._feo.FEO_TM, _fms.FEO_LIQ_BETA)),
    "MgO": dict(src=_fms._mgo, ox=_fms._mgo.OXIDES["MgO"], charge=2.0, quad=(1.0, 1.0),
                beta=(_fms._mgo.MGO_TM, _fms.MGO_LIQ_BETA)),
    "SiO2": dict(src=_cao, ox=_cao.OXIDES["SiO2"], charge=4.0, quad=(1.0, 2.0), beta=None),
}
STOICH = {"CaO": {"Ca": 1.0, "O": 1.0}, "FeO": {"Fe": 1.0, "O": 1.0},
          "MgO": {"Mg": 1.0, "O": 1.0}, "SiO2": {"Si": 1.0, "O": 2.0}}


def _remap(term, m):
    t = dict(term); t["li"] = [m.get(i, i) for i in term["li"]]; return t


# FeO-SiO2 and MgO-SiO2 excesses from feo-mgo-sio2 (Fe=1,Mg=2,Si=3,O=4), remapped to the
# quaternary indices Fe=2, Mg=3, Si=4, O=5.
_M = {1: 2, 2: 3, 3: 4, 4: 5}
EX_CAO_SIO2 = [
    dict(code="Q", li=[1, 4, 5, 5], exp=[0, 0, 0, 0],
         coeffs=[-189763.512, 15.7059847, 0, 0, 0, 0]),
    dict(code="Q", li=[1, 4, 5, 5], exp=[1, 0, 0, 0],
         coeffs=[57170.779, 0, 0, 0, 0, 0]),
]
EXCESS = (EX_CAO_SIO2
          + [_remap(t, _M) for t in _fms.EX_FEO_SIO2]
          + [_remap(t, _M) for t in _fms.EX_MGO_SIO2])   # CaO-FeO, CaO-MgO, FeO-MgO ideal


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
        out.append("   0   0   " + "   ".join(_fmt(c) for c in ex["coeffs"]))
    out.append("   0")
    return out


def build(excess=EXCESS, version="v0.1"):
    L = []
    ap = L.append
    ap(f" System CaO-FeO-MgO-SiO2  open calcium-iron-magnesium-silicate slag database "
       f"{version} (provenance: data/cao-feo-mgo-sio2/PROVENANCE.md)")
    ap(f"    {len(ELEMENTS)}    1    {len(CATIONS)}    0")
    ap(" " + "                       ".join(e[0] for e in ELEMENTS))
    ap("   " + "              ".join(f"{m:.9f}" for _, m in ELEMENTS))
    ap("    6   1   2   3   4   5   6")
    ap("    6   1   2   3   4   5   6")

    ap(" CaO-FeO-MgO-SiO2-liquid")
    ap(" SUBQ")
    ap(f"   {len(CATIONS)}   {len(CATIONS)}")             # n_pairs, n_quads
    for name in ORDER:
        d = OXIDES[name]
        stoich_el = [STOICH[name].get(el, 0.0) for el, _ in ELEMENTS]
        intervals = _intervals(name)
        ap(f" {name}")
        ap(f"   1   {len(intervals)}   " + "   ".join(f"{s:.1f}" for s in stoich_el))
        for t_max, coeffs in intervals:
            ap(f"  {t_max:.4f}   " + "   ".join(_fmt(v) for v in coeffs))
        ap("  " + "   ".join(f"{v:.5f}" for v in [d["quad"][0], d["quad"][1], 0.0, 0.0, 0.0]))
        ap("  1.3774438")

    n_cat = len(CATIONS)
    an_idx = n_cat + 1
    ap(f"   {n_cat}   1")
    ap(" Ca+2                     Fe+2                     Mg+2                     Si+4")
    ap(" O")
    ap("  2.00000      2.00000      2.00000      4.00000")
    ap("   1   1   1   1")
    ap("  2.00000")
    ap("   1")
    ap("   " + "   ".join(str(i) for i in range(1, n_cat + 1)))    # pair cation indices
    ap("   " + "   ".join("1" for _ in range(n_cat)))              # pair anion indices
    for i, name in enumerate(ORDER, start=1):
        z_cat = OXIDES[name]["charge"] * Z_PER_CHARGE
        z_o = 2 * Z_PER_CHARGE
        ap(f"   {i}   {i}   {an_idx}   {an_idx}   "
           f"{z_cat:.7f}   {z_cat:.7f}   {z_o:.7f}   {z_o:.7f}")
    L.extend(_mqmx_block(excess))
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    out = HERE / "CaO-FeO-MgO-SiO2-liquid.dat"
    out.write_text(build(), encoding="ascii")
    print(f"wrote {out}")
