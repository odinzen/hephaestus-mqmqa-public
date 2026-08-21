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
