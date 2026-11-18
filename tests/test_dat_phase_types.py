"""ChemSage phase types beyond SUBQ/SUBG/SUBL: IDMX, RKMP(M), SUBLM, QKTO, SUBI; dummy species; ion compositions."""
import math
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

import mqmqa  # noqa: E402
from mqmqa import gem  # noqa: E402

R = 8.3145            # the ChemSage default these synthetic files take


def _species(name, stoich, a, b, dummy=False):
    """One species record, G = a + b T up to 6000 K."""
    mark = "                       #" if dummy else ""
    st = "    ".join(f"{s:.1f}" for s in stoich)
    return (f" {name}{mark}\n   4  1    {st}\n  6000.0000   {a:.4f}   {b:.4f}   0.0   0.0   0.0\n"
            f" 0.0\n 1 0.0 0.00\n")


def _header(elements, counts, n_stoich):
    return (f" System {'-'.join(elements)}\n"
            f"    {len(elements)}    {len(counts)}    {'    '.join(str(c) for c in counts)}    {n_stoich}\n"
            f" {'                        '.join(elements)}\n"
            f"    {'    '.join('10.0' for _ in elements)}\n"
            "   6   1   2   3   4   5   6\n   6   1   2   3   4   5   6\n")


RK = (_header(["A", "B"], [2], 0) + " LIQ\n RKMP\n"
      + _species("A", [1.0, 0.0], -1000.0, -10.0) + _species("B", [0.0, 1.0], -2000.0, -12.0)
      + "   2\n   1   2   2\n  20000.0  -5.0  0.0  0.0  0.0  0.0\n  3000.0  0.0  0.0  0.0  0.0  0.0\n   0\n")


def test_rkmp_binary_energy_is_redlich_kister():
    """G = x_A G_A + x_B G_B + RT sum x ln x + x_A x_B (L0 + L1 (x_A - x_B)), the terms in the
    order the file lists them, with the sign of the file's A, B."""
    db = mqmqa.Database.read_string(RK)
    T = 1200.0
    for xa in (0.2, 0.5, 0.7):
        xb = 1 - xa
        g = db.cef_gibbs(0, [xa, xb], T)
        ref = (xa * (-1000.0 - 10.0 * T) + xb * (-2000.0 - 12.0 * T)
               + R * T * (xa * math.log(xa) + xb * math.log(xb))
               + xa * xb * ((20000.0 - 5.0 * T) + 3000.0 * (xa - xb)))
        assert g == pytest.approx(ref, abs=1e-6)


def test_rkmp_ternary_is_muggianu():
    """A ternary term with three parameters: x_A x_B x_C (v_A L_A + v_B L_B + v_C L_C),
    v_i = x_i + (1 - x_A - x_B - x_C)/3, here inside a quaternary so the v's differ from x."""
    sp = (_species("A", [1, 0, 0, 0], 0, 0) + _species("B", [0, 1, 0, 0], 0, 0)
          + _species("C", [0, 0, 1, 0], 0, 0) + _species("D", [0, 0, 0, 1], 0, 0))
    text = (_header(["A", "B", "C", "D"], [4], 0) + " LIQ\n RKMP\n" + sp
            + "   3\n   1   2   3   3\n  1000.0  0 0 0 0 0\n  2000.0  0 0 0 0 0\n  4000.0  0 0 0 0 0\n"
            + "   4\n   1   2   3   4   1\n  7000.0  0 0 0 0 0\n   0\n")
    db = mqmqa.Database.read_string(text)
    T = 1000.0
    x = [0.1, 0.2, 0.3, 0.4]
    s = sum(x[:3])
    v = [x[i] + (1 - s) / 3 for i in range(3)]
    ideal = R * T * sum(xi * math.log(xi) for xi in x)
    ref = ideal + x[0] * x[1] * x[2] * (v[0] * 1000.0 + v[1] * 2000.0 + v[2] * 4000.0) \
        + x[0] * x[1] * x[2] * x[3] * 7000.0
    assert db.cef_gibbs(0, x, T) == pytest.approx(ref, abs=1e-6)


GAS = (_header(["A", "B"], [3], 2) + " GAS\n IDMX\n"
       + _species("A", [1.0, 0.0], 0.0, -20.0) + _species("B", [0.0, 1.0], 0.0, -20.0)
       + _species("AB", [1.0, 1.0], -60000.0, -15.0)
       + _species("A_s(s)", [1.0, 0.0], -30000.0, 0.0)
       + _species("A", [1.0, 0.0], -1.0e6, 0.0, dummy=True))


def test_idmx_gas_with_a_molecule_matches_pycalphad():
    """An ideal gas holding A, B and the molecule AB: the molecule's composition is taken
    from its own record, and the dummy A (marked #, absurdly low) never forms. pycalphad applies
    no pressure term to a ChemSage gas, which is the data at their own reference, 1 bar."""
    pycalphad = pytest.importorskip("pycalphad")
    from pycalphad import Database, equilibrium, variables as v
    db = mqmqa.Database.read_string(GAS)
    pdb = Database.from_string(GAS, fmt="dat")
    for T, xa in [(1500.0, 0.5), (900.0, 0.7), (2500.0, 0.3)]:
        r = gem.equilibrium(db, T, {"A": xa, "B": 1 - xa}, P=1.0e5)
        assert all("#" not in p for p in r.phases())
        phases = [p for p in pdb.phases if p not in ("A",)]       # pycalphad keeps the dummy
        eq = equilibrium(pdb, ["A", "B"], phases, {v.T: T, v.P: 101325, v.N: 1, v.X("B"): 1 - xa})
        assert r.phases() == sorted({str(p) for p in eq.Phase.values.ravel() if p})
        assert r.G == pytest.approx(float(eq.GM.squeeze()), abs=1e-3)
        assert r.residual > -1e-3


def test_gas_data_refer_to_one_bar():
    """ChemSage gas data, as FactSage and Thermochimica read them, are at 1 bar: a species'
    energy is its record at 1e5 Pa and gains R T ln 1.01325 at 1 atm (Thermochimica's pure H2
    at 0.986923 atm equals the record; Hephaestus took 1 atm before)."""
    db = mqmqa.Database.read_string(GAS)
    T = 1500.0
    from mqmqa._abi import _lib
    try:
        _lib.mqmqa_db_set_pressure(db._db, 1.0e5)
        g_bar = db.cef_gibbs(0, [1.0, 0.0, 0.0], T)
        _lib.mqmqa_db_set_pressure(db._db, 101325.0)
        g_atm = db.cef_gibbs(0, [1.0, 0.0, 0.0], T)
    finally:
        _lib.mqmqa_db_set_pressure(db._db, 101325.0)
    assert g_bar == pytest.approx(-20.0 * T, abs=1e-9)
    assert g_atm - g_bar == pytest.approx(db.R * T * math.log(1.01325), abs=1e-9)


