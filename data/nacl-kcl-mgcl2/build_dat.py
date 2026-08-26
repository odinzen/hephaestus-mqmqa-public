"""NaCl-KCl-MgCl2 v0.1: the CSP molten-salt ternary, assembled from the three binaries.

Liquid: SUBQ (Na, K, Mg / Cl) carrying the three shipped binary liquid excesses verbatim
(NaCl-KCl, KCl-MgCl2, NaCl-MgCl2), combined by the writer's Muggianu extension. No
ternary term is fitted. Mohan et al. 2018's measured ternary-eutectic melting point is a
pure VALIDATION target (validate_ternary.py), never an input.

Solids: the binary endmembers NaCl, KCl, MgCl2 plus the KCl-MgCl2 double salt KMgCl3.
The (Na,K)Cl halite solid solution (nacl-kcl) is NOT included in v0.1 (the NaCl-KCl edge
is represented by the two stoichiometric solids); it is the v0.2 refinement. Provenance
and limits: PROVENANCE.md.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))

from mqmqa import dbbuild
from mqmqa.dbbuild import BinaryExcess, ExcessTerm, SystemSpec, solid_gibbs_coeffs


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_km = _load("km_build", HERE.parent / "kcl-mgcl2" / "build_dat.py")
_nm = _load("nm_build", HERE.parent / "nacl-mgcl2" / "build_dat.py")

NACL, KCL, MGCL2 = _nm.NACL, _km.KCL, _km.MGCL2   # identical values across the binaries

# The three shipped binary liquid excesses, verbatim (p acts on the first-named cation).
BINARIES = [
    BinaryExcess("NaCl", "KCl",
                 [ExcessTerm(a=-715.1, b=0.0, p=0, q=0)],
                 source="NaCl-KCl v0.1 (Hersh-Kleppa dH_mix)"),
    BinaryExcess("KCl", "MgCl2",
                 [ExcessTerm(a=_km.LIQ_A00, b=0.0, p=0, q=0),
                  ExcessTerm(a=_km.LIQ_A10, b=0.0, p=1, q=0)],
                 source="KCl-MgCl2 v0.1"),
    BinaryExcess("NaCl", "MgCl2",
                 [ExcessTerm(a=_nm.LIQ_A00, b=0.0, p=0, q=0),
                  ExcessTerm(a=_nm.LIQ_A10, b=0.0, p=1, q=0)],
                 source="NaCl-MgCl2 v0.1"),
]

# Solids, per formula, elements (Na, K, Mg, Cl).
SOLIDS = {
    "NaCl_solid": (1, 0, 0, dict(dHf=NACL.dHf, S298=NACL.S298, a=NACL.a, b=NACL.b, c=NACL.c)),
    "KCl_solid": (0, 1, 0, dict(dHf=KCL.dHf, S298=KCL.S298, a=KCL.a, b=KCL.b, c=KCL.c)),
    "MgCl2_solid": (0, 0, 1, dict(dHf=MGCL2.dHf, S298=MGCL2.S298, a=MGCL2.a, b=MGCL2.b, c=MGCL2.c)),
    "KMgCl3": (0, 1, 1, dict(dHf=KCL.dHf + MGCL2.dHf + _km.KMC_DHF_OX, S298=_km.KMC_S298,
                             a=_km.KMC_CP[0], b=_km.KMC_CP[1], c=_km.KMC_CP[2])),
}


# Ternary MQMX term (Poschmann Eq. 25-26, single group, r=1), fitted to the Mohan 2018
# melting point in v0.2: on the KCl-MgCl2 quad with Na as the additional cation. Zero on
# every binary edge (Y_add = 0 there), so the three binaries are untouched.
TERNARY = ("KCl", "MgCl2", "NaCl", -8500.0, 1)


def _stoich_block(name, cf, n_na, n_k, n_mg):
    A, B, C, D, E, F = solid_gibbs_coeffs(cf["dHf"], cf["S298"], cf["a"], cf["b"], cf["c"])
    n_cl = n_na + n_k + 2 * n_mg
    elems = (float(n_na), float(n_k), float(n_mg), float(n_cl))
    return [f" {name}",
            "   1   1   " + "   ".join(f"{e:.6f}" for e in elems),
            "  6000.0000   " + "   ".join(f"{v:.12E}" for v in (A, B, C, D, E, F))]


def _binaries_with(ternary):
    """Copy BINARIES, splicing an optional ternary term (c1, c2, add_cat, a, r)."""
    out = [BinaryExcess(b.first, b.second, list(b.terms), source=b.source)
           for b in BINARIES]
    if ternary is None:
        return out
    c1, c2, add, a, r = ternary
    for b in out:
        if {b.first, b.second} == {c1, c2}:
            b.terms.append(ExcessTerm(a=a, b=0.0, p=0, q=0, add_cat=add, r=r))
            return out
    raise ValueError(f"no binary {c1}-{c2} to carry the ternary term")


def build(out=None, ternary=TERNARY):
    spec = SystemSpec(
        "NaCl-KCl-MgCl2", [NACL, KCL, MGCL2], _binaries_with(ternary),
        version="v0.2",
        provenance="three shipped binaries (Muggianu) + one ternary MQMX term fitted to "
                   "the Mohan 2018 eutectic melting; NaCl/KCl/MgCl2/KMgCl3 solids; see "
                   "PROVENANCE.md")
    lines = dbbuild.write_dat(spec, anion_sym="Cl", anion_charge=1.0,
                              z_per_charge=6.0, family="molten-salt").splitlines()
    lines[1] = f"    4    1    3    {len(SOLIDS)}"      # Na,K,Mg,Cl | 1 soln | 3 cations
    for name, (n_na, n_k, n_mg, cf) in SOLIDS.items():
        lines += _stoich_block(name, cf, n_na, n_k, n_mg)
    path = out or (HERE / "NaCl-KCl-MgCl2.dat")
    Path(path).write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


if __name__ == "__main__":
    print("wrote", build())
