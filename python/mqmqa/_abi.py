"""ABI-mode cffi binding to the prebuilt mqmqa shared library.

ABI mode (dlopen of a prebuilt DLL) avoids needing the Python build compiler to
match the one that built the library, which keeps Windows painless.
"""

import pathlib
import sys

import cffi

_ffi = cffi.FFI()
_ffi.cdef(
    """
    int mqmqa_set_gas_constant(int mode);
    int mqmqa_gas_constant_mode(void);
    double mqmqa_gas_constant_choice(int choice);
    double mqmqa_gas_constant(double own);
    double mqmqa_R(void);
    double mqmqa_ideal_entropy_binary(double x);
    double mqmqa_reference_energy(
        int n_quads,
        const int *quad_ca, const int *quad_cb,
        const int *quad_ax, const int *quad_ay,
        const double *X,
        int n_pairs,
        const int *pair_c, const int *pair_a,
        const double *Gax, const double *stoich,
        const double *Z);
    double mqmqa_ideal_mixing_energy(
        double T,
        int n_cat, int n_an, int n_quads,
        const int *quad_ca, const int *quad_cb,
        const int *quad_ax, const int *quad_ay,
        const double *X,
        const double *Za, const double *Zb, const double *Zx, const double *Zy,
        const double *zeta,
        int soln_type, double R_own);
    double mqmqa_excess_energy(
        int n_cat, int n_an, int n_quads,
        const int *quad_ca, const int *quad_cb,
        const int *quad_ax, const int *quad_ay,
        const double *X,
        const double *Za, const double *Zb, const double *Zx, const double *Zy,
        int soln_type,
        int n_params,
        const int *par_mix, const int *par_code,
        const int *par_A, const int *par_B, const int *par_X, const int *par_Y,
        const double *par_p, const double *par_q, const double *par_L,
        const double *par_r, const int *par_addcat,
        const int *cat_group, const int *an_group);
    double mqmqa_coordination(
        int sp_is_cation, int sp_idx,
        int A, int B, int X, int Y,
        int n_cat, int n_an,
        const double *q_cat, const double *q_an,
        int n_mqmz,
        const int *mz_A, const int *mz_B, const int *mz_X, const int *mz_Y,
        const double *mz_Z);
    double mqmqa_equilibrate(
        double T,
        int n_cat, int n_an, int n_quads,
        const int *quad_ca, const int *quad_cb,
        const int *quad_ax, const int *quad_ay,
        const double *Za, const double *Zb, const double *Zx, const double *Zy,
        const double *zeta,
        int soln_type,
        int n_pairs,
        const int *pair_c, const int *pair_a,
        const double *Gax, const double *stoich,
        const double *Zref,
        int n_params,
        const int *par_mix, const int *par_code,
        const int *par_A, const int *par_B, const int *par_X, const int *par_Y,
        const double *par_p, const double *par_q, const double *par_L,
        const double *par_r, const int *par_addcat,
        const int *cat_group, const int *an_group,
        double R_own,
        int n_elem,
        const int *cat_elem, const int *an_elem,
        const double *target,
        double *X_out, double *comp_err_out);

    double mqmqa_equilibrate_db(const void *db, int phase, double T,
        const double *target_elem, double *X_out, double *err_out);

    double mqmqa_db_R_own(const void *db);
    double mqmqa_db_R(const void *db);
    int mqmqa_db_R_source(const void *db);
    int mqmqa_db_R_own_source(const void *db);
    const char *mqmqa_db_R_note(const void *db);
    double xtdb_R_own(const void *db);
    double xtdb_R(const void *db);
    int xtdb_R_source(const void *db);
    int xtdb_R_own_source(const void *db);
    const char *xtdb_R_note(const void *db);
    double mqmqa_gas_R_own(const void *g);
    double mqmqa_gas_R(const void *g);
    int mqmqa_gas_R_source(const void *g);
    int mqmqa_gas_R_own_source(const void *g);
    const char *mqmqa_gas_R_note(const void *g);
    int mqmqa_db_declare_R(void *db, int choice);
    int xtdb_declare_R(void *db, int choice);
    int mqmqa_gas_declare_R(void *g, int choice);
    void *mqmqa_db_read_file(const char *path);
    void *mqmqa_db_read_string(const char *text);
    void mqmqa_db_free(void *db);
    const char *mqmqa_db_error(void);

    int mqmqa_db_num_elements(const void *db);
    const char *mqmqa_db_element(const void *db, int i);
    double mqmqa_db_element_mass(const void *db, int i);

    int mqmqa_db_num_phases(const void *db);
    int mqmqa_db_phase_index(const void *db, const char *name);
    const char *mqmqa_db_phase_name(const void *db, int p);
    int mqmqa_db_phase_is_subq(const void *db, int p);

    int mqmqa_ph_num_cations(const void *db, int p);
    int mqmqa_ph_num_anions(const void *db, int p);
    const char *mqmqa_ph_cation(const void *db, int p, int i);
    const char *mqmqa_ph_anion(const void *db, int p, int k);
    double mqmqa_ph_cation_charge(const void *db, int p, int i);
    double mqmqa_ph_anion_charge(const void *db, int p, int k);
    int mqmqa_ph_cation_group(const void *db, int p, int i);
    int mqmqa_ph_anion_group(const void *db, int p, int k);

    int mqmqa_ph_num_pairs(const void *db, int p);
    void mqmqa_ph_pair_indices(const void *db, int p, int *cat, int *an);
    void mqmqa_ph_pair_stoich(const void *db, int p, double *stoich);
    void mqmqa_ph_pair_zeta(const void *db, int p, double *zeta);
    void mqmqa_ph_pair_gibbs(const void *db, int p, double T, double *G);

    int mqmqa_ph_num_mqmz(const void *db, int p);
    void mqmqa_ph_mqmz(const void *db, int p,
                       int *A, int *B, int *X, int *Y, double *Z);

    int mqmqa_ph_num_mqmx(const void *db, int p);
    void mqmqa_ph_mqmx(const void *db, int p,
                       int *mix, int *code, int *A, int *B, int *X, int *Y,
                       int *p_exp, int *q_exp);
    void mqmqa_ph_mqmx_L(const void *db, int p, double T, double *L);
    void mqmqa_ph_mqmx_ternary(const void *db, int p, double *r_exp, int *add_cat);
    const char *mqmqa_ph_excess_unsupported(const void *db, int p);

    int mqmqa_db_phase_kind(const void *db, int p);
    int mqmqa_ph_cef_num_subl(const void *db, int p);
    void mqmqa_ph_cef_subl_ncon(const void *db, int p, int *out);
    void mqmqa_ph_cef_site_ratio(const void *db, int p, double *out);
    int mqmqa_ph_cef_num_constituents(const void *db, int p);
    const char *mqmqa_ph_cef_constituent(const void *db, int p, int s, int i);
    double mqmqa_ph_cef_gibbs(const void *db, int p, const double *Y,
                              double T, int per_mole_atoms);
    double mqmqa_ph_cef_line_gibbs(const void *db, int p, double y, double T,
                                   int per_mole_atoms, double *Y_out);

    double mqmqa_cef_gibbs(
        double T, int n_subl,
        const double *site_ratio, const int *subl_ncon, const int *subl_off,
        const double *Y, const double *atoms,
        int n_em, const int *em_con, const double *em_G,
        int n_ex, const int *ex_subl, const int *ex_i, const int *ex_j,
        const int *ex_order, const double *ex_L, const int *ex_other,
        int per_mole_atoms, double R_own);

    int mqmqa_db_num_stoich(const void *db);
    const char *mqmqa_db_stoich_name(const void *db, int i);
    double mqmqa_db_stoich_gibbs(const void *db, int i, double T);
    void mqmqa_db_stoich_elems(const void *db, int i, double *out);

    const char *mqmqa_version(void);
    char *mqmqa_db_write_tdb(const void *db, const char *source_name);
    char *mqmqa_db_write_utdb(const void *db, const char *source_name);
    char *mqmqa_db_write_dat(const void *db, const char *source_name);
    char *mqmqa_db_write_xtdb(const void *db, const char *source_name);
    void mqmqa_text_free(char *text);

    void *xtdb_read_string(const char *text);
    void xtdb_free(void *db);
    const char *xtdb_error(void);
    int xtdb_n_elements(const void *db);
    const char *xtdb_element(const void *db, int i);
    int xtdb_n_phases(const void *db);
    const char *xtdb_phase(const void *db, int p);
    double xtdb_endmember_gibbs(const void *db, const char *phase, const char *cons,
                                double T, int *ok);
    double xtdb_phase_gibbs(const void *db, int p, const char *B, double xB, double T,
                            double *fixed, int *ok);
    char *xtdb_write_xtdb(const void *db, const char *source_name);
    char *xtdb_write_tdb(const void *db, const char *source_name);
    char *xtdb_write_utdb(const void *db, const char *source_name);
    char *xtdb_write_dat(const void *db, const char *source_name);

    int mqmqa_num_quadruplets(int n_cat, int n_an);
    void mqmqa_enumerate_quadruplets(int n_cat, int n_an,
                                     int *ca, int *cb, int *ax, int *ay);

    void *mqmqa_gas_read_string(const char *text);
    void mqmqa_gas_free(void *g);
    const char *mqmqa_gas_error(void);
    int mqmqa_gas_num_species(const void *g);
    const char *mqmqa_gas_species_name(const void *g, int i);
    int mqmqa_gas_num_elements(const void *g);
    const char *mqmqa_gas_element(const void *g, int e);
    double mqmqa_gas_species_grt(const void *g, int i, double T);
    int mqmqa_gas_equilibrium(const void *g, double T, double P,
                              const double *b, double *out_x);
    int mqmqa_gas_equilibrium_ex(const void *g, double T, double P,
                                 const double *b, int nonideal, double *out_x);
    int mqmqa_gas_condensed_equilibrium(const void *g, int n_elem, const double *b,
                                        double T, double P, int n_cond,
                                        const double *cond_grt, const double *cond_stoich,
                                        double *out_x, double *out_cond, double *out_pi);
    """
)

