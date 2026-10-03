"""CaO-Al2O3-SiO2 v0.1: the ternary assembled from the three fitted binaries.

Liquid: SUBQ (Ca, Al, Si / O) carrying the SHIPPED binary excesses verbatim (CaO-SiO2
v0.3, CaO-Al2O3 v0.1, Al2O3-SiO2 v0.1), combined by the writer's Muggianu extension -
no ternary term is fitted. The 45 Kay & Taylor / Zaitsev KEMS activity points in the
assessment workspace are a pure VALIDATION set (validate_kt.py), never inputs.

Solids: the three binary edges' compounds plus the two key ternary compounds,
gehlenite Ca2Al2SiO7 and anorthite CaAl2Si2O8 (Robie & Hemingway 1995; gehlenite's
T^-0.5 Cp term carried exactly via the additional-terms block, anorthite fitted to the R&H
high-temperature table). Provenance and limits:
PROVENANCE.md.
"""
import dataclasses
import importlib.util
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))

from mqmqa import dbbuild
from mqmqa.dbbuild import BinaryExcess, ExcessTerm, SystemSpec


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_caal = _load("caal_build", HERE.parent / "cao-al2o3" / "build_dat.py")
ALO15, AL2O3_SOLID = _caal.ALO15, _caal.AL2O3_SOLID
CAO = dbbuild.starter_component("CaO")
SIO2 = dbbuild.starter_component("SiO2")

_cas_bin = _load("cao_sio2_build", HERE.parent / "cao-sio2" / "build_dat.py")
_alsi = _load("al2o3_sio2_build", HERE.parent / "al2o3-sio2" / "build_dat.py")

# Ternary-level terms (Poschmann Eq. 25-26, r = 1), J: the Ca-Si interaction with Al as the
# additional cation, fitted in v0.2 to the 21 Zaitsev CaO-rich KEMS activities, which showed a
# uniform +3.28 bias in ln a(SiO2) under the pure binary assembly (-110 kJ on the v0.3 binary,
# rescanned to -105 kJ on v0.4; Kay-Taylor held out as validation, see PROVENANCE.md); the Al-Si
# interaction with Ca; the Ca-Al interaction with Si. Zero terms are not written.
TERNARY = {"casi_al": -105000.0, "alsi_ca": 0.0, "caal_si": 0.0}
SI_GROUP = 1          # chemical group of SiO2; CaO and AlO1.5 are group 1


def _t(a, cat):
    return [ExcessTerm(a=a, b=0.0, p=0, q=0, add_cat=cat, r=1)] if a else []


def binaries(t=None):
    """The three shipped binary excesses, verbatim (p acts on the first-named component),
    plus the ternary terms `t` (TERNARY when None)."""
    t = TERNARY if t is None else t
    return [
        BinaryExcess("CaO", "SiO2",
                     [ExcessTerm(a=a, b=b, p=0, q=q) for q, a, b in _cas_bin.ASSESSED_EXCESS]
                     + _t(t["casi_al"], "AlO1.5"),
                     source="CaO-SiO2 v0.4 (data/cao-sio2 build_dat) + CAS ternary term"),
        BinaryExcess("CaO", "AlO1.5",
                     [ExcessTerm(a=-156581.1, b=2.159, p=0, q=0),
                      ExcessTerm(a=133468.2, b=0.0, p=1, q=0)] + _t(t["caal_si"], "SiO2"),
                     source="CaO-Al2O3 v0.1"),
        BinaryExcess("SiO2", "AlO1.5",
                     _alsi.assessed_terms() + _t(t["alsi_ca"], "CaO"),
                     source="Al2O3-SiO2 v0.2 (data/al2o3-sio2 build_dat, Bowen & Greig 1924)"),
    ]


BINARIES = binaries()

# ---- solids, all per formula, elements (Ca, Al, Si, O) -------------------------------
# CaO-SiO2 compounds: the Robie-Hemingway calcium silicates of data/cao-sio2/silicates.py,
# the same functions (Ca2SiO4 in two intervals) the CaO-SiO2 phase model uses.
_sil = _load("ca_silicates", HERE.parent / "cao-sio2" / "silicates.py")


_caal_solids = {k: dict(v[2], d=v[2].get("d", 0.0)) for k, v in _caal.SOLIDS.items()}

