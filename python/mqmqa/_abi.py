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