def _ranged(name, stoich, ranges):
    """A species record with several ranges, G = a + b T in each, up to each T_max."""
    st = "    ".join(f"{s:.1f}" for s in stoich)
    rec = f" {name}\n   4  {len(ranges)}    {st}\n"
    for tmax, a, b in ranges:
        rec += f"  {tmax:.4f}   {a:.4f}   {b:.4f}   0.0   0.0   0.0\n 0.0\n 1 0.0 0.00\n"
    return rec


def test_last_range_is_carried_on_and_flagged():
    """Above the last range a file gives, the energy is the last range carried on, as
    Thermochimica takes it, and the result names the species and where its data end. Zero,
    taken before, put CsTe-2 liquid tellurium at 0 J/mol at 2500 K (data end at 1600 K)."""
    text = (_header(["A", "B"], [2], 0) + " LIQ\n RKMP\n"
            + _ranged("A", [1.0, 0.0], [(1000.0, -1000.0, -10.0), (1500.0, -2000.0, -12.0)])
            + _species("B", [0.0, 1.0], -500.0, -5.0) + "   0\n")
    db = mqmqa.Database.read_string(text)
    for T, a, b in ((800.0, -1000.0, -10.0), (1200.0, -2000.0, -12.0), (2000.0, -2000.0, -12.0)):
        assert db.cef_gibbs(0, [1.0, 0.0], T) == pytest.approx(a + b * T, abs=1e-9)
    assert gem.equilibrium(db, 1200.0, {"A": 0.5, "B": 0.5}).beyond_data == []
    r = gem.equilibrium(db, 2000.0, {"A": 0.5, "B": 0.5})
    assert r.beyond_data == [("A", 1500.0, 2000.0)]
    assert gem.equilibrium(db, 2000.0, {"B": 1.0}).beyond_data == []    # A is not in it


def test_mixing_pair_keeps_the_file_order():
    """An odd-order term is (x_i - x_j)^n with i the constituent the file lists first, here B
    before A. The one-lattice reader always kept the file's order; this holds it to the rule the
    sublattice reader now follows too (next test)."""
    text = (_header(["A", "B"], [2], 0) + " LIQ\n RKMP\n"
            + _species("B", [0.0, 1.0], -2000.0, -12.0) + _species("A", [1.0, 0.0], -1000.0, -10.0)
            + "   2\n   1   2   2\n  20000.0  -5.0  0.0  0.0  0.0  0.0\n  3000.0  0.0  0.0  0.0  0.0  0.0\n   0\n")
    db = mqmqa.Database.read_string(text)
    T = 1200.0
    for xb in (0.2, 0.7):
        xa = 1 - xb
        ref = (xb * (-2000.0 - 12.0 * T) + xa * (-1000.0 - 10.0 * T)
               + R * T * (xa * math.log(xa) + xb * math.log(xb))
               + xb * xa * ((20000.0 - 5.0 * T) + 3000.0 * (xb - xa)))
        assert db.cef_gibbs(0, [xb, xa], T) == pytest.approx(ref, abs=1e-6)


CUFEC = ROOT.parent / "thermochimica-ref" / "data" / "CuFeC-Kang.dat"
if not CUFEC.exists():
    CUFEC = Path.home() / "Code" / "thermochimica-ref" / "data" / "CuFeC-Kang.dat"


@pytest.mark.skipif(not CUFEC.exists(), reason="needs Thermochimica's data folder (CuFeC-Kang.dat)")
def test_sublattice_pair_keeps_the_file_order():
    """CuFeC-Kang fcc lists (Fe,Cu):Va with L1 = -1882.8. With the file's order the fcc at 3% Cu
    and 1400 K is Thermochimica's -72995.866 J; sorting the pair moved it by
    2 x_Fe x_Cu L1 (x_Fe - x_Cu) = 103 J."""
    db = mqmqa.Database.read(str(CUFEC))
    r = gem.equilibrium(db, 1400.0, {"Cu": 0.03, "Fe": 0.97})
    assert r.phases() == ["FCC_A1"]
    assert r.G == pytest.approx(-72995.866, abs=0.05)


def test_dummy_compound_never_forms():
    db = mqmqa.Database.read_string(GAS)
    r = gem.equilibrium(db, 600.0, {"A": 0.9, "B": 0.1})
    assert r.G > -1.0e5                  # the dummy alone would put G near -9e5 J/mol


def test_writers_refuse_idmx_and_rkmp_phases():
    for text in (GAS, RK):
        db = mqmqa.Database.read_string(text)
        for write in (db.write_dat, db.write_xtdb):
            with pytest.raises(Exception, match="ChemSage (IDMX|RKMP) phase"):
                write()


@pytest.mark.parametrize("name", ["Q", "Mg2"])
def test_ion_composition_comes_from_the_pair_records(name):
    """An ion whose name does not give its composition (a dimer such as Al2, a vacancy, or
    any other name) takes it from the pair records, each the neutral unit of its two ions.
    Renaming the FeO-MgO-SiO2 liquid's Mg cation to Q, or to Mg2 (which reads like two Mg),
    leaves its MgO pair saying one Mg, and the equilibrium is the original file's."""
    path = ROOT / "data" / "feo-mgo-sio2" / "FeO-MgO-SiO2-combined.dat"
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    i = next(k for k, line in enumerate(lines) if line.split() == ["Fe+2", "Mg+2", "Si+4"])
    lines[i] = lines[i].replace("Mg+2", f"{name:4s}")
    renamed = mqmqa.Database.read_string("\n".join(lines) + "\n")
    amt = {"FE": 0.3, "MG": 0.2, "SI": 0.5, "O": 1.5}
    for T in (1873.0, 1673.0):
        a = gem.equilibrium(mqmqa.Database.read(str(path)), T, amt)
        b = gem.equilibrium(renamed, T, amt)
        assert b.phases() == a.phases()
        assert b.G == pytest.approx(a.G, abs=1e-6)