# DRY SLAGS ONLY: no Ca12Al14O33, which needs absorbed water to be stable (data/cao-al2o3/build_dat.py).
SOLIDS = {
    # name: (n_Ca, n_Al, n_Si, coeff dict)
    "CaO_solid": (1, 0, 0, dict(dHf=CAO.dHf, S298=CAO.S298, a=CAO.a, b=CAO.b, c=CAO.c, d=0.0)),
    "SiO2_cristobalite": (0, 0, 1, dict(dHf=SIO2.dHf, S298=SIO2.S298,
                                        a=SIO2.a, b=SIO2.b, c=SIO2.c, d=0.0)),
    "Al2O3_corundum": (0, 2, 0, dict(AL2O3_SOLID, d=0.0)),
    # CaO-SiO2 edge (data/cao-sio2 phase model, v0.3)
    "CaSiO3": (1, 0, 1, _sil.intervals("CaSiO3")),
    "Ca3Si2O7": (3, 0, 2, _sil.intervals("Ca3Si2O7")),
    "Ca2SiO4": (2, 0, 1, _sil.intervals("Ca2SiO4")),
    "Ca3SiO5": (3, 0, 1, _sil.intervals("Ca3SiO5")),
    # CaO-Al2O3 edge (data/cao-al2o3 v0.1)
    "Ca3Al2O6": (3, 2, 0, _caal_solids["Ca3Al2O6"]),
    "CaAl2O4": (1, 2, 0, _caal_solids["CaAl2O4"]),
    "CaAl4O7": (1, 4, 0, _caal_solids["CaAl4O7"]),
    "CaAl12O19": (1, 12, 0, _caal_solids["CaAl12O19"]),
    # Al2O3-SiO2 edge (data/al2o3-sio2 v0.1)
    "Al6Si2O13": (0, 6, 2, dict(dHf=-6819.2e3, S298=275.0,
                                a=754.6, b=-0.02943, c=-3.454e6, d=-6576.0)),
    # ternary compounds (Robie & Hemingway 1995)
    "Ca2Al2SiO7": (2, 2, 1, dict(dHf=-3985.0e3, S298=210.1,
                                 a=405.7, b=-0.007099, c=-1.188e6, d=-3174.0)),
    # anorthite on the R&H high-T table to 1800 K (rh1995_anorthite.csv), the fit the calcium
    # silicates use; its Cp was a Maier-Kelley fit to 1000 K until 2026-09-30
    "CaAl2Si2O8": (1, 2, 2, _sil.fit(_sil.read_table(HERE / "rh1995_anorthite.csv")["CaAl2Si2O8"])),
}

T0 = 298.15


def solid_gibbs_coeffs_sqrt(cf):
    A, B, C, D, E, F = dbbuild.solid_gibbs_coeffs(cf["dHf"], cf["S298"],
                                                  cf["a"], cf["b"], cf["c"])
    d = cf.get("d", 0.0)
    A += -2.0 * d * math.sqrt(T0)
    B += -2.0 * d / math.sqrt(T0)
    return [A, B, C, D, E, F, 4.0 * d]


def _stoich_block(name, cf, n_ca, n_al, n_si):
    """cf is one coefficient dict (valid to 6000 K) or a list of (T_upper, dict)."""
    ivs = cf if isinstance(cf, list) else [(6000.0, cf)]
    coeffs = [(t, solid_gibbs_coeffs_sqrt(c)) for t, c in ivs]
    eq_type = 4 if any(c[6] for _, c in coeffs) else 1
    n_o = n_ca + 1.5 * n_al + 2.0 * n_si
    elems = (float(n_ca), float(n_al), float(n_si), float(n_o))
    lines = [f" {name}",
             f"   {eq_type}   {len(ivs)}   " + "   ".join(f"{e:.6f}" for e in elems)]
    for t, c in coeffs:
        lines.append(f"  {t:.4f}   " + "   ".join(f"{v:.12E}" for v in c[:6]))
        if eq_type == 4:
            lines.append(f"   1   {c[6]:.12E}   5.000000000000E-01")
    return lines


def build(out=None, ternary=None, si_group=None):
    si = dataclasses.replace(SIO2, group=SI_GROUP if si_group is None else si_group)
    spec = SystemSpec(
        "CaO-AlO1.5-SiO2", [CAO, ALO15, si], binaries(ternary),
        version="v0.2",
        provenance="three shipped binaries (Muggianu) + one ternary term fitted to "
                   "the Zaitsev KEMS activities; see PROVENANCE.md")
    lines = dbbuild.write_dat(spec).splitlines()
    lines[1] = f"    4    1    3    {len(SOLIDS)}"
    for name, (n_ca, n_al, n_si, cf) in SOLIDS.items():
        lines += _stoich_block(name, cf, n_ca, n_al, n_si)
    path = out or (HERE / "CaO-Al2O3-SiO2.dat")
    Path(path).write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


if __name__ == "__main__":
    print("wrote", build())
