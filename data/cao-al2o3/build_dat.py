"""CaO-Al2O3 v0.1: open literature-only database (liquid SUBQ + 6 stoichiometric solids).

Liquid components CaO and AlO1.5 (per-cation basis, charge-neutral units; AlO1.5 carries half
the Al2O3 thermodynamics). Compound enthalpies from measured formation-from-oxides values on
CODATA/JANAF endmembers; entropies Barin (1995); Cp Maier-Kelley (Bonnickson 1955 drop
calorimetry for CA; workspace fits to Barin points for C3A/C12A7/CA2). Invariant targets are
Rankin & Wright (1915). Full provenance in PROVENANCE.md.
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))

from mqmqa import dbbuild
from mqmqa.dbbuild import BinaryExcess, Component, ExcessTerm, SystemSpec, solid_gibbs_coeffs

CAO = dbbuild.starter_component("CaO")

# Corundum solid (per mole Al2O3): dHf TKV/JANAF/CODATA -1675.692 kJ; S298 CODATA 50.92;
# Cp Kelley J-based Maier-Kelley (Cp298 = 79.09 vs Barin 79.038). Fusion: Barin (1995)
# corundum sheet (= JANAF): Tm 2327 K, dHfus 111.085 kJ/mol.
AL2O3_SOLID = dict(dHf=-1675692.0, S298=50.92, a=115.0182, b=0.01179888, c=-3.50619e6)
ALO15 = Component(
    name="AlO1.5", cation="Al", charge=3.0, n_cation=1.0, n_oxygen=1.5,
    dHf=AL2O3_SOLID["dHf"] / 2, S298=AL2O3_SOLID["S298"] / 2,
    a=AL2O3_SOLID["a"] / 2, b=AL2O3_SOLID["b"] / 2, c=AL2O3_SOLID["c"] / 2,
    Tm=2327.0, dHfus=111085.0 / 2,
    source="dHf TKV/CODATA; S298 CODATA; Cp Kelley (J Maier-Kelley); fusion Barin 1995 "
           "corundum sheet (=JANAF): 2327 K, 111.085 kJ/mol Al2O3; all halved to AlO1.5")

# Stoichiometric solids, per formula. dHf assembled as sum(oxide dHf) + measured dHf_ox:
#   C3A, C12A7, CA: Coughlin 1956 solution calorimetry (-6.65, -79.37, -15.44 kJ/mol)
#   CA2: Geiger 1988 Eqn (2)/Table 2 (-25.6 kJ/mol at 1063 K, oxide-melt solution calorimetry;
#        his Eqn (3) carries it to 298 K as -20.9 with Bonnickson's Cp; Barin implies -39.3)
#   CA6 (hibonite): Geiger 1988 Eqn (5)/Table 2 (-33.0 kJ/mol)
# S298: Barin 1995 (from King 1955 low-temperature calorimetry).
# Heat content: Bonnickson 1955 drop calorimetry, Table II (298-1800 K; C12A7 to 1700 K),
# bonnickson1955_table2.csv, fitted as the calcium silicates are (data/cao-sio2/silicates.py),
# so the extrapolation above the table is short. Until 2026-09-30 C3A, C12A7 and CA2 used
# Maier-Kelley fits to Barin points to 1000 K only.
# Hibonite has no measured heat capacity: the oxide sum (Neumann-Kopp), with the formation
# entropy from the oxides Geiger derives at 1100 K from his calorimetry and the Kumar & Kay 1985
# and Allibert 1981 electrochemistry, +24.3 J/K (Eqn 10).
_D = dict


def _load(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_sil = _load("caal_silicates", HERE.parent / "cao-sio2" / "silicates.py")
CAL = 4.184
CAO_SOLID = _D(dHf=CAO.dHf, S298=CAO.S298, a=CAO.a, b=CAO.b, c=CAO.c)
_OXIDE_DHF = {"Ca3Al2O6": (3, 1, -6650.0), "Ca12Al14O33": (12, 7, -79370.0),
              "CaAl2O4": (1, 1, -15440.0), "CaAl4O7": (1, 2, -25600.0)}
# The temperature each dHf_ox was measured at. Coughlin's HCl solution calorimetry is at 298 K;
# Geiger's oxide-melt calorimetry is at 1063 K, so CaAl4O7 is anchored there. Until 2026-10-02 his
# 1063 K value was used as the 298 K one, which left CaAl4O7 3.7 kJ too stable at 1063 K.
_T_REF = {"CaAl4O7": 1063.0}
_S298 = {"Ca3Al2O6": 205.899, "Ca12Al14O33": 1046.837, "CaAl2O4": 114.223, "CaAl4O7": 177.820}


def _bonnickson(dhf_ox_298):
    """{formula: [(T, G from the elements, S), ...]} on the measured anchors."""
    import csv
    out = {}
    with open(HERE / "bonnickson1955_table2.csv", newline="") as fh:
        rows = list(csv.DictReader(line for line in fh if not line.startswith("#")))
    for f, (n_cao, n_al2o3, _) in _OXIDE_DHF.items():
        dhf_ox = dhf_ox_298[f]
        dhf = n_cao * CAO.dHf + n_al2o3 * AL2O3_SOLID["dHf"] + dhf_ox
        pts = [(298.15, dhf - 298.15 * _S298[f], _S298[f])]
        for r in rows:
            if r["formula"] == f:
                T, S = float(r["T_K"]), _S298[f] + CAL * float(r["ST_minus_S298_cal"])
                pts.append((T, dhf + CAL * float(r["HT_minus_H298_cal"]) - T * S, S))
        out[f] = pts
    return out


def _h(g, T, step=0.5):
    """Enthalpy from a Gibbs function, H = G - T dG/dT."""
    return g(T) - T * (g(T + step) - g(T - step)) / (2 * step)


def _g_solid(cf, T):
    A, B, C, D, E, F = solid_gibbs_coeffs(cf["dHf"], cf["S298"], cf["a"], cf["b"], cf["c"])
    return A + B * T + C * T * math.log(T) + D * T * T + E * T ** 3 + F / T


def dh_ox(formula, cf, T):
    """Enthalpy of formation from the oxides of a fitted compound at T, J per formula."""
    n_cao, n_al2o3, _ = _OXIDE_DHF[formula]
    return (_h(lambda t: _sil.gibbs_cf(cf, t), T) - n_cao * _h(lambda t: _g_solid(CAO_SOLID, t), T)
            - n_al2o3 * _h(lambda t: _g_solid(AL2O3_SOLID, t), T))


def _anchored():
    """dHf_ox at 298 K for each compound such that the fitted functions reproduce the measured value
    at its own temperature. The fit is linear in a constant offset, so one correction is exact."""
    at298 = {f: v[2] for f, v in _OXIDE_DHF.items()}
    for f, T in _T_REF.items():
        at298[f] += _OXIDE_DHF[f][2] - dh_ox(f, _sil.fit(_bonnickson(at298)[f]), T)
    return at298


TABLES = _bonnickson(_anchored())
# CaAl4O7's enthalpy of formation from the oxides is the least certain of the four: one oxide-melt
# measurement (Geiger 1988, 89 % pure sample), Barin implies -39.3. A constant shift, assessed
# with the liquid (assessment/assess.py) under a prior of Geiger's stated uncertainty (+-4.7 kJ).
CA2_DHF_SHIFT = 0.0
HIBONITE_DHF_OX = -33000.0      # J per CaAl12O19
HIBONITE_DS_OX = 24.3           # J/K per CaAl12O19
HIBONITE = _D(dHf=CAO.dHf + 6 * AL2O3_SOLID["dHf"] + HIBONITE_DHF_OX,
              S298=CAO.S298 + 6 * AL2O3_SOLID["S298"] + HIBONITE_DS_OX,
              **{k: CAO_SOLID[k] + 6 * AL2O3_SOLID[k] for k in ("a", "b", "c")})

# DRY SLAGS ONLY. Ca12Al14O33 (C12A7, mayenite) is left out: it is stable only with absorbed water
# (under 1 mass%) and does not form in a dry atmosphere (Nurse, Welch & Majumdar 1965; Jerebtsov &
# Mikhailov 2001, DTA in argon). Water in a molten slag is unlikely, so the dry diagram is the one
# these files describe; its Bonnickson heat contents stay in bonnickson1955_table2.csv.
SOLIDS = {
    # name: (n_CaO_units, n_AlO15_units, coeff dict per formula)
    "CaO_solid": (1, 0, CAO_SOLID),
    "Al2O3_corundum": (0, 2, AL2O3_SOLID),
    "Ca3Al2O6": (3, 2, _sil.fit(TABLES["Ca3Al2O6"])),
    "CaAl2O4": (1, 2, _sil.fit(TABLES["CaAl2O4"])),
    "CaAl4O7": (1, 4, dict(_sil.fit(TABLES["CaAl4O7"]),
                           dHf=_sil.fit(TABLES["CaAl4O7"])["dHf"] + CA2_DHF_SHIFT)),
    "CaAl12O19": (1, 12, HIBONITE),
}


def solid_x_and_units(name):
    """(x_AlO15, cation units per formula) for a solid's position on the join."""
    n_ca, n_al, _ = SOLIDS[name]
    return n_al / (n_ca + n_al), n_ca + n_al