def test_gas_pressure_follows_mass_action():
    """At pressure P each gas species gains R T ln(P / 1 bar). For the A + B = AB gas at equal
    A and B, the equilibrium is the minimum over the AB fraction f of the 1 atm energy plus
    R T ln(P / 1 atm) (per mole of atoms, 1 + f atoms per mole of species); lower pressure leaves less
    AB (Le Chatelier). pycalphad applies no pressure to a ChemSage gas, so it cannot check this."""
    from scipy.optimize import minimize_scalar
    db = mqmqa.Database.read_string(GAS)
    T = 1500.0
    fractions = []
    for P_atm in (1.0, 1e-2, 1e-5):
        g1 = lambda f: db.cef_gibbs(0, [(1 - f) / 2, (1 - f) / 2, f], T) \
            + R * T * math.log(P_atm) / (1 + f)
        best = minimize_scalar(g1, bounds=(1e-12, 1 - 1e-12), method="bounded", options={"xatol": 1e-12})
        r = gem.equilibrium(db, T, {"A": 0.5, "B": 0.5}, P=P_atm * 101325.0)
        assert r.phases() == ["GAS"]
        assert r.G == pytest.approx(g1(best.x), abs=1e-3)
        fractions.append(best.x)
    assert fractions[0] > fractions[1] > fractions[2]
    assert gem.equilibrium(db, T, {"A": 0.5, "B": 0.5}).G == pytest.approx(
        gem.equilibrium(db, T, {"A": 0.5, "B": 0.5}, P=101325.0).G, abs=1e-9)


def test_phase_with_constituents_of_an_absent_element_still_forms():
    """With no B in the system the gas of A, B and AB is the pure A gas, not left out: its B
    and AB species are held at zero. At 2000 K the A gas (G = -20 T at 1 bar, plus R T ln 1.01325
    at 1 atm) is below solid A (-30000)."""
    db = mqmqa.Database.read_string(GAS)
    r = gem.equilibrium(db, 2000.0, {"A": 1.0})
    assert r.phases() == ["GAS"]
    assert r.G == pytest.approx(-40000.0 + R * 2000.0 * math.log(1.01325), abs=1e-6)
    r = gem.equilibrium(db, 1000.0, {"A": 1.0})
    assert r.phases() == ["A_S(S)"]
    assert r.G == pytest.approx(-30000.0, abs=1e-6)


def _ihj(T, tc, beta, p):
    """Inden-Hillert-Jarl magnetic Gibbs energy, J/mol, written out here independently."""
    A = 518 / 1125 + 11692 / 15975 * (1 / p - 1)
    t = T / tc
    if t < 1:
        f = 1 - (79 / (140 * p * t) + 474 / 497 * (1 / p - 1) * (t ** 3 / 6 + t ** 9 / 135 + t ** 15 / 600)) / A
    else:
        f = -(t ** -5 / 10 + t ** -15 / 315 + t ** -25 / 1500) / A
    return R * T * math.log(beta + 1) * f


def _mag_species(name, stoich, a, b, tc, beta):
    st = "    ".join(f"{s:.1f}" for s in stoich)
    return (f" {name}\n  16  1    {st}\n  6000.0000   {a:.4f}   {b:.4f}   0.0   0.0   0.0\n"
            f" 0.0\n 1 0.0 0.00\n {tc}   {beta}\n")


def _mag_file(afm_inv, p):
    return (_header(["A", "B"], [2], 0) + f" BCC\n SUBLM\n  {afm_inv}    {p}\n"
            + _mag_species("A", [1.0, 0.0], -1000.0, -10.0, 1000.0, 2.0)
            + _mag_species("B", [0.0, 1.0], -2000.0, -12.0, -300.0, -0.9)
            + "   1\n  1.00000\n   2\n A                        B\n   1   2\n"
            + "   2\n   1   2   1\n  200.0   0.5\n   0\n"
            + "   2\n   1   2   1\n  5000.0  0.0  0.0  0.0  0.0  0.0\n   0\n")


@pytest.mark.parametrize("afm_inv,p", [("1.000000", 0.40), ("0.333333", 0.28)])
@pytest.mark.parametrize("y_a,T", [(1.0, 600.0), (1.0, 1400.0), (0.5, 600.0), (0.2, 900.0)])
def test_sublm_magnetic_energy_is_inden_hillert_jarl(y_a, T, afm_inv, p):
    """G = sum y G + RT sum y ln y + y_A y_B L + G_mag, with Tc and beta mixed linearly plus
    their interaction, and an antiferromagnetic (negative) Tc or beta divided by the factor
    the header stands for: 1.0 for BCC's -1, 0.333333 for FCC's -3. B is antiferromagnetic,
    and at y_A = 0.2 the mixture is too."""
    db = mqmqa.Database.read_string(_mag_file(afm_inv, p))
    afm = -1.0 / float(afm_inv)
    y_b = 1 - y_a
    g = db.cef_gibbs(0, [y_a, y_b], T)
    tc = y_a * 1000.0 + y_b * -300.0 + y_a * y_b * 200.0
    beta = y_a * 2.0 + y_b * -0.9 + y_a * y_b * 0.5
    if tc < 0:
        tc = tc / afm
    if beta < 0:
        beta = beta / afm
    ideal = sum(y * math.log(y) for y in (y_a, y_b) if y > 0)
    ref = (y_a * (-1000.0 - 10.0 * T) + y_b * (-2000.0 - 12.0 * T) + R * T * ideal
           + y_a * y_b * 5000.0 + (_ihj(T, tc, beta, p) if tc > 1e-10 else 0.0))
    assert g == pytest.approx(ref, abs=1e-6)


def _subl_ternary_file():
    """(A,B)1 (C,D,E,F)3: eight endmembers, a ternary C-D-E on the second sublattice with A
    pinned (three parameters, Muggianu's weights), and a binary A-B with C pinned."""
    els = ["A", "B", "C", "D", "E", "F"]
    recs, k = "", 0
    for i, a in enumerate("AB"):
        for j, c in enumerate("CDEF"):
            st = [0.0] * 6
            st[i] = 1.0
            st[2 + j] = 3.0
            recs += _species(a + c, st, -1000.0 * (k + 1), -2.0 * k)
            k += 1
    return (_header(els, [8], 0) + " SOL\n SUBL\n" + recs
            + "   2\n  1.00000    3.00000\n   2   4\n A    B\n C    D    E    F\n"
            + "   1   1   1   1   2   2   2   2\n   1   2   3   4   1   2   3   4\n"
            + "   4\n   1   3   4   5   3\n"
            + "  1000.0  0 0 0 0 0\n  2000.0  0 0 0 0 0\n  4000.0  0 0 0 0 0\n"
            + "   3\n   1   2   3   1\n  -7000.0  0 0 0 0 0\n   0\n")


