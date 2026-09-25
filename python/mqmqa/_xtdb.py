"""Pythonic view over the C XTDB reader (src/xtdb.c) and its writers.

The XTDB engine is its own subsystem with its own handle: it evaluates the
third-generation models (Einstein heat capacity, two-state liquid) that the .dat/.tdb
database does not hold, so an .xtdb file is read here rather than by Database.
"""

import math
import os

from ._abi import _ffi, _lib, _GasConstantInfo
from ._database import _s, _save, _take_text


class XTDB(_GasConstantInfo):
    _R_fns = (_lib.xtdb_R_own, _lib.xtdb_R, _lib.xtdb_R_source, _lib.xtdb_R_own_source,
              _lib.xtdb_R_note)

    def __init__(self, handle, source=None):
        if handle == _ffi.NULL:
            raise OSError(f"failed to read XTDB database: {_s(_lib.xtdb_error())}")
        self._db = handle
        self.source = source

    @classmethod
    def read(cls, path):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        return cls(_lib.xtdb_read_string(text.encode()), os.path.basename(str(path)))

    @classmethod
    def read_string(cls, text):
        return cls(_lib.xtdb_read_string(text.encode()))

    def __del__(self):
        db = getattr(self, "_db", None)
        if db is not None and db != _ffi.NULL:
            _lib.xtdb_free(db)
            self._db = _ffi.NULL

    @property
    def elements(self):
        return [_s(_lib.xtdb_element(self._db, i)) for i in range(_lib.xtdb_n_elements(self._db))]

    @property
    def phase_names(self):
        return [_s(_lib.xtdb_phase(self._db, p)) for p in range(_lib.xtdb_n_phases(self._db))]

    def endmember_gibbs(self, phase, cons, T):
        """Endmember Gibbs energy per formula unit, cons like "AL:VA"; NaN if undefined."""
        ok = _ffi.new("int *", 1)
        g = _lib.xtdb_endmember_gibbs(self._db, phase.encode(), cons.encode(), float(T), ok)
        return g if ok[0] else math.nan

    def phase_gibbs(self, p, B, xB, T):
        """(G per mole of atoms, fixed x_B or None) at mole fraction xB of element B."""
        ok = _ffi.new("int *", 1)
        fixed = _ffi.new("double *", -1.0)
        g = _lib.xtdb_phase_gibbs(self._db, int(p), B.encode(), float(xB), float(T), fixed, ok)
        return (g if ok[0] else math.nan), (fixed[0] if fixed[0] >= 0 else None)

    # --- writers: file text returned, and saved when a path is given; a model the
    # target cannot hold raises ConversionError and writes nothing.
    def _write(self, fn, path, source_name):
        src = source_name if source_name is not None else (self.source or "")
        return _save(_take_text(fn(self._db, src.encode()), _lib.xtdb_error), path)

    def write_xtdb(self, path=None, source_name=None):
        return self._write(_lib.xtdb_write_xtdb, path, source_name)

    def write_tdb(self, path=None, source_name=None):
        return self._write(_lib.xtdb_write_tdb, path, source_name)

    def write_utdb(self, path=None, source_name=None):
        return self._write(_lib.xtdb_write_utdb, path, source_name)

    def write_dat(self, path=None, source_name=None):
        return self._write(_lib.xtdb_write_dat, path, source_name)
