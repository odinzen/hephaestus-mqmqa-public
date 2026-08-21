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
    """
)

_libname = {"win32": "mqmqa.dll", "darwin": "libmqmqa.dylib"}.get(sys.platform, "libmqmqa.so")
_libpath = pathlib.Path(__file__).resolve().parent / _libname
if not _libpath.exists():
    raise OSError(f"mqmqa shared library not found at {_libpath}; run scripts/build.sh first")

_lib = _ffi.dlopen(str(_libpath))

R = _lib.mqmqa_R
ideal_entropy_binary = _lib.mqmqa_ideal_entropy_binary