def test_subl_ternary_on_one_sublattice_is_muggianu():
    db = mqmqa.Database.read_string(_subl_ternary_file())
    T = 900.0
    ya = [0.3, 0.7]
    yc = [0.1, 0.2, 0.3, 0.4]                    # C D E F
    g = db.cef_gibbs(0, ya + yc, T, per_mole_atoms=False)
    em, k = 0.0, 0
    for i in range(2):
        for j in range(4):
            em += ya[i] * yc[j] * (-1000.0 * (k + 1) - 2.0 * k * T)
            k += 1
    ideal = R * T * (sum(y * math.log(y) for y in ya) + 3 * sum(y * math.log(y) for y in yc))
    s = yc[0] + yc[1] + yc[2]
    v = [yc[m] + (1 - s) / 3 for m in range(3)]
    tern = ya[0] * yc[0] * yc[1] * yc[2] * (v[0] * 1000.0 + v[1] * 2000.0 + v[2] * 4000.0)
    binary = ya[0] * ya[1] * yc[0] * -7000.0
    assert g == pytest.approx(em + ideal + tern + binary, abs=1e-6)


def test_subl_reciprocal_term():
    """(A,B)1 (C,D)2 with a reciprocal term L y_A y_B y_C y_D, both sublattices mixing a pair."""
    els = ["A", "B", "C", "D"]
    recs, k = "", 0
    for i, a in enumerate("AB"):
        for j, c in enumerate("CD"):
            st = [0.0] * 4
            st[i] = 1.0
            st[2 + j] = 2.0
            recs += _species(a + c, st, -500.0 * (k + 1), -1.0 * k)
            k += 1
    text = (_header(els, [4], 0) + " SOL\n SUBL\n" + recs
            + "   2\n  1.00000    2.00000\n   2   2\n A    B\n C    D\n"
            + "   1   1   2   2\n   1   2   1   2\n"
            + "   4\n   1   2   3   4   1\n  3000.0  0 0 0 0 0\n   0\n")
    db = mqmqa.Database.read_string(text)
    T = 800.0
    ya, yc = [0.25, 0.75], [0.6, 0.4]
    em, k = 0.0, 0
    for i in range(2):
        for j in range(2):
            em += ya[i] * yc[j] * (-500.0 * (k + 1) - 1.0 * k * T)
            k += 1
    ideal = R * T * (sum(y * math.log(y) for y in ya) + 2 * sum(y * math.log(y) for y in yc))
    ref = em + ideal + ya[0] * ya[1] * yc[0] * yc[1] * 3000.0
    assert db.cef_gibbs(0, ya + yc, T, per_mole_atoms=False) == pytest.approx(ref, abs=1e-6)


# --- SUBI: the two-sublattice ionic liquid of Sundman, Calphad 15 (1991) 109 -------------
# Where the paper shows the model reduces to a substitutional solution (no anions: x_C =
# y_Va y_C, x_B = y_B, eq. 19) or, with one charge per sublattice, to a sublattice phase of
# fixed sites, the same parameters run through the RKMP or SUBL path must give the same
# energy. Those paths are checked against pycalphad above and in the CEF tests.

def _rec(name, stoich, a, b, star=None):
    """A SUBI record; a neutral's may carry FactSage 8's '* v_C' after its name."""
    first, rest = _species(name, stoich, a, b).split("\n", 1)
    return f"{first}     *   {star:.2f}\n{rest}" if star is not None else f"{first}\n{rest}"


def _term(idx, vals):
    return (f"   {len(idx)}\n   {'   '.join(map(str, idx))}   {len(vals)}\n"
            + "".join(f"  {v:.4f}  0 0 0 0 0\n" for v in vals))


def _unit(i, k, n):
    v = [0.0] * n
    v[i] = k
    return v


def _rand_simplex(rng, n):
    v = [rng.random() + 1e-3 for _ in range(n)]
    return [a / sum(v) for a in v]


# cations Fe+2, Cr+3, Ni+2 on (Va, C, N): every term of the vacancy and neutral sums
_EL_A = ["Fe", "Cr", "Ni", "C", "N"]
_G_A = {"Fe": (-1000.0, -10.0), "Cr": (-1500.0, -11.0), "Ni": (-800.0, -9.0), "C": (-3000.0, -5.0),
        "N": (-2000.0, -4.0)}


def _subi_va_neutral(extra="", fec=-30000.0):
    rec = ""
    for k, (nm, q, e) in enumerate([("FE+2", 2.0, 0), ("CR+3", 3.0, 1), ("NI+2", 2.0, 2)]):
        rec += _rec(f"{nm}:VA", _unit(e, 1.0, 5), *_G_A[_EL_A[e]])
        rec += _rec("C", _unit(3, q, 5), q * _G_A["C"][0], q * _G_A["C"][1], star=q if k % 2 == 0 else None)
        rec += _rec("N", _unit(4, q, 5), q * _G_A["N"][0], q * _G_A["N"][1])
    subi = (" LIQ\n SUBI\n" + rec + "   3   3\n FE+2  CR+3  NI+2\n VA  C  N\n   2\n   2.0  3.0  2.0\n"
            "   -1.0  0.0  0.0\n   1 1 1 2 2 2 3 3 3\n   1 2 3 1 2 3 1 2 3\n"
            + _term([1, 2, 4], [20000.0, 3000.0])            # Fe,Cr:Va, rule of pairs
            + _term([1, 4, 5], [fec, 4000.0])                # Fe:Va,C (eq. 26)
            + _term([2, 5, 4], [-25000.0, 5000.0])           # Cr:C,Va, the file's order kept
            + _term([1, 2, 3, 4], [1000.0, 2000.0, 4000.0])  # Fe,Cr,Ni:Va, v weights (eqs. 32, 33)
            + _term([1, 4, 5, 6], [1500.0, -2500.0, 3500.0])  # Fe:Va,C,N (eq. 36)
            + _term([1, 2, 4, 5], [7000.0]) + extra + "   0\n")   # Fe,Cr:Va,C (eq. 29)
    twin = (" TWIN\n RKMP\n" + "".join(_species(e, _unit(i, 1.0, 5), *_G_A[e]) for i, e in enumerate(_EL_A))
            + _term([1, 2], [20000.0, 3000.0]) + _term([1, 4], [fec, 4000.0])
            + _term([4, 2], [-25000.0, 5000.0]) + _term([1, 2, 3], [1000.0, 2000.0, 4000.0])
            + _term([1, 4, 5], [1500.0, -2500.0, 3500.0]) + _term([1, 2, 4], [7000.0]) + "   0\n")
    return _header(_EL_A, [9, 5], 0) + subi + twin


