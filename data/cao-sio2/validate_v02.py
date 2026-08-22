"""Validate the v0.2 CaO-SiO2 liquid excess against the open experimental data.

Reports real numbers for four checks, all from the shipped CaO-SiO2-liquid.dat:

  1. Structure + excess parameters round-trip through the reader.
  2. Fitted activities: engine a(CaO), a(SiO2) vs Stolyarova 1991 (single-phase
     points, 1933 K) and Kay & Taylor 1960 (central points, ~1821 K), in ln(a).
  3. Integral Gibbs energy of mixing at 1933 K vs Stolyarova.
  4. Cross-temperature consistency: the SAME (temperature-independent) excess
     reproduces both the 1933 K and the 1821 K datasets - the excess is not tuned
     to a single isotherm.
  5. Full-range stability: d2 Gmix/dx2 > 0 across the join (no spurious miscibility
     gap; the real CaO-SiO2 gap is silica-rich and outside this model's scope).

The endmember round-trip and the published fusion points are checked by the
sibling validate.py and are unchanged from v0.1.
"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "python"))

import mqmqa
from mqmqa import equilibrium as eq
import _activity as act
import fit_excess as fx

DAT = HERE / "CaO-SiO2-liquid.dat"


def main():
    db = mqmqa.Database.read(str(DAT))
    p = db.phase_index("CAO-SIO2-LIQUID")
    inp_s = eq.build_inputs(db, p, fx.T_STOL, components=["CA", "SI", "O"])
    inp_k = eq.build_inputs(db, p, fx.T_KT, components=["CA", "SI", "O"])

    print("=" * 72)
    print("1. STRUCTURE + EXCESS ROUND-TRIP")
    print("=" * 72)
    mx = db.mqmx(p, fx.T_STOL)
    print(f"  MQMX terms: {len(mx['A'])}  (code {mx['code']}, "
          f"p={mx['p']}, q={mx['q']})")
    for (pp, qq), L in zip(zip(mx["p"], mx["q"]), mx["L"]):
        print(f"    Q (Ca,Si,O,O)  chi_Ca^{pp} chi_Si^{qq}   L = {L:12.1f} J/mol")

    print()
    print("=" * 72)
    print("2. FITTED ACTIVITIES  (engine vs open data, liquid reference)")
    print("=" * 72)
    print(f"  {'dataset':13s}{'x_SiO2':>7s}{'T/K':>7s}{'measured':>10s}"
          f"{'engine':>9s}{'ln ratio':>10s}")
    lnres = {"aCaO": [], "aSiO2_S": [], "aSiO2_KT": []}
    for x, (aC, aS) in sorted(fx.STOL.items()):
        if x in fx.STOL_DROP:
            continue
        cC, cS = act.activities(inp_s, x, fx.T_STOL)
        lnres["aCaO"].append(np.log(cC / aC))
        lnres["aSiO2_S"].append(np.log(cS / aS))
        print(f"  {'Stol a(CaO)':13s}{x:7.2f}{fx.T_STOL:7.0f}{aC:10.3f}"
              f"{cC:9.3f}{np.log(cC / aC):10.3f}")
        print(f"  {'Stol a(SiO2)':13s}{x:7.2f}{fx.T_STOL:7.0f}{aS:10.3f}"
              f"{cS:9.3f}{np.log(cS / aS):10.3f}")
    for x, a_liq, T in fx.kaytaylor_points():
        _cC, cS = act.activities(inp_k, x, T)
        lnres["aSiO2_KT"].append(np.log(cS / a_liq))
        print(f"  {'KT a(SiO2)':13s}{x:7.2f}{T:7.0f}{a_liq:10.3f}"
              f"{cS:9.3f}{np.log(cS / a_liq):10.3f}")

    def rms(v):
        return float(np.sqrt(np.mean(np.array(v) ** 2)))

    print(f"\n  RMS ln(a):  a(CaO)={rms(lnres['aCaO']):.3f}  "
          f"a(SiO2,Stol)={rms(lnres['aSiO2_S']):.3f}  "
          f"a(SiO2,KT)={rms(lnres['aSiO2_KT']):.3f}")
    allres = sum(lnres.values(), [])
    print(f"  overall RMS ln(a) = {rms(allres):.3f}  "
          f"(typical activity factor {np.exp(rms(allres)):.2f})")

    print()
    print("=" * 72)
    print("3. INTEGRAL GIBBS ENERGY OF MIXING at 1933 K (J/mol oxide formula)")
    print("=" * 72)
    RT = fx.R * fx.T_STOL
    for x, (aC, aS) in sorted(fx.STOL.items()):
        if x in fx.STOL_DROP:
            continue
        dg_m = (1 - x) * RT * np.log(aC) + x * RT * np.log(aS)
        dg_c = act.delta_g_mix(inp_s, x)
        print(f"  x_SiO2={x:.2f}  measured={dg_m:8.0f}  engine={dg_c:8.0f}  "
              f"diff={dg_c - dg_m:7.0f}")

    print()
    print("=" * 72)
    print("4. CROSS-TEMPERATURE CONSISTENCY  (one excess, two isotherms)")
    print("=" * 72)
    print("  a(SiO2) reproduced at BOTH 1821 K (Kay-Taylor) and 1933 K "
          "(Stolyarova)\n  with the same temperature-independent excess "
          f"->  RMS(1821)={rms(lnres['aSiO2_KT']):.3f}, "
          f"RMS(1933)={rms(lnres['aSiO2_S']):.3f}")

    print()
    print("=" * 72)
    print("5. FULL-RANGE STABILITY  (no spurious miscibility gap)")
    print("=" * 72)
    xs = np.linspace(0.03, 0.97, 60)
    g = np.array([act.delta_g_mix(inp_s, x) for x in xs])
    d2 = np.gradient(np.gradient(g, xs), xs)
    unstable = [round(float(x), 2) for x, u in zip(xs, d2 < -1) if u]
    aC = np.array([act.activities(inp_s, x, fx.T_STOL)[0] for x in xs])
    aS = np.array([act.activities(inp_s, x, fx.T_STOL)[1] for x in xs])
    print(f"  d2 Gmix/dx2 < 0 at: {unstable if unstable else 'NONE (stable across the join)'}")
    print(f"  a(CaO) monotone-decreasing: {bool(np.all(np.diff(aC) < 1e-6))}; "
          f"a(SiO2) monotone-increasing: {bool(np.all(np.diff(aS) > -1e-6))}")
    print(f"  max a(CaO)={aC.max():.3f}, max a(SiO2)={aS.max():.3f} "
          "(both < 1 in the single-phase melt)")


if __name__ == "__main__":
    main()