_libname = {"win32": "mqmqa.dll", "darwin": "libmqmqa.dylib"}.get(sys.platform, "libmqmqa.so")
_libpath = pathlib.Path(__file__).resolve().parent / _libname
if not _libpath.exists():
    raise OSError(f"mqmqa shared library not found at {_libpath}; run scripts/build.sh first")

_lib = _ffi.dlopen(str(_libpath))

R = _lib.mqmqa_R
ideal_entropy_binary = _lib.mqmqa_ideal_entropy_binary

# Gas-constant modes, in the order of the C enum (MQMQA_R_AS_ASSESSED ...).
GAS_CONSTANT_MODES = ("as_assessed", "calphad", "sgte", "si")

# Where a database's R comes from, in the order of the C enum (MQMQA_R_SRC_FILE ...).
GAS_CONSTANT_SOURCES = ("read from file", "inferred from constants in the file",
                        "format convention, not stated in file", "declared by user",
                        "user override")


class _GasConstantInfo:
    """R properties shared by the database handles; _R_fns names the C accessors."""

    @property
    def own_gas_constant(self):
        """This database's own R, what its calculations use unless a mode forces another."""
        return self._R_fns[0](self._db)

    @property
    def gas_constant(self):
        """The R this database's calculations use now."""
        return self._R_fns[1](self._db)

    @property
    def gas_constant_source(self):
        """Where the R in use comes from ("user override" while a mode is forced)."""
        return GAS_CONSTANT_SOURCES[self._R_fns[2](self._db)]

    @property
    def own_gas_constant_source(self):
        return GAS_CONSTANT_SOURCES[self._R_fns[3](self._db)]

    @property
    def gas_constant_note(self):
        """One line for the user: the R in use and where it comes from."""
        return _ffi.string(self._R_fns[4](self._db)).decode()

    def declare_gas_constant(self, choice):
        """Declare the R this database was assessed with when the file does not state it:
        "calphad", "sgte" or "si", or "as_assessed" to withdraw a declaration. It is then
        the database's own value, used in the as-assessed mode and recorded by the
        writers. Raises ValueError when the file states R."""
        if choice not in GAS_CONSTANT_MODES:
            raise ValueError(f"gas constant choice must be one of {GAS_CONSTANT_MODES}")
        if self._R_fns[5](self._db, GAS_CONSTANT_MODES.index(choice)) != 0:
            raise ValueError(_ffi.string(self._R_fns[6]()).decode())


