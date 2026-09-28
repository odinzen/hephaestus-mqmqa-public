#!/usr/bin/env bash
# Debug build of the mqmqa library under AddressSanitizer, for hunting memory errors.
# It REPLACES python/mqmqa/mqmqa.dll; rerun scripts/build.sh before shipping or measuring.
#
# ASan on Windows needs the MSVC target (the mingw target has no ASan runtime), so this
# uses clang with the Visual Studio Build Tools libraries. It checks the C code, not the
# release toolchain. A defect of the mingw link itself (such as the truncated TLS
# directory that once corrupted the heap) does not show up here.
#
# Run the tests through the launcher it builds, which loads the ASan runtime before
# Python starts. PYTHONMALLOC=malloc routes the arrays cffi hands to C through the
# instrumented malloc, so overruns into them are caught too. pytest's faulthandler must
# be off, since ASan maps its shadow memory through access faults it handles itself, and
# --capture=sys keeps stderr a real file, or a report dies with pytest's capture file:
#   PYTHONHOME="$ENV_DIR" PYTHONMALLOC=malloc PATH="$ENV_DIR:$ENV_DIR/Library/bin:$PATH" \
#     build/asan/python-asan.exe -m pytest -q -p no:cacheprovider -p no:faulthandler \
#     --capture=sys
# pycalphad's LLVM JIT now and then aborts under ASan with "IMAGE_REL_AMD64_ADDR32NB
# relocation requires an ordered section layout" (the shadow memory crowds its code
# sections apart). That is not a report on this library; rerun the file.
set -euo pipefail

ENV_DIR="${MQMQA_ENV:-C:/Users/busta/miniforge3/envs/calphad}"
CLANG="${MQMQA_CLANG:-$ENV_DIR/Library/bin/clang.exe}"
RT_DIR="$("$CLANG" --target=x86_64-pc-windows-msvc -print-resource-dir)/lib/windows"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/python/mqmqa"
BIN="$ROOT/build/asan"
PYDLL="$(cd "$ENV_DIR" && ls python3?*.dll | head -n 1)"
mkdir -p "$BIN"

"$CLANG" --target=x86_64-pc-windows-msvc \
    -fsanitize=address -fno-omit-frame-pointer -g -O1 \
    -std=c11 -Wall -Wextra -D_CRT_SECURE_NO_WARNINGS \
    -shared -fuse-ld=lld -I"$ROOT/src" \
    -o "$OUT/mqmqa.dll" \
    "$ROOT/src/mqmqa.c" "$ROOT/src/cs_dat.c" "$ROOT/src/cef.c" "$ROOT/src/gas.c" "$ROOT/src/equil.c" "$ROOT/src/hull.c" "$ROOT/src/equilibrium.c" "$ROOT/src/tq.c" \
    "$ROOT/src/db_write.c" "$ROOT/src/xtdb.c" "$ROOT/src/vis3d.c"
rm -f "$OUT/mqmqa.lib" "$OUT/mqmqa.exp"   # the .pdb stays, ASan symbolizes its reports with it

"$CLANG" --target=x86_64-pc-windows-msvc -O1 -fuse-ld=lld -DPYDLL="L\"$PYDLL\"" \
    -o "$BIN/python-asan.exe" "$ROOT/scripts/asan_python.c"
cp "$RT_DIR/clang_rt.asan_dynamic-x86_64.dll" "$BIN/"

echo "built $OUT/mqmqa.dll with AddressSanitizer and $BIN/python-asan.exe (debug only)"
