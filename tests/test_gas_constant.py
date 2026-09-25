"""The engine-wide gas-constant setting.

In the default "as_assessed" mode every part of the engine keeps the value its data
was built with: 8.3145 in the condensed engine (ChemSage and TDB databases), 8.31451 in
the XTDB engine and for the built-in TDB function R, 8.314462618 in the gas modules.
The existing suite passing unchanged is the proof that this default is bit-identical;
here each forced mode is checked to reach every module, and switching back to restore
the default results exactly. The setting never reaches database building or a written
file.
"""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))
import roundtrip_util as U  # noqa: E402
import mqmqa  # noqa: E402
from mqmqa import Database, XTDB, dbbuild  # noqa: E402
from mqmqa import equilibrium as eq  # noqa: E402
from mqmqa import gas_flux  # noqa: E402
from mqmqa._abi import _ffi, _lib, c_equilibrate  # noqa: E402

VALUES = {"calphad": 8.3145, "sgte": 8.31451, "si": 8.314462618}
FORCED = list(VALUES)
WEB = os.path.join(U.ROOT, "web")


@pytest.fixture(autouse=True)
def _restore_mode():
    yield
    mqmqa.set_gas_constant("as_assessed")


def test_modes_and_values():
    assert mqmqa.gas_constant_mode() == "as_assessed"
    for name, v in VALUES.items():
        assert mqmqa.gas_constant_choice(name) == v
        assert mqmqa.gas_constant(1.2345) == 1.2345          # as assessed: the data's own
        mqmqa.set_gas_constant(name)
        assert mqmqa.gas_constant_mode() == name
        assert mqmqa.gas_constant(1.2345) == v                # forced: everywhere
        assert mqmqa.R() == v
        mqmqa.set_gas_constant("as_assessed")
    assert mqmqa.R() == 8.3145
    with pytest.raises(ValueError):
        mqmqa.set_gas_constant("codata")
    assert _lib.mqmqa_set_gas_constant(7) == -1 and mqmqa.gas_constant_mode() == "as_assessed"


def _liquid(path):
    db = Database.read(os.path.join(WEB, path))
    p = next(i for i in range(len(db.phase_names)) if db.phase_kind(i) == 0)
    return db, p


def _ideal(inp, X):
    return mqmqa.ideal_mixing_energy(inp["T"], inp["ncat"], inp["nan"], inp["qca"], inp["qcb"],
                                     inp["qax"], inp["qay"], X, inp["Za"], inp["Zb"], inp["Zx"],
                                     inp["Zy"], inp["zeta"], inp["soln_type"], inp["R_own"])


@pytest.mark.parametrize("mode", FORCED)
def test_mqmqa_ideal_mixing_scales_with_R(mode):
    db, p = _liquid("FeO-MgO-SiO2-combined.dat")
    inp = eq.build_inputs(db, p, 1873.0)
    X = list(np.random.default_rng(1).dirichlet(np.ones(len(inp["quads"]))))
    base = _ideal(inp, X)
    mqmqa.set_gas_constant(mode)
    assert db.gas_constant == VALUES[mode]
    forced = _ideal(inp, X)
    assert abs(forced / VALUES[mode] - base / 8.3145) <= 4e-16 * abs(base / 8.3145)


@pytest.mark.parametrize("mode", FORCED)
def test_mqmqa_equilibrium_uses_the_forced_R(mode):
    """G at a fixed quadruplet distribution moves by exactly the ideal term's change,
    and the C solver's minimum follows."""
    db, p = _liquid("LiCl-KCl.dat")
    inp = eq.build_inputs(db, p, 1000.0)
    X = [0.3, 0.3, 0.4]
    g0, i0 = eq.gibbs_per_quad(inp, X), _ideal(inp, X)
    comp = {"LI": 0.5, "K": 0.5, "CL": 1.0}
    gm0 = c_equilibrate(inp, comp)["GM"]
    mqmqa.set_gas_constant(mode)
    g1, i1 = eq.gibbs_per_quad(inp, X), _ideal(inp, X)
    assert abs((g1 - g0) - (i1 - i0)) < 1e-9
    assert abs(i1 * 8.3145 - i0 * VALUES[mode]) < 1e-9
    gm1 = c_equilibrate(inp, comp)["GM"]
    if mode != "calphad":
        assert gm1 != gm0


