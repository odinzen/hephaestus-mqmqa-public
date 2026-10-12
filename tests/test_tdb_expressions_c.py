"""Compile tests/c/tdb_expressions.c against src/ and run it.

The C program exercises the TDB and XTDB expression readers through the C API with no
Python in between (xtdb.c is otherwise only in the browser build). On Windows it is built with the same conda clang and mingw runtime as
scripts/build.sh (MQMQA_ENV / MQMQA_CLANG); elsewhere with $CC or cc.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ["mqmqa.c", "cs_dat.c", "cef.c", "gas.c", "equil.c", "hull.c", "equilibrium.c",
           "tq.c", "xtdb.c"]


def _compiler(exe):
    if sys.platform == "win32":
        env = Path(os.environ.get("MQMQA_ENV",
                                  Path(os.environ.get("USERPROFILE", "~")) / "miniforge3/envs/calphad"))
        clang = Path(os.environ.get("MQMQA_CLANG", env / "Library/bin/clang.exe"))
        if not clang.exists():
            pytest.skip(f"clang not found at {clang}")
        mw = env / "Library/mingw-w64"
        return [str(clang), "--target=x86_64-w64-mingw32", f"--sysroot={mw / 'x86_64-w64-mingw32'}",
                f"-L{mw / 'lib/gcc/x86_64-w64-mingw32/5.3.0'}", f"-L{mw / 'x86_64-w64-mingw32/lib'}",
                "-fuse-ld=lld", "-static-libgcc", "-o", str(exe)]
    cc = os.environ.get("CC") or shutil.which("cc")
    if not cc:
        pytest.skip("no C compiler")
    return [cc, "-o", str(exe)]


def test_expression_readers_in_c(tmp_path):
    exe = tmp_path / ("tdb_expressions" + (".exe" if sys.platform == "win32" else ""))
    cmd = _compiler(exe) + ["-O1", "-std=c11", "-Wall", "-Wextra", "-Werror",
                            f"-I{ROOT / 'src'}", str(ROOT / "tests/c/tdb_expressions.c")]
    cmd += [str(ROOT / "src" / s) for s in SOURCES]
    if sys.platform != "win32":
        cmd.append("-lm")
    build = subprocess.run(cmd, capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "all passed" in run.stdout
