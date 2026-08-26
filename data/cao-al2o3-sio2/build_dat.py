"""CaO-Al2O3-SiO2 v0.1: the ternary assembled from the three fitted binaries.

Liquid: SUBQ (Ca, Al, Si / O) carrying the SHIPPED binary excesses verbatim (CaO-SiO2
v0.3, CaO-Al2O3 v0.1, Al2O3-SiO2 v0.1), combined by the writer's Muggianu extension -
no ternary term is fitted. The 45 Kay & Taylor / Zaitsev KEMS activity points in the
assessment workspace are a pure VALIDATION set (validate_kt.py), never inputs.

Solids: the three binary edges' compounds plus the two key ternary compounds,
gehlenite Ca2Al2SiO7 and anorthite CaAl2Si2O8 (Robie & Hemingway 1995; gehlenite's
T^-0.5 Cp term carried exactly via the additional-terms block). Provenance and limits:
PROVENANCE.md.
"""
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

# The three shipped binary excesses, verbatim (p acts on the first-named component).
BINARIES = [
    BinaryExcess("CaO", "SiO2",
                 [ExcessTerm(a=-189763.512, b=15.7059847, p=0, q=0),
                  ExcessTerm(a=57170.779, b=0.0, p=1, q=0)],
                 source="CaO-SiO2 v0.3 (shipped .dat)"),
    BinaryExcess("CaO", "AlO1.5",
                 [ExcessTerm(a=-156581.1, b=2.159, p=0, q=0),
                  ExcessTerm(a=133468.2, b=0.0, p=1, q=0)],
                 source="CaO-Al2O3 v0.1"),
    BinaryExcess("SiO2", "AlO1.5",
                 [ExcessTerm(a=9317.3, b=0.0, p=0, q=0),
                  ExcessTerm(a=33855.3, b=0.0, p=5, q=0)],
                 source="Al2O3-SiO2 v0.1"),
]

# ---- solids, all per formula, elements (Ca, Al, Si, O) -------------------------------
# CaO-SiO2 compounds: Neumann-Kopp on the starter oxides + measured dHf_ox (quartz
# basis, corrected to cristobalite by -2300 J per SiO2) + absolute S298 - identical to
# the shipped data/cao-sio2 phase model.
DHF_QZ_TO_CRIST = -2300.0


def _nk_cs(n_cao, n_sio2, dHf_ox_qz, S298):
    return dict(
        dHf=n_cao * CAO.dHf + n_sio2 * SIO2.dHf + dHf_ox_qz + DHF_QZ_TO_CRIST * n_sio2,
        S298=S298,
        a=n_cao * CAO.a + n_sio2 * SIO2.a,
        b=n_cao * CAO.b + n_sio2 * SIO2.b,
        c=n_cao * CAO.c + n_sio2 * SIO2.c, d=0.0)


_caal_solids = {k: dict(v[2], d=v[2].get("d", 0.0)) for k, v in _caal.SOLIDS.items()}

SOLIDS = {
    # name: (n_Ca, n_Al, n_Si, coeff dict)
    "CaO_solid": (1, 0, 0, dict(dHf=CAO.dHf, S298=CAO.S298, a=CAO.a, b=CAO.b, c=CAO.c, d=0.0)),
    "SiO2_cristobalite": (0, 0, 1, dict(dHf=SIO2.dHf, S298=SIO2.S298,
                                        a=SIO2.a, b=SIO2.b, c=SIO2.c, d=0.0)),
    "Al2O3_corundum": (0, 2, 0, dict(AL2O3_SOLID, d=0.0)),
    # CaO-SiO2 edge (data/cao-sio2 phase model, v0.3)
    "CaSiO3": (1, 0, 1, _nk_cs(1, 1, -81922.72, 85.2)),
    "Ca3Si2O7": (3, 0, 2, _nk_cs(3, 2, -229136.76, 210.6)),
    "Ca2SiO4": (2, 0, 1, _nk_cs(2, 1, -136816.80, 120.5)),
    "Ca3SiO5": (3, 0, 1, _nk_cs(3, 1, -112884.32, 168.6)),
    # CaO-Al2O3 edge (data/cao-al2o3 v0.1)
    "Ca3Al2O6": (3, 2, 0, _caal_solids["Ca3Al2O6"]),
    "Ca12Al14O33": (12, 14, 0, _caal_solids["Ca12Al14O33"]),
    "CaAl2O4": (1, 2, 0, _caal_solids["CaAl2O4"]),
    "CaAl4O7": (1, 4, 0, _caal_solids["CaAl4O7"]),
    # Al2O3-SiO2 edge (data/al2o3-sio2 v0.1)
    "Al6Si2O13": (0, 6, 2, dict(dHf=-6819.2e3, S298=275.0,
                                a=754.6, b=-0.02943, c=-3.454e6, d=-6576.0)),
    # ternary compounds (Robie & Hemingway 1995)
    "Ca2Al2SiO7": (2, 2, 1, dict(dHf=-3985.0e3, S298=210.1,
                                 a=405.7, b=-0.007099, c=-1.188e6, d=-3174.0)),
    "CaAl2Si2O8": (1, 2, 2, dict(dHf=-4234.0e3, S298=199.3,
                                 a=266.4025, b=6.058556e-2, c=-6.55428e6, d=0.0)),
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
    A, B, C, D, E, F, G05 = solid_gibbs_coeffs_sqrt(cf)
    eq_type = 4 if G05 else 1
    n_o = n_ca + 1.5 * n_al + 2.0 * n_si
    elems = (float(n_ca), float(n_al), float(n_si), float(n_o))
    lines = [f" {name}",
             f"   {eq_type}   1   " + "   ".join(f"{e:.6f}" for e in elems),
             "  6000.0000   " + "   ".join(f"{v:.12E}" for v in (A, B, C, D, E, F))]
    if eq_type == 4:
        lines.append(f"   1   {G05:.12E}   5.000000000000E-01")
    return lines


def build(out=None):
    spec = SystemSpec(
        "CaO-AlO1.5-SiO2", [CAO, ALO15, SIO2], BINARIES,
        version="v0.1",
        provenance="assembled from the three shipped binaries (Muggianu, no ternary "
                   "term); KEMS activities are validation only; see PROVENANCE.md")
    lines = dbbuild.write_dat(spec).splitlines()
    lines[1] = f"    4    1    3    {len(SOLIDS)}"
    for name, (n_ca, n_al, n_si, cf) in SOLIDS.items():
        lines += _stoich_block(name, cf, n_ca, n_al, n_si)
    path = out or (HERE / "CaO-Al2O3-SiO2.dat")
    Path(path).write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


if __name__ == "__main__":
    print("wrote", build())
