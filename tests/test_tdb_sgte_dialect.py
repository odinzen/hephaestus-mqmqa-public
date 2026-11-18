"""The Thermo-Calc dialect of the SGTE binary collection (Hallstedt, Calphad 89 (2025) 102833).

Those files abbreviate keywords (PAR, CONST, TEMP-LIM, TYPE-DEF), write an empty temperature limit
as ",," for the TEMP_LIM default, use "*" for any constituent of a sublattice, name constituents a
phase does not have, write the magnetic moment as BM or BMAG, and declare TYPE_DEFINITIONs after
the phases that use them. Each test writes the same model two ways, or checks it against pycalphad.
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

from mqmqa import Database  # noqa: E402

HEAD = """
 ELEMENT VA   VACUUM   0.0 0.0 0.0 !
 ELEMENT FE   BCC_A2   55.847 4489.0 27.2797 !
 ELEMENT NI   FCC_A1   58.69 4787.0 29.796 !
 FUNCTION GHSERFE 298.15 1225.7+124.134*T-23.5143*T*LN(T)-.00439752*T**2-5.8927E-08*T**3
      +77359*T**(-1); 1811 Y -25383.581+299.31255*T-46*T*LN(T)+2.29603E+31*T**(-9); 6000 N !
 FUNCTION GHSERNI 298.15 -5179.159+117.854*T-22.096*T*LN(T)-.0048407*T**2; 1728 Y
      -27840.655+279.135*T-43.1*T*LN(T)+1.12754E+31*T**(-9); 6000 N !
"""

ABBREVIATED = HEAD + """
 TEMP-LIM 298.15 6000 !
 PHASE BCC_A2 %B 2 1 3 !
 CONST BCC_A2 : FE NI : VA : !
 PAR G(BCC_A2,FE:VA),, +GHSERFE;,, N 91Din !
 PAR G(BCC_A2,NI:VA),, +GHSERNI+8715.084-3.556*T;,, N 91Din !
 PAR TC(BCC_A2,FE:VA),, 1043;,, N 91Din !
 PAR BM(BCC_A2,FE:VA),, 2.22;,, N 91Din !
 PAR TC(BCC_A2,NI:VA),, 575;,, N 91Din !
 PAR BMAG(BCC_A2,NI:VA),, 0.85;,, N 91Din !
 PAR L(BCC_A2,FE,NI:VA;0),, -956.63-1.28726*T;,, N 99Ref !
 PAR L(BCC_A2,FE,NI:VA;1),, +1789.03-1.92912*T;,, N 99Ref !
 TYPE-DEF B GES AMEND_PHASE_DESCRIPTION @ MAGNETIC -1 0.4 !
"""

WRITTEN_OUT = HEAD + """
 TYPE_DEFINITION B GES A_P_D BCC_A2 MAGNETIC -1.0 0.4 !
 PHASE BCC_A2 %B 2 1 3 !
 CONSTITUENT BCC_A2 : FE,NI : VA : !
 PARAMETER G(BCC_A2,FE:VA;0) 298.15 +GHSERFE; 6000 N !
 PARAMETER G(BCC_A2,NI:VA;0) 298.15 +GHSERNI+8715.084-3.556*T; 6000 N !
 PARAMETER TC(BCC_A2,FE:VA;0) 298.15 1043; 6000 N !
 PARAMETER BMAGN(BCC_A2,FE:VA;0) 298.15 2.22; 6000 N !
 PARAMETER TC(BCC_A2,NI:VA;0) 298.15 575; 6000 N !
 PARAMETER BMAGN(BCC_A2,NI:VA;0) 298.15 0.85; 6000 N !
 PARAMETER G(BCC_A2,FE,NI:VA;0) 298.15 -956.63-1.28726*T; 6000 N !
 PARAMETER G(BCC_A2,FE,NI:VA;1) 298.15 +1789.03-1.92912*T; 6000 N !