def test_subi_without_anions_is_the_substitutional_solution():
    """Cations on (Va, C, N): G per mole of atoms equals the RKMP solution of Fe, Cr, Ni, C, N
    at x_c = y_Va y_c, x_C = y_C, x_N = y_N, and the formula's element amounts are those
    fractions times Q. This holds only with Sundman's rule of pairs (y_Va with each y_c)."""
    db = mqmqa.Database.read_string(_subi_va_neutral())
    rng = random.Random(1)
    for _ in range(40):
        T = rng.uniform(500, 3000)
        yc, yd = _rand_simplex(rng, 3), _rand_simplex(rng, 3)
        g, n = db.ionic_gibbs(0, yc + yd, T)
        atoms = sum(n.values())
        x = [yd[0] * yc[0], yd[0] * yc[1], yd[0] * yc[2], yd[1], yd[2]]
        assert [n[e.upper()] / atoms for e in _EL_A] == pytest.approx(x, abs=1e-12)
        assert g / atoms == pytest.approx(db.cef_gibbs(1, x, T), abs=1e-8)


def test_subi_neutral_terms_with_one_unit_cation_are_substitutional():
    """(Cs+)(Va, Te, S, Se): the neutral-neutral binary and ternary, and the Va-neutral
    ternary, equal the RKMP solution of Cs, Te, S, Se at x_Cs = y_Va."""
    els = ["Cs", "Te", "S", "Se"]
    G = {"Cs": (-500.0, -8.0), "Te": (-1200.0, -6.0), "S": (-900.0, -7.0), "Se": (-1100.0, -6.5)}
    rec = _rec("CS+:VA", _unit(0, 1.0, 4), *G["Cs"]) + "".join(
        _rec(e, _unit(i + 1, 1.0, 4), *G[e], star=1.0) for i, e in enumerate(els[1:]))
    subi = (" LIQ\n SUBI\n" + rec + "   1   4\n CS+\n VA  TE  S  SE\n   2\n   1.0\n   -1.0  0.0  0.0  0.0\n"
            "   1 1 1 1\n   1 2 3 4\n"
            + _term([1, 3, 4], [-8000.0, 2000.0, 1500.0]) + _term([1, 2, 3, 4], [3000.0, -1000.0, 2500.0])
            + _term([1, 3, 4, 5], [4000.0, 1000.0, -3000.0]) + _term([1, 2, 5], [-12000.0, 6000.0]) + "   0\n")
    twin = (" TWIN\n RKMP\n" + "".join(_species(e, _unit(i, 1.0, 4), *G[e]) for i, e in enumerate(els))
            + _term([2, 3], [-8000.0, 2000.0, 1500.0]) + _term([1, 2, 3], [3000.0, -1000.0, 2500.0])
            + _term([2, 3, 4], [4000.0, 1000.0, -3000.0]) + _term([1, 4], [-12000.0, 6000.0]) + "   0\n")
    db = mqmqa.Database.read_string(_header(els, [4, 4], 0) + subi + twin)
    rng = random.Random(2)
    for _ in range(40):
        T = rng.uniform(500, 3000)
        yd = _rand_simplex(rng, 4)
        g, n = db.ionic_gibbs(0, [1.0] + yd, T)
        assert g / sum(n.values()) == pytest.approx(db.cef_gibbs(1, yd, T), abs=1e-8)


def test_subi_with_one_charge_per_sublattice_is_a_sublattice_phase():
    """All ions of charge 2: P = Q = 2 at every composition, so the liquid is the SUBL phase
    with sites 2:2 and the same records and terms (binaries on each sublattice, ternaries
    with v weights on each, and a reciprocal term)."""
    els = ["Ca", "Mg", "Mn", "O", "S", "Se"]
    cn, an = ["CA+2", "MG+2", "MN+2"], ["O-2", "S-2", "SE-2"]
    rec = ""
    for i in range(3):
        for j in range(3):
            st = [0.0] * 6
            st[i] = st[3 + j] = 2.0
            rec += _rec(f"{cn[i]}:{an[j]}", st, -400000.0 - 50000.0 * i - 30000.0 * j, 80.0 + 3 * i + 2 * j)
    emap = "   1 1 1 2 2 2 3 3 3\n   1 2 3 1 2 3 1 2 3\n"
    ex = (_term([1, 2, 4], [-20000.0, 5000.0]) + _term([1, 4, 5], [15000.0, -4000.0])
          + _term([1, 2, 3, 4], [1000.0, -2000.0, 3000.0]) + _term([1, 4, 5, 6], [2500.0, 500.0, -1500.0])
          + _term([1, 2, 4, 5], [9000.0]) + "   0\n")
    names = " " + "  ".join(cn) + "\n " + "  ".join(an) + "\n"
    subi = " LIQ\n SUBI\n" + rec + "   3   3\n" + names + "   2\n   2.0 2.0 2.0\n   -2.0 -2.0 -2.0\n" + emap + ex
    subl = " TWIN\n SUBL\n" + rec + "   2\n   2.0   2.0\n   3   3\n" + names + emap + ex
    db = mqmqa.Database.read_string(_header(els, [9, 9], 0) + subi + subl)
    rng = random.Random(3)
    for _ in range(40):
        T = rng.uniform(500, 3000)
        y = _rand_simplex(rng, 3) + _rand_simplex(rng, 3)
        g, _ = db.ionic_gibbs(0, y, T)
        assert g == pytest.approx(db.cef_gibbs(1, y, T, per_mole_atoms=False), abs=1e-7)