def _stoich_block(name, coeffs, n_ca, n_al):
    """ChemSage stoichiometric block, Gibbs eq. type 1 (elements Ca, Al, O order)."""
    A, B, C, D, E, F = solid_gibbs_coeffs(coeffs["dHf"], coeffs["S298"],
                                          coeffs["a"], coeffs["b"], coeffs["c"])
    elems = (float(n_ca), float(n_al), float(n_ca + 1.5 * n_al))
    return [f" {name}",
            "   1   1   " + "   ".join(f"{e:.6f}" for e in elems),
            "  6000.0000   " + "   ".join(f"{v:.12E}" for v in (A, B, C, D, E, F))]


def build(terms=(), out=None):
    """Write the .dat with the given liquid ExcessTerms; returns the path."""
    spec = SystemSpec(
        "CaO-AlO1.5", [CAO, ALO15],
        [BinaryExcess("CaO", "AlO1.5", list(terms))] if terms else [],
        version="v0.1",
        provenance="Rankin&Wright 1915 invariants + Coughlin 1956/Geiger 1988 calorimetry "
                   "+ Barin 1995/CODATA endmembers; see PROVENANCE.md")
    lines = dbbuild.write_dat(spec).splitlines()
    lines[1] = f"    3    1    2    {len(SOLIDS)}"      # 3 elements, 1 solution (2 cations), solids
    for name, (n_ca, n_al, coeffs) in SOLIDS.items():
        lines += _stoich_block(name, coeffs, n_ca, n_al)
    path = out or (HERE / "CaO-Al2O3.dat")
    Path(path).write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


if __name__ == "__main__":
    print("wrote", build())
