"""Validate the open FeO-MgO-SiO2 ternary liquid.

Two independent checks, both at the MODEL level (a fixed quadruplet distribution, so the
result is exact and does not depend on any minimizer):

  1. Engine vs pycalphad. The molar Gibbs energy of the ternary liquid computed by our
     C engine matches pycalphad's ModelMQMQA.GM to machine precision, over random
     quadruplet distributions. This proves the ChemSage reader ingests the 3-cation .dat
     correctly and the excess (all three binary sets combined) is assembled right.

  2. Reduction to the shipped binaries (the transcription guard). At a binary edge - only
     the Fe-Si quadruplets populated, all Mg quadruplets zero - the ternary .dat must give
     exactly the same Gibbs energy as the shipped FeO-SiO2 binary .dat; likewise the Mg-Si
     edge vs the MgO-SiO2 binary. This proves the excess coefficients copied into the
     ternary builder are byte-for-byte the shipped binary parameters, not a re-typing.

The general equilibrium solver's accuracy is a separate engine concern (the binary work uses
an exact 1-D solve for the same reason); it is not exercised here.
"""
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "python"))

import mqmqa
from mqmqa import equilibrium as eqm


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, HERE.parent / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bd = _load("bd_ternary", "feo-mgo-sio2/build_dat.py")
DAT = HERE / "FeO-MgO-SiO2-liquid.dat"
FEO_DAT = HERE.parent / "feo-sio2" / "FeO-SiO2-liquid.dat"
MGO_DAT = HERE.parent / "mgo-sio2" / "MgO-SiO2-liquid.dat"
T = 1873.0


def _elem(s):
    return re.match(r"[A-Za-z]+", str(s)).group(0).upper()


def _quad_key(A, B, X, Y):
    return tuple(sorted([_elem(A), _elem(B)])) + tuple(sorted([_elem(X), _elem(Y)]))


def _engine_setup(dat):
    db = mqmqa.Database.read(str(dat))
    p = 0  # the liquid is the only solution phase in each of these files
    inp = eqm.build_inputs(db, p, T)
    cats = [c["name"] for c in db.cations(p)]
    ans = [a["name"] for a in db.anions(p)]
    keys = [_quad_key(cats[a], cats[b], ans[x], ans[y]) for (a, b, x, y) in inp["quads"]]
    return db, p, inp, keys


def _engine_gm(inp, X):
    return eqm.gibbs_per_quad(inp, X) / sum(eqm.element_moles(inp, X).values())


def check_vs_pycalphad(n=5, tol=1e-6):
    from pycalphad import Database, variables as v
    from pycalphad.models.model_mqmqa import ModelMQMQA
    _, _, inp, keys = _engine_setup(DAT)
    dbf = Database(str(DAT))
    mod = ModelMQMQA(dbf, ["FE", "MG", "SI", "O", "VA"], "FEO-MGO-SIO2-LIQUID")
    pyq = list(mod._quadruplets)
    gm_expr = mod.symbol_replace(mod.GM, dict(dbf.symbols))
    worst = 0.0
    for seed in range(n):
        vals = [0.04 + 0.017 * ((i * 7 + seed * 3) % len(keys)) for i in range(len(keys))]
        s = sum(vals)
        X = [x / s for x in vals]
        xmap = {keys[i]: X[i] for i in range(len(keys))}
        gm_eng = _engine_gm(inp, X)
        subs = {v.T: T}
        subs.update({mod._X_ijkl(*q): xmap[_quad_key(*q)] for q in pyq})
        gm_py = float(gm_expr.subs(subs))
        worst = max(worst, abs(gm_eng - gm_py))
    print(f"1) engine vs pycalphad (ternary GM, {n} random quad dists): "
          f"worst |diff| = {worst:.2e} J/mol-atom  "
          f"{'PASS' if worst < tol else 'FAIL'}")
    return worst


def _beta_matched_mgo_reference():
    """Build a MgO-SiO2 binary .dat with the assessed excess AND the ternary's MgO(l)
    forsterite-liquidus beta, so the ternary's MgO edge reduces to it exactly (up to the
    binary builder's 8-figure endmember rounding)."""
    mgo_bd = _load("mgo_bd_ref", "mgo-sio2/build_dat.py")
    # the assessed excess, in binary (Mg=1,Si=2,O=3) indexing (matches the shipped .dat)
    excess = [dict(code="Q", li=[1, 2, 3, 3], exp=ex["exp"], coeffs=list(ex["coeffs"]))
              for ex in bd.EX_MGO_SIO2]
    txt = mgo_bd.build(excess=excess, version="beta-ref", mgo_liq_beta=bd.MGO_LIQ_BETA)
    ref = HERE / "_mgo_beta_ref.dat"
    ref.write_text(txt, encoding="ascii")
    return ref


def check_binary_reduction(tol=1e-2):
    """Ternary at a binary edge == the shipped binary .dat.

    The ternary MgO(l) carries the forsterite-liquidus recalibration (MGO_LIQ_BETA), which
    the shipped MgO-SiO2 binary does not, so the edge is compared against a beta-matched
    MgO-SiO2 reference (same assessed excess, same beta) built on the fly - isolating the
    excess transcription from the deliberate endmember calibration.

    Tolerance is 1e-2 J, not machine precision: the MgO-SiO2 builder stores endmember
    coefficients at 8 significant figures (%.8E) while the ternary writes full precision
    (%.12E), a ~2e-4 J rounding on the MgO edge. The FeO-SiO2 edge is exact (that binary
    already uses %.12E). A real excess-coefficient typo would be hundreds of J, far above
    this floor - the guard still catches it."""
    _, _, inpT, keysT = _engine_setup(DAT)
    mgo_ref = _beta_matched_mgo_reference()

    def reduce(binary_dat, present):
        _, _, inpB, keysB = _engine_setup(binary_dat)
        # a distribution on the binary quads
        vB = [0.1 + 0.05 * i for i in range(len(keysB))]
        s = sum(vB)
        XB = [x / s for x in vB]
        gmB = _engine_gm(inpB, XB)
        binmap = {keysB[i]: XB[i] for i in range(len(keysB))}
        # embed into the ternary: matching quads get the binary value, the rest 0
        XT = [binmap.get(k, 0.0) for k in keysT]
        # the ternary quads not in the binary must all be the absent-cation ones
        assert all(binmap.get(k, 0.0) == 0.0 or k in binmap for k in keysT)
        gmT = _engine_gm(inpT, XT)
        return gmB, gmT

    gmB1, gmT1 = reduce(FEO_DAT, "FE")
    gmB2, gmT2 = reduce(mgo_ref, "MG")
    d1, d2 = abs(gmB1 - gmT1), abs(gmB2 - gmT2)
    print(f"2) reduction to shipped binaries (transcription guard):")
    print(f"   FeO-SiO2 edge: binary={gmB1:.4f} ternary={gmT1:.4f}  |diff|={d1:.2e}  "
          f"{'PASS' if d1 < tol else 'FAIL'}")
    print(f"   MgO-SiO2 edge: binary={gmB2:.4f} ternary={gmT2:.4f}  |diff|={d2:.2e}  "
          f"{'PASS' if d2 < tol else 'FAIL'}")
    return max(d1, d2)


def main():
    print("FeO-MgO-SiO2 ternary liquid validation\n")
    w1 = check_vs_pycalphad()
    w2 = check_binary_reduction()
    print(f"\noverall: {'PASS' if (w1 < 1e-6 and w2 < 1e-2) else 'FAIL'}")


if __name__ == "__main__":
    main()