def test_subi_equilibrium_is_its_substitutional_twin():
    """With strong Fe-C repulsion the (Fe,Cr,Ni)(Va,C,N) liquid splits; the general solver
    finds the same two liquids with the SUBI liquid alone as with its RKMP twin alone, to the
    solver's own precision (its stopping rule is 1e-3 J per mole of atoms)."""
    db = mqmqa.Database.read_string(_subi_va_neutral(fec=45000.0))
    amt = {"Fe": 0.35, "Cr": 0.1, "Ni": 0.1, "C": 0.35, "N": 0.1}
    for T in (700.0, 1500.0):
        a = gem.equilibrium(db, T, amt, suspend=("TWIN",))
        b = gem.equilibrium(db, T, amt, suspend=("LIQ",))
        assert a.residual > -1e-3 and b.residual > -1e-3
        assert len(a.sets) == len(b.sets) == 2
        assert a.G == pytest.approx(b.G, abs=1e-3)
        for sa, sb in zip(sorted(a.sets, key=lambda s: s.x["C"]), sorted(b.sets, key=lambda s: s.x["C"])):
            assert sa.amount == pytest.approx(sb.amount, abs=1e-3)
            for e in _EL_A:
                assert sa.x.get(e.upper(), 0.0) == pytest.approx(sb.x.get(e.upper(), 0.0), abs=1e-3)


def _ionic_tdb(params):
    head = ["ELEMENT /-   ELECTRON_GAS 0 0 0 !", "ELEMENT VA   VACUUM 0 0 0 !", "ELEMENT CA   X 40 0 0 !",
            "ELEMENT FE   X 55 0 0 !", "ELEMENT O   X 16 0 0 !", "ELEMENT S   X 32 0 0 !",
            "SPECIES CA+2 CA1/+2 !", "SPECIES FE+2 FE1/+2 !", "SPECIES O-2 O1/-2 !",
            "TYPE_DEFINITION % SEQ * !", "PHASE IONIC_LIQ:Y % 2 1 1 !",
            "CONSTITUENT IONIC_LIQ:Y :CA+2,FE+2 : O-2,VA,S : !",
            "PARAMETER G(IONIC_LIQ,CA+2:O-2;0) 298.15 -1300000+100*T; 6000 N !",
            "PARAMETER G(IONIC_LIQ,FE+2:O-2;0) 298.15 -600000+90*T; 6000 N !",
            "PARAMETER G(IONIC_LIQ,CA+2:VA;0) 298.15 -1000-10*T; 6000 N !",
            "PARAMETER G(IONIC_LIQ,FE+2:VA;0) 298.15 -800-9*T; 6000 N !",
            "PARAMETER G(IONIC_LIQ,S;0) 298.15 -3000-5*T; 6000 N !"]
    return "\n".join(head + params) + "\n"


def _ionic_dat(terms):
    rec = ""
    for i, (c, g, gv) in enumerate((("CA", (-1300000.0, 100.0), (-1000.0, -10.0)),
                                    ("FE", (-600000.0, 90.0), (-800.0, -9.0)))):
        rec += _rec(f"{c}+2:O-2", [2.0 if k in (i, 2) else 0.0 for k in range(4)], *g)
        rec += _rec(f"{c}+2:VA", _unit(i, 1.0, 4), *gv)
        rec += _rec("S", _unit(3, 2.0, 4), -6000.0, -10.0, star=2.0)
    return (_header(["Ca", "Fe", "O", "S"], [6], 0) + " LIQ\n SUBI\n" + rec
            + "   2   3\n CA+2  FE+2\n O-2  VA  S\n   2\n   2.0  2.0\n   -2.0 -1.0 0.0\n"
            + "   1 1 1 2 2 2\n   1 2 3 1 2 3\n" + "".join(_term(i, v) for i, v in terms) + "   0\n")


_ANION_TERMS = {   # TDB descriptor: (file indices, one coefficient per order)
    "CA+2,FE+2:O-2": ([1, 2, 3], [-20000.0, 6000.0]),
    "CA+2:O-2,VA": ([1, 3, 4], [15000.0, -5000.0]),
    "CA+2:O-2,S": ([1, 3, 5], [-9000.0, 3000.0]),
    "CA+2,FE+2:O-2,VA": ([1, 2, 3, 4], [8000.0, 3000.0, -2000.0]),   # reciprocal, eq. 37
}


@pytest.mark.parametrize("desc", [None] + list(_ANION_TERMS))
def test_subi_terms_with_an_anion_match_pycalphad(desc):
    """No substitutional twin exists once an anion is present (P then moves with the anion
    fractions). Against pycalphad's ionic liquid, used through calculate() as a black box:
    the records, the ideal entropy with its moving P and Q, and each term an anion multiplies,
    one at a time, the reciprocal term with three parameters as eq. 37 orders them."""
    pycalphad = pytest.importorskip("pycalphad")
    import numpy as np
    params, terms = [], []
    if desc:
        idx, cs = _ANION_TERMS[desc]
        params = [f"PARAMETER L(IONIC_LIQ,{desc};{k}) 298.15 {c}; 6000 N !" for k, c in enumerate(cs)]
        terms = [(idx, cs)]
    dbf = pycalphad.Database(_ionic_tdb(params))
    db = mqmqa.Database.read_string(_ionic_dat(terms))
    rng = random.Random(4)
    T = 1500.0
    for _ in range(6):
        yc, yd = _rand_simplex(rng, 2), _rand_simplex(rng, 3)
        g, n = db.ionic_gibbs(0, yc + yd, T)
        pt = np.array([[yc[0], yc[1], yd[0], yd[2], yd[1]]])      # pycalphad: O-2, S, VA
        res = pycalphad.calculate(dbf, ["CA", "FE", "O", "S", "VA"], "IONIC_LIQ", T=T, P=101325, N=1,
                                  points=pt, output="GM")
        assert g / sum(n.values()) == pytest.approx(float(np.squeeze(res.GM.values)), abs=1e-6)


