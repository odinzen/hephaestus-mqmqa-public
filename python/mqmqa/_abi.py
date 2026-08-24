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
        int soln_type);
    double mqmqa_excess_energy(
        int n_cat, int n_an, int n_quads,
        const int *quad_ca, const int *quad_cb,
        const int *quad_ax, const int *quad_ay,
        const double *X,
        const double *Za, const double *Zb, const double *Zx, const double *Zy,
        int n_params,
        const int *par_mix, const int *par_code,
        const int *par_A, const int *par_B, const int *par_X, const int *par_Y,
        const double *par_p, const double *par_q, const double *par_L);
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
        int n_elem,
        const int *cat_elem, const int *an_elem,
        const double *target,
        double *X_out, double *comp_err_out);

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

    int mqmqa_db_phase_kind(const void *db, int p);
    int mqmqa_ph_cef_num_subl(const void *db, int p);
    void mqmqa_ph_cef_subl_ncon(const void *db, int p, int *out);
    void mqmqa_ph_cef_site_ratio(const void *db, int p, double *out);
    int mqmqa_ph_cef_num_constituents(const void *db, int p);
    const char *mqmqa_ph_cef_constituent(const void *db, int p, int s, int i);
    double mqmqa_ph_cef_gibbs(const void *db, int p, const double *Y,
                              double T, int per_mole_atoms);

    double mqmqa_cef_gibbs(
        double T, int n_subl,
        const double *site_ratio, const int *subl_ncon, const int *subl_off,
        const double *Y, const double *atoms,
        int n_em, const int *em_con, const double *em_G,
        int n_ex, const int *ex_subl, const int *ex_i, const int *ex_j,
        const int *ex_order, const double *ex_L, const int *ex_other,
        int per_mole_atoms);

    int mqmqa_db_num_stoich(const void *db);
    const char *mqmqa_db_stoich_name(const void *db, int i);
    double mqmqa_db_stoich_gibbs(const void *db, int i, double T);

    int mqmqa_num_quadruplets(int n_cat, int n_an);
    void mqmqa_enumerate_quadruplets(int n_cat, int n_an,
                                     int *ca, int *cb, int *ax, int *ay);
    """
)

_libname = {"win32": "mqmqa.dll", "darwin": "libmqmqa.dylib"}.get(sys.platform, "libmqmqa.so")
_libpath = pathlib.Path(__file__).resolve().parent / _libname
if not _libpath.exists():
    raise OSError(f"mqmqa shared library not found at {_libpath}; run scripts/build.sh first")

_lib = _ffi.dlopen(str(_libpath))

R = _lib.mqmqa_R
ideal_entropy_binary = _lib.mqmqa_ideal_entropy_binary


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
                        Za, Zb, Zx, Zy, zeta, soln_type):
    """MQMQA ideal-mixing (configurational entropy) energy, J per mole of quadruplets.

    soln_type: 0 for SUBG, 1 for SUBQ. zeta is a flat [n_cat*n_an] sequence.
    """
    return _lib.mqmqa_ideal_mixing_energy(
        float(T), int(n_cat), int(n_an), len(X),
        _ints(quad_ca), _ints(quad_cb), _ints(quad_ax), _ints(quad_ay),
        _dbls(X),
        _dbls(Za), _dbls(Zb), _dbls(Zx), _dbls(Zy),
        _dbls(zeta), int(soln_type),
    )


def excess_energy(n_cat, n_an, quad_ca, quad_cb, quad_ax, quad_ay, X,
                  Za, Zb, Zx, Zy, par_mix, par_code,
                  par_A, par_B, par_X, par_Y, par_p, par_q, par_L):
    """Excess energy for MQMX parameters, J per mole of quadruplets."""
    return _lib.mqmqa_excess_energy(
        int(n_cat), int(n_an), len(X),
        _ints(quad_ca), _ints(quad_cb), _ints(quad_ax), _ints(quad_ay),
        _dbls(X),
        _dbls(Za), _dbls(Zb), _dbls(Zx), _dbls(Zy),
        len(par_A),
        _ints(par_mix), _ints(par_code),
        _ints(par_A), _ints(par_B), _ints(par_X), _ints(par_Y),
        _dbls(par_p), _dbls(par_q), _dbls(par_L),
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
