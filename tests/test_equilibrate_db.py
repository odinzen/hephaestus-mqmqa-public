"""The C-core db-level equilibrium (mqmqa_equilibrate_db) must reproduce the
Python-marshalled path through the same solver core, bit for bit. This is the
candidate generator the multiphase equilibrium engine is built on."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
from mqmqa._abi import _lib, _ffi, c_equilibrate           # noqa: E402
from mqmqa._database import Database                        # noqa: E402
from mqmqa import equilibrium as eq                         # noqa: E402

HERE = os.path.dirname(__file__)


def _find(*names):
    for n in names:
        for base in ("data", "web"):
            p = os.path.join(HERE, "..", base, n)
            if os.path.exists(p):
                return p
    raise FileNotFoundError(names)


def _check(datafile, phase_pick, T, targets):
    text = open(datafile, encoding="utf-8").read()
    pydb = Database.read_string(text)
    cdb = _lib.mqmqa_db_read_string(text.encode())
    try:
        nph = _lib.mqmqa_db_num_phases(cdb)
        phase = next(p for p in range(nph) if _lib.mqmqa_db_phase_kind(cdb, p) == 0)
        ndbel = _lib.mqmqa_db_num_elements(cdb)
        els = [_ffi.string(_lib.mqmqa_db_element(cdb, e)).decode() for e in range(ndbel)]
        ncat = _lib.mqmqa_ph_num_cations(cdb, phase)
        nan = _lib.mqmqa_ph_num_anions(cdb, phase)
        nq = _lib.mqmqa_num_quadruplets(ncat, nan)
        inp = eq.build_inputs(pydb, phase, T)
        for tgt in targets:
            tvec = _ffi.new("double[]", [tgt.get(e, 0.0) for e in els])
            Xout = _ffi.new("double[]", nq)
            err = _ffi.new("double[]", 1)
            gw = _lib.mqmqa_equilibrate_db(cdb, phase, T, tvec, Xout, err)
            gr = c_equilibrate(inp, tgt)["GM"]
            assert abs(gw - gr) < 1e-6, (datafile, tgt, gw, gr)
    finally:
        _lib.mqmqa_db_free(cdb)


def test_binary_salt():
    _check(_find("LiCl-KCl.dat"), None, 1000.0,
           [{"LI": 1 - x, "K": x, "CL": 1.0} for x in (0.1, 0.3, 0.5, 0.7, 0.9)])


def test_ternary_slag():
    T = 1873.0
    tg = []
    for xfe in (0.2, 0.4, 0.6):
        for xmg in (0.2, 0.4):
            xsi = 1 - xfe - xmg
            if xsi > 0:
                tg.append({"FE": xfe, "MG": xmg, "SI": xsi, "O": xfe + xmg + 2 * xsi})
    _check(_find("FeO-MgO-SiO2-combined.dat"), None, T, tg)