def set_gas_constant(mode):
    """Engine-wide gas constant for calculations: "as_assessed" (each database keeps
    its own value, the default), or "calphad" (8.3145), "sgte" (8.31451), "si"
    (8.314462618) forced everywhere. Never written into a file."""
    if mode not in GAS_CONSTANT_MODES:
        raise ValueError(f"gas constant mode must be one of {GAS_CONSTANT_MODES}, not {mode!r}")
    _lib.mqmqa_set_gas_constant(GAS_CONSTANT_MODES.index(mode))


def gas_constant_mode():
    return GAS_CONSTANT_MODES[_lib.mqmqa_gas_constant_mode()]


def gas_constant_choice(choice):
    """The value of one labeled choice ("calphad", "sgte", "si"), whatever the mode."""
    if choice not in GAS_CONSTANT_MODES[1:]:
        raise ValueError(f"gas constant choice must be one of {GAS_CONSTANT_MODES[1:]}")
    return _lib.mqmqa_gas_constant_choice(GAS_CONSTANT_MODES.index(choice))


def gas_constant(own):
    """The R a calculation uses for data whose own value is `own` (the mode applied)."""
    return _lib.mqmqa_gas_constant(float(own))


def _ints(seq):
    return _ffi.new("int[]", [int(v) for v in seq])


