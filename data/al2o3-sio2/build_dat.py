"""Al2O3-SiO2 v0.1: open literature-only database (liquid + cristobalite, corundum, mullite).

Third slag binary and the opening brick of the CaO-Al2O3-SiO2 ternary. Liquid components
SiO2 and AlO1.5 (reused from the shipped systems). Mullite (3Al2O3.2SiO2) from Robie &
Hemingway (1995), whose Cp carries a T^-0.5 term; its Gibbs block is written exactly via
the ChemSage additional-terms slot (coefficient, exponent 0.5), the same mechanism the
olivine endmembers use. The Al2SiO5 polymorphs (kyanite/andalusite/sillimanite) are
deliberately absent: mullite is the stable binary compound on the melting diagram.
Invariant target and identity revision: see PROVENANCE.md.
"""
import importlib.util
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))

from mqmqa import dbbuild
from mqmqa.dbbuild import BinaryExcess, SystemSpec, solid_gibbs_coeffs

# the cao-al2o3 endmember, reused verbatim (explicit file load; both builders are build_dat)
_spec = importlib.util.spec_from_file_location("caal_build", HERE.parent / "cao-al2o3" / "build_dat.py")
_caal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_caal)
ALO15, AL2O3_SOLID = _caal.ALO15, _caal.AL2O3_SOLID

T0 = 298.15
SIO2 = dbbuild.starter_component("SiO2")

# Stoichiometric solids per formula: (n_SiO2 units, n_AlO15 units, Cp/thermo dict).
# Mullite: R&H 1995 (dHf -6819.2 kJ, S298 275.0; Haas-Fisher Cp with d/sqrt(T) term).
# dHf_ox vs corundum+cristobalite = +24.7 kJ with dS_ox = +35.4 J/K: mullite is
# entropy-stabilized, becoming oxide-stable above ~700 K - physically right.
SOLIDS = {
    "SiO2_cristobalite": (1, 0, dict(dHf=SIO2.dHf, S298=SIO2.S298,
                                     a=SIO2.a, b=SIO2.b, c=SIO2.c, d=0.0)),
    "Al2O3_corundum": (0, 2, dict(AL2O3_SOLID, d=0.0)),
    "Al6Si2O13": (2, 6, dict(dHf=-6819.2e3, S298=275.0,
                             a=754.6, b=-0.02943, c=-3.454e6, d=-6576.0)),
}


def solid_gibbs_coeffs_sqrt(dHf, S298, a, b, c, d=0.0):
    """Seven ChemSage coefficients [A,B,C,D,E,F,G05] for Cp = a + bT + c/T^2 + d/sqrt(T);
    G05 multiplies T^0.5 (the additional-terms slot). Reduces to dbbuild's form at d=0."""
    A, B, C, D, E, F = solid_gibbs_coeffs(dHf, S298, a, b, c)
    A += -2.0 * d * math.sqrt(T0)
    B += -2.0 * d / math.sqrt(T0)
    return [A, B, C, D, E, F, 4.0 * d]


def _stoich_block(name, cf, n_si, n_al):
    """ChemSage stoichiometric block (elements Si, Al, O order); eq type 4 when the
    Gibbs function carries the T^0.5 additional term."""
    A, B, C, D, E, F, G05 = solid_gibbs_coeffs_sqrt(cf["dHf"], cf["S298"],
                                                    cf["a"], cf["b"], cf["c"], cf["d"])
    eq_type = 4 if G05 else 1
    elems = (float(n_si), float(n_al), float(2 * n_si + 1.5 * n_al))
    lines = [f" {name}",
             f"   {eq_type}   1   " + "   ".join(f"{e:.6f}" for e in elems),
             "  6000.0000   " + "   ".join(f"{v:.12E}" for v in (A, B, C, D, E, F))]
    if eq_type == 4:
        lines.append(f"   1   {G05:.12E}   5.000000000000E-01")
    return lines


def solid_x_and_units(name):
    n_si, n_al, _ = SOLIDS[name]
    return n_al / (n_si + n_al), n_si + n_al


def build(terms=(), out=None):
    spec = SystemSpec(
        "SiO2-AlO1.5", [SIO2, ALO15],
        [BinaryExcess("SiO2", "AlO1.5", list(terms))] if terms else [],
        version="v0.1",
        provenance="R&W 1915 silica-side eutectic + R&H 1995 mullite + shipped-system "
                   "endmembers; see PROVENANCE.md")
    lines = dbbuild.write_dat(spec).splitlines()
    lines[1] = "    3    1    2    3"      # 3 elements, 1 solution (2 cations), 3 stoich
    for name, (n_si, n_al, cf) in SOLIDS.items():
        lines += _stoich_block(name, cf, n_si, n_al)
    path = out or (HERE / "Al2O3-SiO2.dat")
    Path(path).write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


if __name__ == "__main__":
    print("wrote", build())