@pytest.mark.parametrize("mode", FORCED)
def test_cef_and_magnetic_terms_use_the_forced_R(mode):
    """FeC.tdb's BCC carries the Inden magnetic term, R T ln(1+beta) f(tau), and the CEF
    ideal term; both are linear in R, so G(R) is exactly a line through the default."""
    db = Database.read(os.path.join(WEB, "FeC.tdb"))
    p = db.phase_names.index("BCC_A2")
    subls = db.cef_sublattices(p)
    Y = U._random_Y(subls, np.random.default_rng(2))
    T = 900.37
    g = {}
    for m in ("calphad", "sgte", "si"):
        mqmqa.set_gas_constant(m)
        g[m] = db.cef_gibbs(p, Y, T)
    mqmqa.set_gas_constant("as_assessed")
    assert db.cef_gibbs(p, Y, T) == g["calphad"]              # the TDB's own 8.3145
    slope = (g["si"] - g["calphad"]) / (8.314462618 - 8.3145)
    assert abs(g["sgte"] - (g["calphad"] + slope * (8.31451 - 8.3145))) < 1e-9 * abs(g["sgte"])
    assert slope < 0                                           # the entropy terms are negative


XTDB_TEXT = """<XTDB version="0.1.5">
<Defaults LowT="298.15" HighT="6000" Elements="VA /-" />
<Element Id="A" Refstate="X" Mass="10" H298="0" S298="0" />
<Element Id="B" Refstate="X" Mass="20" H298="0" S298="0" />
<Species Id="A" Stoichiometry="A" />
<Species Id="B" Stoichiometry="B" />
<TPfun Id="R" Expr="8.31451;" />
<Phase Id="EIN" Configuration="CEF" State="S">
  <Sublattices NumberOf="1" Multiplicities="1">
    <Constituents Sublattice="1" List="A B" />
  </Sublattices>
</Phase>
<Parameter Id="G(EIN,A;0)" Expr="-1000+R*T;" />
<Parameter Id="LNTH(EIN,A;0)" Expr="LN(300);" />
<Parameter Id="G(EIN,B;0)" Expr="-2000;" />
<Parameter Id="LNTH(EIN,B;0)" Expr="LN(200);" />
</XTDB>
"""


def _xtdb_expected(R, xB, T):
    def ein(th):
        return 1.5 * R * th + 3.0 * R * T * math.log(1.0 - math.exp(-th / T))
    ga = -1000 + R * T + ein(300.0)
    gb = -2000 + ein(200.0)
    return (1 - xB) * ga + xB * gb + R * T * ((1 - xB) * math.log(1 - xB) + xB * math.log(xB))


@pytest.mark.parametrize("mode", ["as_assessed"] + FORCED)
def test_xtdb_engine_uses_the_forced_R(mode):
    """Einstein term, ideal mixing, and the file's own TPfun R all follow the mode."""
    x = XTDB.read_string(XTDB_TEXT)
    mqmqa.set_gas_constant(mode)
    R = VALUES.get(mode, 8.31451)
    for T in (400.0, 1500.0):
        g, _ = x.phase_gibbs(0, "B", 0.3, T)
        want = _xtdb_expected(R, 0.3, T)
        assert abs(g - want) <= 1e-12 * abs(want), (mode, T, g, want)


def test_xtdb_forced_sgte_is_its_own_value():
    x = XTDB.read(os.path.join(WEB, "AlC.xtdb"))
    ref = [x.phase_gibbs(p, "C", 0.3, T)[0] for p in range(len(x.phase_names)) for T in (500., 2500.)]
    mqmqa.set_gas_constant("sgte")
    same = [x.phase_gibbs(p, "C", 0.3, T)[0] for p in range(len(x.phase_names)) for T in (500., 2500.)]
    mqmqa.set_gas_constant("calphad")
    moved = [x.phase_gibbs(p, "C", 0.3, T)[0] for p in range(len(x.phase_names)) for T in (500., 2500.)]
    np.testing.assert_array_equal(np.array(ref), np.array(same))
    assert any(a != b for a, b in zip(ref, moved) if not (math.isnan(a) and math.isnan(b)))


RTDB = """ ELEMENT A   X  10  0  0 !
 {func}
 PHASE P %  1  1.0 !
 CONSTITUENT P : A : !
 PARAMETER G(P,A;0)  298.15  -1000+R#*T;  6000 N !
"""