def test_vacancy_neutral_term_follows_sundman_eq15_where_pycalphad_differs():
    """Sundman's eq. 15: in (Fe+2)(Va, C) the parameter L(Fe+2:Va,C) is the substitutional
    L(Fe,C), the excess per mole of atoms x_Fe x_C L with x_Fe = y_Va. Hephaestus gives that.
    pycalphad 0.11.2's ionic liquid gives x_Fe^2 x_C L, one factor y_Va more (as it does in
    the cation-pair term with Va); recorded here so a change on either side shows."""
    pycalphad = pytest.importorskip("pycalphad")
    import numpy as np
    base = ("ELEMENT /- ELECTRON_GAS 0 0 0 !\nELEMENT VA VACUUM 0 0 0 !\nELEMENT FE X 55 0 0 !\n"
            "ELEMENT C X 12 0 0 !\nSPECIES FE+2 FE1/+2 !\nTYPE_DEFINITION % SEQ * !\n"
            "PHASE IONIC_LIQ:Y % 2 1 1 !\nCONSTITUENT IONIC_LIQ:Y :FE+2 : C,VA : !\n"
            "PARAMETER G(IONIC_LIQ,FE+2:VA;0) 298.15 -1000; 6000 N !\n"
            "PARAMETER G(IONIC_LIQ,C;0) 298.15 -2000; 6000 N !\n")
    with_l = pycalphad.Database(base + "PARAMETER L(IONIC_LIQ,FE+2:VA,C;0) 298.15 10000; 6000 N !\n")
    without = pycalphad.Database(base)

    def dat(L):
        recs = _rec("FE+2:VA", [1.0, 0.0], -1000.0, 0.0) + _rec("C", [0.0, 2.0], -4000.0, 0.0, star=2.0)
        ex = _term([1, 2, 3], [L]) if L else ""
        return (_header(["Fe", "C"], [2], 0) + " LIQ\n SUBI\n" + recs + "   1   2\n FE+2\n VA  C\n   2\n   2.0\n"
                "   -1.0  0.0\n   1 1\n   1 2\n" + ex + "   0\n")

    mine_w, mine_wo = mqmqa.Database.read_string(dat(10000.0)), mqmqa.Database.read_string(dat(0.0))
    for yc in (0.1, 0.3, 0.5, 0.8):
        xfe, xc = 1 - yc, yc
        gw, nw = mine_w.ionic_gibbs(0, [1.0, 1 - yc, yc], 1500.0)
        gwo, nwo = mine_wo.ionic_gibbs(0, [1.0, 1 - yc, yc], 1500.0)
        assert gw / sum(nw.values()) - gwo / sum(nwo.values()) == pytest.approx(xfe * xc * 1e4, abs=1e-8)
        pt = np.array([[1.0, yc, 1 - yc]])
        theirs = [float(np.squeeze(pycalphad.calculate(d, ["FE", "C", "VA"], "IONIC_LIQ", T=1500, P=101325, N=1,
                                                       points=pt, output="GM").GM.values))
                  for d in (with_l, without)]
        assert theirs[0] - theirs[1] == pytest.approx(xfe * xfe * xc * 1e4, abs=1e-6)


def test_subi_refuses_what_it_cannot_read_safely():
    """A neutral whose records disagree between cations, a '*' factor that is not the
    cation's charge, and the reciprocal term of two cations with Va and a neutral given three
    parameters (the paper allows both its eq. 34 v weights and its eq. 37 series) are
    refused, each with its reason; so is writing a database that holds a SUBI phase."""
    good = _subi_va_neutral()
    mqmqa.Database.read_string(good)
    # Cr's record of C (3 x G_C) changed so C's energy differs under Cr
    bad_energy = good.replace("   -9000.0000   -15.0000", "   -9300.0000   -15.0000", 1)
    assert bad_energy != good
    with pytest.raises(Exception, match="different energy"):
        mqmqa.Database.read_string(bad_energy)
    with pytest.raises(Exception, match="factor"):
        mqmqa.Database.read_string(good.replace("*   2.00", "*   3.00", 1))
    with pytest.raises(Exception, match="more than one parameter"):
        mqmqa.Database.read_string(_subi_va_neutral(extra=_term([1, 3, 4, 5], [1.0, 2.0, 3.0])))
    db = mqmqa.Database.read_string(good)
    for write in (db.write_tdb, db.write_dat, db.write_xtdb):
        with pytest.raises(Exception, match="SUBI"):
            write()


def test_factsage8_annotations_are_skipped():
    """FactSage 8 files annotate phase and compound names ('= MIXTURE PHASE = 2',
    '= COMPOUND PHASE = 1.0000') and the end of a list ('0 = end of ...'). The annotated
    file reads as the plain one; a compound annotated with another value is refused."""
    plain = (_header(["A", "B"], [2], 1) + " LIQ\n RKMP\n"
             + _species("A", [1.0, 0.0], -1000.0, -10.0) + _species("B", [0.0, 1.0], -2000.0, -12.0)
             + "   2\n   1   2   1\n  20000.0  -5.0  0.0  0.0  0.0  0.0\n   0\n"
             + _species("AB_s", [1.0, 1.0], -9000.0, 1.0))
    noted = (plain.replace(" LIQ\n", " LIQ                = MIXTURE PHASE =  2\n")
             .replace("   0\n", "   0                = end of excess parameters\n")
             .replace(" AB_s\n", " AB_s               = COMPOUND PHASE =       1.0000\n"))
    assert noted.count("=") == 5
    a, b = mqmqa.Database.read_string(plain), mqmqa.Database.read_string(noted)
    assert b.cef_gibbs(0, [0.3, 0.7], 1000.0) == a.cef_gibbs(0, [0.3, 0.7], 1000.0)
    assert b.stoich_gibbs(0, 1000.0) == a.stoich_gibbs(0, 1000.0)
    with pytest.raises(Exception, match="COMPOUND PHASE"):
        mqmqa.Database.read_string(noted.replace("1.0000\n", "2.0000\n"))


# --- QKTO: Kohler polynomial solutions, Pelton, Calphad 12 (1988) 127 ------------------
# A term lists its species and the power of each (eq. 7, g = sum phi_ij Y_A^i Y_B^j); with
# all species in one group the multicomponent form is Kohler's (eq. 12): a binary term at
# s^2 (Y_A/s)^i (Y_B/s)^j with s = Y_A + Y_B, a ternary at s^3 and three such ratios.

def _qk_species(name, stoich, a, b, group=1, q=1.0):
    return _species(name, stoich, a, b) + f"  {q:.5f}      {group}\n"


def _qk_term(idx, powers, a, b=0.0):
    return (f"   {len(idx)}\n   {'   '.join(map(str, idx + powers))}  {a:.4f}  {b:.4f}  0.0  0.0\n"
            "  0.0  0.0\n")