def _dbls(seq):
    return _ffi.new("double[]", [float(v) for v in seq])


def reference_energy(quad_ca, quad_cb, quad_ax, quad_ay, X,
                     pair_c, pair_a, Gax, stoich, Z):
    """MQMQA reference (pair) energy, J per mole of quadruplets.

    Z is a flat row-major [n_pairs * n_quads] sequence.
    """
    return _lib.mqmqa_reference_energy(
        len(X),
        _ints(quad_ca), _ints(quad_cb), _ints(quad_ax), _ints(quad_ay),
        _dbls(X),
        len(pair_c),
        _ints(pair_c), _ints(pair_a),
        _dbls(Gax), _dbls(stoich),
        _dbls(Z),
    )


def ideal_mixing_energy(T, n_cat, n_an, quad_ca, quad_cb, quad_ax, quad_ay, X,
                        Za, Zb, Zx, Zy, zeta, soln_type, R_own=None):
    """MQMQA ideal-mixing (configurational entropy) energy, J per mole of quadruplets.

    soln_type: 0 for SUBG, 1 for SUBQ. zeta is a flat [n_cat*n_an] sequence. R_own is
    the database's own gas constant (Database.own_gas_constant), the CALPHAD 8.3145
    when omitted; the engine-wide mode is applied to it.
    """
    return _lib.mqmqa_ideal_mixing_energy(
        float(T), int(n_cat), int(n_an), len(X),
        _ints(quad_ca), _ints(quad_cb), _ints(quad_ax), _ints(quad_ay),
        _dbls(X),
        _dbls(Za), _dbls(Zb), _dbls(Zx), _dbls(Zy),
        _dbls(zeta), int(soln_type),
        _own(R_own),
    )


def _own(R_own):
    return float(R_own) if R_own is not None else _lib.mqmqa_gas_constant_choice(1)


def _groups(seq):
    return _ffi.NULL if seq is None else _ints(seq)


def excess_energy(n_cat, n_an, quad_ca, quad_cb, quad_ax, quad_ay, X,
                  Za, Zb, Zx, Zy, par_mix, par_code,
                  par_A, par_B, par_X, par_Y, par_p, par_q, par_L,
                  par_r=None, par_addcat=None, cat_group=None, an_group=None, *,
                  soln_type):
    """Excess energy for MQMX parameters, J per mole of quadruplets.

    soln_type: 0 for SUBG, 1 for SUBQ (Database.is_subq); a reciprocal SUBQ phase's
    G-code terms depend on it. cat_group/an_group are the species' chemical groups;
    None puts a whole sublattice in one group. NaN for a term the engine does not
    evaluate."""
    n = len(par_A)
    return _lib.mqmqa_excess_energy(
        int(n_cat), int(n_an), len(X),
        _ints(quad_ca), _ints(quad_cb), _ints(quad_ax), _ints(quad_ay),
        _dbls(X),
        _dbls(Za), _dbls(Zb), _dbls(Zx), _dbls(Zy),
        int(soln_type),
        n,
        _ints(par_mix), _ints(par_code),
        _ints(par_A), _ints(par_B), _ints(par_X), _ints(par_Y),
        _dbls(par_p), _dbls(par_q), _dbls(par_L),
        _dbls(par_r if par_r is not None else [0.0] * n),
        _ints(par_addcat if par_addcat is not None else [-1] * n),
        _groups(cat_group), _groups(an_group),
    )