@pytest.mark.parametrize("own,func", [(8.31451, ""), (8.3, " FUNCTION R  298.15  8.3;  6000 N !")])
def test_tdb_function_R_follows_the_mode(own, func):
    """R# is the built-in 8.31451 unless the file defines FUNCTION R; a forced mode
    replaces either, and the default comes back exactly."""
    db = Database.read_string(RTDB.format(func=func))
    i = db.stoich.index("P")
    T = 1234.5
    assert db.stoich_gibbs(i, T) == -1000 + own * T
    for mode, v in VALUES.items():
        mqmqa.set_gas_constant(mode)
        assert db.stoich_gibbs(i, T) == -1000 + v * T
    mqmqa.set_gas_constant("as_assessed")
    assert db.stoich_gibbs(i, T) == -1000 + own * T


def test_gas_modules_use_the_forced_R():
    """The JANAF vaporisation of MgCl2 in gas_flux is on the SI value: ln p scales as 1/R."""
    T = 1200.0
    lnp = math.log(gas_flux.pure_vapor_pressure("MgCl2", T))
    for mode, v in VALUES.items():
        mqmqa.set_gas_constant(mode)
        forced = math.log(gas_flux.pure_vapor_pressure("MgCl2", T))
        assert abs(forced * v - lnp * 8.314462618) <= 1e-13 * abs(lnp * 8.314462618)


def test_c_gas_engine_reads_the_setting():
    """The C gas engine's only R is in the Peng-Robinson fugacities, where it cancels:
    a forced mode leaves the real-gas equilibrium unchanged to rounding."""
    text = open(os.path.join(WEB, "nasa_gas.dat")).read()
    g = _lib.mqmqa_gas_read_string(text.encode())
    try:
        nel, nsp = _lib.mqmqa_gas_num_elements(g), _lib.mqmqa_gas_num_species(g)
        els = [_ffi.string(_lib.mqmqa_gas_element(g, e)).decode() for e in range(nel)]
        b = _ffi.new("double[]", [{"C": 1.0, "O": 3.0, "H": 2.0}.get(e, 0.0) for e in els])

        def solve():
            x = _ffi.new("double[]", nsp)
            assert _lib.mqmqa_gas_equilibrium_ex(g, 1500.0, 5.0e7, b, 1, x) == 0
            return np.array(list(x))
        x0 = solve()
        for mode in FORCED:
            mqmqa.set_gas_constant(mode)
            assert np.max(np.abs(solve() - x0)) < 1e-12
    finally:
        _lib.mqmqa_gas_free(g)


def test_building_and_writing_never_see_the_mode():
    """dbbuild and every writer produce the same file in every mode, for a database whose
    expressions reference R# too."""
    spec = dbbuild.SystemSpec("CaO-SiO2", [dbbuild.starter_component("CaO"),
                                           dbbuild.starter_component("SiO2")],
                              [dbbuild.BinaryExcess("CaO", "SiO2",
                                                    [dbbuild.ExcessTerm(a=-80000.0)])],
                              version="t", provenance="t")
    rdb = Database.read_string(RTDB.format(func=""))
    salt = Database.read(os.path.join(WEB, "LiCl-KCl.dat"))

    def outputs():
        return (dbbuild.R, dbbuild.write_dat(spec), rdb.write_tdb(), rdb.write_utdb(),
                rdb.write_dat(), rdb.write_xtdb(), salt.write_dat(), salt.write_utdb())
    ref = outputs()
    for mode in FORCED:
        mqmqa.set_gas_constant(mode)
        assert outputs() == ref, mode


def test_switching_back_is_bit_identical():
    db, p = _liquid("AlZn-NaClKClMgCl2.utdb")
    inp = eq.build_inputs(db, p, 1100.0)
    comp = {"NA": 0.3, "K": 0.3, "MG": 0.4, "CL": 1.4}
    tdb = Database.read(os.path.join(WEB, "FeC.tdb"))
    q = tdb.phase_names.index("BCC_A2")
    Y = U._random_Y(tdb.cef_sublattices(q), np.random.default_rng(4))

    def values():
        return (c_equilibrate(inp, comp)["GM"], tdb.cef_gibbs(q, Y, 1000.0),
                [tdb.stoich_gibbs(i, 1500.0) for i in range(len(tdb.stoich))])
    ref = values()
    for mode in FORCED:
        mqmqa.set_gas_constant(mode)
        values()
        mqmqa.set_gas_constant("as_assessed")
        assert values() == ref