"""


def _g(db, phase, Y, T):
    return db.cef_gibbs(db.phase_index(phase), Y, T)


def _points():
    rng = np.random.default_rng(5)
    for _ in range(12):
        x = float(rng.uniform(0.01, 0.99))
        yield [x, 1.0 - x, 1.0], float(rng.uniform(300.0, 1800.0))


def test_abbreviated_file_reads_as_the_written_out_one():
    a, b = Database.read_string(ABBREVIATED), Database.read_string(WRITTEN_OUT)
    for Y, T in _points():
        assert _g(a, "BCC_A2", Y, T) == _g(b, "BCC_A2", Y, T)


def test_abbreviated_file_matches_pycalphad():
    pyc = pytest.importorskip("pycalphad")
    pdb = pyc.Database(ABBREVIATED)
    db = Database.read_string(ABBREVIATED)
    for Y, T in _points():
        res = pyc.calculate(pdb, ["FE", "NI", "VA"], "BCC_A2", T=T, P=101325, N=1, points=np.array([Y]))
        # pycalphad keeps its own gas constant; the file's R is SGTE's, a few mJ apart
        assert abs(_g(db, "BCC_A2", Y, T) - float(res.GM.values.squeeze())) < 0.05


def test_late_magnetic_type_definition_is_applied():
    plain = ABBREVIATED.replace(" TYPE-DEF B GES AMEND_PHASE_DESCRIPTION @ MAGNETIC -1 0.4 !", "")
    with_mag, without = Database.read_string(ABBREVIATED), Database.read_string(plain)
    assert abs(_g(with_mag, "BCC_A2", [0.9, 0.1, 1.0], 600.0) - _g(without, "BCC_A2", [0.9, 0.1, 1.0], 600.0)) > 1000.0


def test_wildcard_is_the_parameter_written_for_each_constituent():
    base = HEAD + """
 PHASE SIG % 2 1 1 !
 CONST SIG : FE NI : FE NI : !
 PAR G(SIG,FE:FE),, +GHSERFE+2000;,, N !
 PAR G(SIG,NI:NI),, +GHSERNI+2000;,, N !
 PAR G(SIG,FE:NI),, +GHSERFE+GHSERNI-5000;,, N !
 PAR G(SIG,NI:FE),, +GHSERFE+GHSERNI+3000;,, N !
"""
    star = base + " PAR L(SIG,*:FE,NI;0),, -12000+3*T;,, N !\n"
    each = base + (" PAR L(SIG,FE:FE,NI;0),, -12000+3*T;,, N !\n"
                   " PAR L(SIG,NI:FE,NI;0),, -12000+3*T;,, N !\n")
    a, b = Database.read_string(star), Database.read_string(each)
    for Y in ([0.3, 0.7, 0.6, 0.4], [0.8, 0.2, 0.1, 0.9]):
        assert _g(a, "SIG", Y, 900.0) == _g(b, "SIG", Y, 900.0)


def test_parameter_for_a_constituent_the_phase_lacks_is_skipped():
    extra = ABBREVIATED.replace(" PAR L(BCC_A2,FE,NI:VA;0)",
                                " PAR L(BCC_A2,FE,CR:VA;0),, -9999;,, N !\n PAR L(BCC_A2,FE,NI:VA;0)")
    a, b = Database.read_string(extra), Database.read_string(ABBREVIATED)
    assert _g(a, "BCC_A2", [0.4, 0.6, 1.0], 1000.0) == _g(b, "BCC_A2", [0.4, 0.6, 1.0], 1000.0)


@pytest.mark.parametrize("typedef", ["DIS_PART BCC_DIS", "NEVER_DIS DIS_BCC", "DISORDERED_PART BCC_DIS"])
def test_late_order_disorder_type_definition_is_refused(typedef):
    text = ABBREVIATED + f" TYPE-DEF Y GES AMEND_PHASE_DESCRIPTION BCC_A2 {typedef} !\n"
    text = text.replace("PHASE BCC_A2 %B", "PHASE BCC_A2 %BY")
    with pytest.raises(Exception, match="order-disorder"):
        Database.read_string(text)


def test_energy_parameter_types_are_refused_and_volumes_skipped():
    with pytest.raises(Exception, match="changes the Gibbs energy"):
        Database.read_string(ABBREVIATED + " PAR THETA(BCC_A2,FE:VA),, 300;,, N !\n")
    vol = Database.read_string(ABBREVIATED + " PAR V0(BCC_A2,FE:VA),, 7.0E-06;,, N !\n")
    assert _g(vol, "BCC_A2", [0.5, 0.5, 1.0], 800.0) == _g(Database.read_string(ABBREVIATED), "BCC_A2",
                                                         [0.5, 0.5, 1.0], 800.0)


def test_magnetic_fixed_composition_phase_keeps_its_magnetic_term():
    pyc = pytest.importorskip("pycalphad")
    text = HEAD + """
 TEMP-LIM 298.15 6000 !
 PHASE BCC_A2 %B 2 1 3 !
 CONST BCC_A2 : FE : VA : !
 PAR G(BCC_A2,FE:VA),, +GHSERFE;,, N 91Din !
 PAR TC(BCC_A2,FE:VA),, 1043;,, N 91Din !
 PAR BM(BCC_A2,FE:VA),, 2.22;,, N 91Din !
 TYPE-DEF B GES AMEND_PHASE_DESCRIPTION @ MAGNETIC -1 0.4 !