def coordination(sp_is_cation, sp_idx, A, B, X, Y, n_cat, n_an, q_cat, q_an,
                 mz_A, mz_B, mz_X, mz_Y, mz_Z):
    """Coordination number Z of a species in a quadruplet."""
    return _lib.mqmqa_coordination(
        int(sp_is_cation), int(sp_idx),
        int(A), int(B), int(X), int(Y),
        int(n_cat), int(n_an),
        _dbls(q_cat), _dbls(q_an),
        len(mz_A),
        _ints(mz_A), _ints(mz_B), _ints(mz_X), _ints(mz_Y), _dbls(mz_Z),
    )


def _check_charge_balance(inp, amounts):
    """Raise on a composition no quadruplet distribution can hold.

    The solver returns NaN for such input, which is easy to miss. Checked only when
    every element is a single ion, so the balance is unambiguous.
    """
    if "q_cat" not in inp:
        return
    charge = {}
    for e, z in zip(inp["cat_el"] + inp["an_el"], list(inp["q_cat"]) + [-z for z in inp["q_an"]]):
        charge.setdefault(e.upper(), set()).add(z)
    if any(len(z) != 1 for z in charge.values()):
        return
    plus = sum(amounts[e] * z for e, (z,) in charge.items() if z > 0)
    minus = -sum(amounts[e] * z for e, (z,) in charge.items() if z < 0)
    if abs(plus - minus) > 1e-9 * max(plus, minus):
        raise ValueError(f"composition is not charge balanced: cation charge {plus:.6g}, "
                         f"anion charge {minus:.6g}")


def c_equilibrate(inp, x_target):
    """Solve the single-phase equilibrium in C, given inputs from build_inputs.

    inp is the dict that mqmqa.equilibrium.build_inputs produces; x_target maps
    element -> mole fraction (need not be normalized). Returns a dict with the
    equilibrium quadruplet fractions X, molar Gibbs energy GM (J per mole of
    atoms), and the composition error, mirroring equilibrium.equilibrate.
    """
    ex = inp["ex"]
    elements = sorted(set(inp["cat_el"]) | set(inp["an_el"]))
    eid = {e: i for i, e in enumerate(elements)}
    cat_elem = [eid[e] for e in inp["cat_el"]]
    an_elem = [eid[e] for e in inp["an_el"]]

    tgt = {e.upper(): 0.0 for e in elements}
    for e, v in x_target.items():
        tgt[e.upper()] += float(v)
    tot = sum(tgt.values())
    target = [tgt[e] / tot for e in elements]
    _check_charge_balance(inp, tgt)

    n_quads = len(inp["quads"])
    X_out = _ffi.new("double[]", n_quads)
    comp_err = _ffi.new("double[]", 1)

    gm = _lib.mqmqa_equilibrate(
        float(inp["T"]),
        int(inp["ncat"]), int(inp["nan"]), n_quads,
        _ints(inp["qca"]), _ints(inp["qcb"]), _ints(inp["qax"]), _ints(inp["qay"]),
        _dbls(inp["Za"]), _dbls(inp["Zb"]), _dbls(inp["Zx"]), _dbls(inp["Zy"]),
        _dbls(inp["zeta"]), int(inp["soln_type"]),
        len(inp["pcat"]),
        _ints(inp["pcat"]), _ints(inp["pan"]),
        _dbls(inp["pG"]), _dbls(inp["pstoich"]), _dbls(inp["Ztab"]),
        len(ex["A"]),
        _ints(ex["mix"]), _ints(ex["code"]),
        _ints(ex["A"]), _ints(ex["B"]), _ints(ex["X"]), _ints(ex["Y"]),
        _dbls(ex["p"]), _dbls(ex["q"]), _dbls(ex["L"]),
        _dbls(ex.get("r", [0.0] * len(ex["A"]))),
        _ints(ex.get("addcat", [-1] * len(ex["A"]))),
        _groups(inp.get("cat_group")), _groups(inp.get("an_group")),
        _own(inp.get("R_own")),
        len(elements),
        _ints(cat_elem), _ints(an_elem),
        _dbls(target),
        X_out, comp_err,
    )
    return {
        "X": [X_out[q] for q in range(n_quads)],
        "GM": gm,
        "comp_error": comp_err[0],
    }