def _qkto(els, species, terms):
    return _header(els, [len(species)], 0) + " SOL\n QKTO\n" + "".join(species) + "".join(terms) + "   0\n"


def test_qkto_binary_terms_follow_kaye_2007():
    """Kaye, Lewis and Thompson, J. Nucl. Mater. 366 (2007) 8, Table 2, give the bcc Mo-Pd
    excess as X_Mo X_Pd [40328.63 + 1220269 X_Pd - (73.49 + 159.92 X_Pd) T]; Thermochimica's
    file of their work holds it as two terms of powers (1, 1) and (1, 2). A (0, 1) term, as in
    Thermochimica's FeTiVO file, adds L X_B (s^2 times Y_B / s)."""
    sp = [_qk_species("MO", [1.0, 0.0], -1000.0, -10.0), _qk_species("PD", [0.0, 1.0], -2000.0, -12.0)]
    db = mqmqa.Database.read_string(_qkto(["Mo", "Pd"], sp, [_qk_term([1, 2], [1, 1], 40328.63, -73.49),
                                                            _qk_term([1, 2], [1, 2], 1220269.0, -159.92)]))
    shifted = mqmqa.Database.read_string(_qkto(["Mo", "Pd"], sp, [_qk_term([1, 2], [0, 1], 5000.0, -2.0)]))
    for T in (1000.0, 1800.0):
        for x in (0.1, 0.3, 0.5, 0.8):
            base = (1 - x) * (-1000.0 - 10.0 * T) + x * (-2000.0 - 12.0 * T) \
                + R * T * ((1 - x) * math.log(1 - x) + x * math.log(x))
            kaye = (1 - x) * x * (40328.63 + 1220269 * x - (73.49 + 159.92 * x) * T)
            assert db.cef_gibbs(0, [1 - x, x], T) == pytest.approx(base + kaye, abs=1e-6)
            assert shifted.cef_gibbs(0, [1 - x, x], T) == pytest.approx(base + x * (5000.0 - 2.0 * T), abs=1e-6)


def _qk_quaternary():
    els = ["A", "B", "C", "D"]
    sp = [_qk_species(e, _unit(i, 1.0, 4), -1000.0 * (i + 1), -5.0 - i) for i, e in enumerate(els)]
    terms = [_qk_term([1, 2], [1, 1], -12000.0, 3.0), _qk_term([1, 2], [1, 2], 8000.0),
             _qk_term([2, 3], [2, 1], 15000.0, -4.0), _qk_term([1, 4], [1, 3], -6000.0),
             _qk_term([1, 2, 3], [2, 1, 1], 20000.0), _qk_term([2, 3, 4], [1, 1, 2], -9000.0, 2.0)]
    return els, _qkto(els, sp, terms)


def test_qkto_multicomponent_terms_are_kohler_eq12():
    """In a quaternary the binary and ternary terms take Kohler's weights of Pelton's eq. 12,
    which differ from plain products of the mole fractions once the powers are unequal."""
    _, text = _qk_quaternary()
    db = mqmqa.Database.read_string(text)
    terms = [((0, 1), (1, 1), -12000.0, 3.0), ((0, 1), (1, 2), 8000.0, 0.0), ((1, 2), (2, 1), 15000.0, -4.0),
             ((0, 3), (1, 3), -6000.0, 0.0), ((0, 1, 2), (2, 1, 1), 20000.0, 0.0), ((1, 2, 3), (1, 1, 2), -9000.0, 2.0)]
    rng = random.Random(6)
    for _ in range(20):
        T = rng.uniform(600, 2000)
        x = _rand_simplex(rng, 4)
        ref = sum(x[i] * (-1000.0 * (i + 1) + (-5.0 - i) * T) for i in range(4)) \
            + R * T * sum(v * math.log(v) for v in x)
        for idx, pw, a, b in terms:
            s = sum(x[i] for i in idx)
            ref += s ** len(idx) * (a + b * T) * math.prod((x[i] / s) ** p for i, p in zip(idx, pw))
        assert db.cef_gibbs(0, x, T) == pytest.approx(ref, abs=1e-6)


def test_qkto_matches_pycalphad():
    """The same quaternary through pycalphad's ChemSage reader, used as a black box."""
    pycalphad = pytest.importorskip("pycalphad")
    import numpy as np
    els, text = _qk_quaternary()
    db = mqmqa.Database.read_string(text)
    dbf = pycalphad.Database.from_string(text, fmt="dat")
    rng = random.Random(8)
    for _ in range(8):
        T = rng.uniform(600, 2000)
        x = _rand_simplex(rng, 4)
        res = pycalphad.calculate(dbf, els + ["VA"], "SOL", T=T, P=101325, N=1, points=np.array([x]), output="GM")
        assert db.cef_gibbs(0, x, T) == pytest.approx(float(np.squeeze(res.GM.values)), abs=1e-6)


def test_qkto_refuses_what_it_cannot_read_safely():
    """Species in two groups (the Toop form) or counting other than one equivalent are refused,
    since no file at hand shows how those are written; writers refuse the phase as well."""
    sp = [_qk_species("A", [1.0, 0.0], 0.0, 0.0), _qk_species("B", [0.0, 1.0], 0.0, 0.0, group=2)]
    with pytest.raises(Exception, match="more than one group"):
        mqmqa.Database.read_string(_qkto(["A", "B"], sp, []))
    sp = [_qk_species("A", [1.0, 0.0], 0.0, 0.0), _qk_species("B", [0.0, 1.0], 0.0, 0.0, q=2.0)]
    with pytest.raises(Exception, match="equivalent"):
        mqmqa.Database.read_string(_qkto(["A", "B"], sp, []))
    db = mqmqa.Database.read_string(_qk_quaternary()[1])
    for write in (db.write_dat, db.write_xtdb):
        with pytest.raises(Exception, match="QKTO"):
            write()


def test_subm_is_refused_with_its_reason():
    """SUBM stays refused (validation/thermochimica/PROTOCOL.md): its excess-term layout is
    documented in no source the engine was written from, and the refusal says so."""
    text = _header(["A", "B"], [2], 0) + " SALT\n SUBM\n" + _species("AB", [1.0, 1.0], 0.0, 0.0)
    with pytest.raises(Exception, match="SUBM, which is not read.*not documented"):
        mqmqa.Database.read_string(text)