"""
    db = Database.read_string(text)
    assert "BCC_A2" in db.phase_names, "built as a one-endmember solution phase"
    pdb = pyc.Database(text)
    for T in (400.0, 900.0, 1300.0):
        res = pyc.calculate(pdb, ["FE", "VA"], "BCC_A2", T=T, P=101325, N=1, points=np.array([[1.0, 1.0]]))
        assert abs(_g(db, "BCC_A2", [1.0, 1.0], T) - float(res.GM.values.squeeze())) < 0.05


def test_parameter_with_more_sublattices_than_its_phase_is_refused():
    # CeCr-09Cha writes G(DHCP,CE:VA) for a one-sublattice DHCP
    text = HEAD + " PHASE DHCP % 1 1 !\n CONST DHCP : FE : !\n PAR G(DHCP,FE:VA),, +GHSERFE+500;,, N !\n"
    with pytest.raises(Exception, match="does not match sublattice count"):
        Database.read_string(text)


def test_parameter_defined_twice_is_refused():
    # AuNd-15Wan leaves two active G(AU36ND17,AU:ND): pycalphad adds them, Thermo-Calc keeps the last
    twice = ABBREVIATED + " PAR G(BCC_A2,NI:VA),, +GHSERNI+9000;,, N !\n"
    with pytest.raises(Exception, match="defined twice"):
        Database.read_string(twice)
    pair = ABBREVIATED + " PAR L(BCC_A2,NI,FE:VA;0),, -100;,, N !\n"
    with pytest.raises(Exception, match="defined twice"):
        Database.read_string(pair)


def test_wildcard_parameter_adds_to_a_specific_one():
    # AlFe-09Sun writes L(B2_BCC,AL,FE:*:VA;0) and L(B2_BCC,AL,FE:AL:VA;0); both count
    base = HEAD + """
 PHASE SIG % 2 1 1 !
 CONST SIG : FE NI : FE NI : !
 PAR G(SIG,FE:FE),, +GHSERFE+2000;,, N !
 PAR G(SIG,NI:NI),, +GHSERNI+2000;,, N !
 PAR G(SIG,FE:NI),, +GHSERFE+GHSERNI-5000;,, N !
 PAR G(SIG,NI:FE),, +GHSERFE+GHSERNI+3000;,, N !
"""
    both = base + " PAR L(SIG,*:FE,NI;0),, -12000;,, N !\n PAR L(SIG,FE:FE,NI;0),, +4000;,, N !\n"
    summed = base + (" PAR L(SIG,FE:FE,NI;0),, -8000;,, N !\n"
                     " PAR L(SIG,NI:FE,NI;0),, -12000;,, N !\n")
    Y = [0.3, 0.7, 0.6, 0.4]
    assert abs(_g(Database.read_string(both), "SIG", Y, 900.0) - _g(Database.read_string(summed), "SIG", Y, 900.0)) < 1e-9
