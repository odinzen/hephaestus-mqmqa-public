"""FeO-MgO-SiO2 phase diagram via the 2-D global minimizer (mqmqa.ternary).

Assembles the candidate phases - the ternary MQMQA liquid, the olivine and orthopyroxene
CEF solid solutions, and the stoichiometric oxide solids (cristobalite SiO2, periclase MgO,
wustite FeO) - and computes the equilibrium assemblage across the cation simplex by lower
convex hull. All Gibbs energies are per mole of cations; composition is the cation fractions
(x_Fe, x_Si), x_Mg = 1 - x_Fe - x_Si.
"""
import importlib.util
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))

import mqmqa
from mqmqa import ternary as tern


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, HERE.parents[0] / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_feo = _load("bd_feo_td", "feo-sio2/build_dat.py")
_mgo = _load("bd_mgo_td", "mgo-sio2/build_dat.py")

LIQ = HERE / "FeO-MgO-SiO2-liquid.dat"
OLV = HERE.parents[0] / "olivine" / "Olivine-CEF.dat"
OPX = HERE.parents[0] / "olivine-opx" / "Olivine-Opx-CEF.dat"

T0 = 298.15


def _solid_oxide_g(ox, T):
    """Solid oxide Gibbs per formula (= per cation for a mono-cation oxide) from the
    Haas-Fisher Cp = a + b*T + c*T^-2 (no fusion term - this is the solid)."""
    a, b, c = ox["a"], ox["b"], ox["c"]
    H = ox["dHf"] + a * (T - T0) + 0.5 * b * (T * T - T0 * T0) - c * (1.0 / T - 1.0 / T0)
    S = (ox["S298"] + a * math.log(T / T0) + b * (T - T0)
         - 0.5 * c * (1.0 / (T * T) - 1.0 / (T0 * T0)))
    return H - T * S


def build(T, nsamp=12000, n_cef=81, refine=True):
    """Pool all candidate phases at T, build the lower hull, refine the liquid hull vertices,
    and re-hull. Returns (points, facets) ready for `assemblage` queries."""
    ldb = mqmqa.Database.read(str(LIQ))
    lp = ldb.phase_index("FEO-MGO-SIO2-LIQUID")
    cdb = mqmqa.Database.read(str(OLV))
    odb = mqmqa.Database.read(str(OPX))

    liq, inp = tern.liquid_points(ldb, lp, T, nsamp=nsamp)
    solids = tern.cef_line_points(cdb, "OLIVINE", T, x_si_line=1.0 / 3.0, n_cations=3, n=n_cef)
    solids += tern.cef_line_points(odb, "ORTHOPYROXENE", T, x_si_line=1.0 / 2.0, n_cations=4, n=n_cef)
    solids.append(tern.stoich_point("CRISTOBALITE", 0.0, 1.0, _solid_oxide_g(_feo.OXIDES["SiO2"], T)))
    solids.append(tern.stoich_point("PERICLASE", 0.0, 0.0, _solid_oxide_g(_mgo.OXIDES["MgO"], T)))
    solids.append(tern.stoich_point("WUSTITE", 1.0, 0.0, _solid_oxide_g(_feo.OXIDES["FeO"], T)))

    pts = liq + solids
    facets = tern.lower_hull(pts)
    if refine:
        pts = tern.refine_liquid(inp, pts, facets, "LIQUID")
        facets = tern.lower_hull(pts)
    return pts, facets


def equilibrium(T, x_fe, x_si, **kw):
    pts, facets = build(T, **kw)
    return tern.assemblage(pts, facets, x_fe, x_si)


if __name__ == "__main__":
    T = 1800.0
    pts, facets = build(T)
    from collections import defaultdict
    for xfe, xsi, label in [(0.20, 1 / 3, "olivine-join X_Fe=0.3"),
                            (0.30, 0.55, "silica-rich (opx)"),
                            (0.10, 0.10, "MgO-rich (3-phase)")]:
        a = tern.assemblage(pts, facets, xfe, xsi)
        print(f"T={T} bulk(x_Fe={xfe:.2f},x_Si={xsi:.2f}): {label}")
        agg = defaultdict(lambda: [0.0, 0.0, 0.0])
        for ph, amt, xf, xs in (a or []):
            agg[ph][0] += amt; agg[ph][1] += amt * xf; agg[ph][2] += amt * xs
        for ph, (amt, sf, ss) in agg.items():
            print(f"   {ph:13s} amt={amt:.3f} x_Fe={sf/amt:.3f} x_Si={ss/amt:.3f}")
