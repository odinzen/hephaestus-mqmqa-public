#!/usr/bin/env bash
# Build the WebAssembly engine for the browser calculator.
#
# The same C core (energy terms + ChemSage reader) compiled with emscripten to a
# single self-contained JS file (the .wasm is inlined as base64, SINGLE_FILE=1),
# so the whole engine ships as one asset a static page loads. No server, no
# install. emscripten lives in its own conda env; we invoke it through conda run.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/web"
CONDA="${MQMQA_CONDA:-C:/Users/busta/miniforge3/Scripts/conda.exe}"
# The conda-forge emscripten config looks for node under Library/bin, but the
# nodejs package installs it in the env root; point NODE_JS at the real binary.
export NODE_JS="${NODE_JS:-C:/Users/busta/miniforge3/envs/wasm/node.exe}"
mkdir -p "$OUT"

# Export exactly the public API (every MQMQA_API declaration), plus malloc/free for
# marshaling arrays from JS. Generated from the headers so it never drifts.
FUNCS=$(grep -hE 'MQMQA_API' "$ROOT"/src/*.h \
        | grep -oE 'mqmqa_[A-Za-z0-9_]+\(' | tr -d '(' | sort -u)
EXPORTS='"_malloc","_free"'
for f in $FUNCS; do EXPORTS="$EXPORTS,\"_$f\""; done

# NOTE: -O0 for now. The conda-forge emscripten 4.0.9 ships a mismatched wasm-opt
# (binaryen 117 vs expected 123) that rejects --enable-bulk-memory-opt, so the -O2
# binaryen pass fails. -O0 skips it. Revisit for a size-optimized release build.
"$CONDA" run -n wasm emcc \
    -O0 -std=c11 -Wall \
    -I"$ROOT/src" \
    "$ROOT/src/mqmqa.c" "$ROOT/src/cs_dat.c" \
    -s "EXPORTED_FUNCTIONS=[$EXPORTS]" \
    -s EXPORTED_RUNTIME_METHODS='["ccall","cwrap","UTF8ToString","stringToUTF8","lengthBytesUTF8","getValue","setValue"]' \
    -s ALLOW_MEMORY_GROWTH=1 \
    -s MODULARIZE=1 -s EXPORT_NAME=Hephaestus \
    -s SINGLE_FILE=1 \
    -o "$OUT/hephaestus.js"

echo "built $OUT/hephaestus.js"
