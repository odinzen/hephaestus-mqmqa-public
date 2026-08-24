"""Pythonic view over the C ChemSage `.dat` reader.

The C side owns an opaque database handle; this wraps it with dict/list-returning
accessors and frees it on garbage collection. Names come back uppercased, as the
reader uppercases the file to match pycalphad.
"""

from ._abi import _ffi, _lib


def _s(ptr):
    return _ffi.string(ptr).decode() if ptr != _ffi.NULL else None


class Database:
    def __init__(self, handle):
        if handle == _ffi.NULL:
            raise OSError(f"failed to read ChemSage database: {_s(_lib.mqmqa_db_error())}")
        self._db = handle

    @classmethod
    def read(cls, path):
        return cls(_lib.mqmqa_db_read_file(str(path).encode()))

    @classmethod
    def read_string(cls, text):
        return cls(_lib.mqmqa_db_read_string(text.encode()))

    def __del__(self):
        db = getattr(self, "_db", None)
        if db is not None and db != _ffi.NULL:
            _lib.mqmqa_db_free(db)
            self._db = _ffi.NULL

    # --- header ---
    @property
    def elements(self):
        return [
            (_s(_lib.mqmqa_db_element(self._db, i)), _lib.mqmqa_db_element_mass(self._db, i))
            for i in range(_lib.mqmqa_db_num_elements(self._db))
        ]

    # --- solution phases ---
    @property
    def phase_names(self):
        return [_s(_lib.mqmqa_db_phase_name(self._db, p))
                for p in range(_lib.mqmqa_db_num_phases(self._db))]

    def phase_index(self, name):
        return _lib.mqmqa_db_phase_index(self._db, name.encode())

    def is_subq(self, p):
        return _lib.mqmqa_db_phase_is_subq(self._db, p)

    def cations(self, p):
        n = _lib.mqmqa_ph_num_cations(self._db, p)
        return [dict(name=_s(_lib.mqmqa_ph_cation(self._db, p, i)),
                     charge=_lib.mqmqa_ph_cation_charge(self._db, p, i),
                     group=_lib.mqmqa_ph_cation_group(self._db, p, i)) for i in range(n)]

    def anions(self, p):
        n = _lib.mqmqa_ph_num_anions(self._db, p)
        return [dict(name=_s(_lib.mqmqa_ph_anion(self._db, p, k)),
                     charge=_lib.mqmqa_ph_anion_charge(self._db, p, k),
                     group=_lib.mqmqa_ph_anion_group(self._db, p, k)) for k in range(n)]

    def pairs(self, p, T):
        """Pair (MQMG) data: 0-based cation/anion indices, cation stoichiometry,
        zeta, and Gibbs energy evaluated at T. Lists are aligned by pair."""
        n = _lib.mqmqa_ph_num_pairs(self._db, p)
        cat = _ffi.new("int[]", n)
        an = _ffi.new("int[]", n)
        stoich = _ffi.new("double[]", n)
        zeta = _ffi.new("double[]", n)
        G = _ffi.new("double[]", n)
        _lib.mqmqa_ph_pair_indices(self._db, p, cat, an)
        _lib.mqmqa_ph_pair_stoich(self._db, p, stoich)
        _lib.mqmqa_ph_pair_zeta(self._db, p, zeta)
        _lib.mqmqa_ph_pair_gibbs(self._db, p, T, G)
        return dict(cat=list(cat), an=list(an), stoich=list(stoich),
                    zeta=list(zeta), G=list(G))

    def mqmz(self, p):
        """Coordination entries, canonicalized (A<=B, X<=Y). Z is flat [n*4],
        ready for mqmqa.coordination."""
        n = _lib.mqmqa_ph_num_mqmz(self._db, p)
        A = _ffi.new("int[]", n)
        B = _ffi.new("int[]", n)
        X = _ffi.new("int[]", n)
        Y = _ffi.new("int[]", n)
        Z = _ffi.new("double[]", n * 4)
        _lib.mqmqa_ph_mqmz(self._db, p, A, B, X, Y, Z)
        return dict(A=list(A), B=list(B), X=list(X), Y=list(Y), Z=list(Z))

    def mqmx(self, p, T):
        """Excess (MQMX) parameters with L evaluated at T. mix: 0 cation, 1
        anion, -1 other. code: 0 Q, 1 G, 2 B, 3 R."""
        n = _lib.mqmqa_ph_num_mqmx(self._db, p)
        arrs = {k: _ffi.new("int[]", n) for k in ("mix", "code", "A", "B", "X", "Y", "p", "q")}
        L = _ffi.new("double[]", n)
        _lib.mqmqa_ph_mqmx(self._db, p, arrs["mix"], arrs["code"], arrs["A"], arrs["B"],
                           arrs["X"], arrs["Y"], arrs["p"], arrs["q"])
        _lib.mqmqa_ph_mqmx_L(self._db, p, T, L)
        return {k: list(v) for k, v in arrs.items()} | {"L": list(L)}

    # --- CEF (SUBL) solution phases ---
    def phase_kind(self, p):
        """0 for MQMQA (SUBQ/SUBG), 1 for CEF (SUBL)."""
        return _lib.mqmqa_db_phase_kind(self._db, p)

    def cef_sublattices(self, p):
        """The CEF sublattice model: a list of dicts, one per sublattice, each with
        the site multiplicity and its constituent names (in the reader's order, which
        is the order site fractions are supplied to cef_gibbs)."""
        n_subl = _lib.mqmqa_ph_cef_num_subl(self._db, p)
        ncon = _ffi.new("int[]", n_subl)
        site = _ffi.new("double[]", n_subl)
        _lib.mqmqa_ph_cef_subl_ncon(self._db, p, ncon)
        _lib.mqmqa_ph_cef_site_ratio(self._db, p, site)
        return [dict(site_ratio=site[s],
                     constituents=[_s(_lib.mqmqa_ph_cef_constituent(self._db, p, s, i))
                                   for i in range(ncon[s])])
                for s in range(n_subl)]

    def cef_gibbs(self, p, Y, T, per_mole_atoms=True):
        """Molar Gibbs energy of a CEF phase at site fractions Y (flattened by
        sublattice, in the order cef_sublattices reports) and temperature T."""
        flat = [float(v) for v in Y]
        Yc = _ffi.new("double[]", flat)
        return _lib.mqmqa_ph_cef_gibbs(self._db, p, Yc, float(T), 1 if per_mole_atoms else 0)

    @property
    def stoich(self):
        return [_s(_lib.mqmqa_db_stoich_name(self._db, i))
                for i in range(_lib.mqmqa_db_num_stoich(self._db))]

    def stoich_gibbs(self, i, T):
        return _lib.mqmqa_db_stoich_gibbs(self._db, i, T)


def enumerate_quadruplets(n_cat, n_an):
    """The full quadruplet set: every unordered cation pair crossed with every
    unordered anion pair. Returns four aligned index lists (ca, cb, ax, ay)."""
    n = _lib.mqmqa_num_quadruplets(n_cat, n_an)
    ca = _ffi.new("int[]", n)
    cb = _ffi.new("int[]", n)
    ax = _ffi.new("int[]", n)
    ay = _ffi.new("int[]", n)
    _lib.mqmqa_enumerate_quadruplets(n_cat, n_an, ca, cb, ax, ay)
    return list(ca), list(cb), list(ax), list(ay)
