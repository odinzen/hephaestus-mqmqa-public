#!/usr/bin/env bash
# Build the mqmqa shared library.
#
# The conda mingw gcc 5.3 is broken (ICEs on trivial code), so we compile with
# conda's modern clang targeting the mingw-w64 runtime that ships alongside it.
# libgcc is linked statically so the DLL has no external runtime dependency.
set -euo pipefail

ENV_DIR="${MQMQA_ENV:-C:/Users/busta/miniforge3/envs/calphad}"
CLANG="${MQMQA_CLANG:-$ENV_DIR/Library/bin/clang.exe}"
MW="$ENV_DIR/Library/mingw-w64"
GCCLIB="$MW/lib/gcc/x86_64-w64-mingw32/5.3.0"
MINGWLIB="$MW/x86_64-w64-mingw32/lib"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

"$CLANG" --target=x86_64-w64-mingw32 \
    --sysroot="$MW/x86_64-w64-mingw32" \
    -L"$GCCLIB" -L"$MINGWLIB" \
    -fuse-ld=lld -static-libgcc \
    -O2 -std=c11 -Wall -Wextra \
    -shared -I"$ROOT/src" \
    -o "$ROOT/python/mqmqa/mqmqa.dll" \
    "$ROOT/src/mqmqa.c"

echo "built $ROOT/python/mqmqa/mqmqa.dll"
