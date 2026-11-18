#!/usr/bin/env bash
# Runs every input script in ti/ with Thermochimica's InputScriptMode; output goes to the sealed folder.
# Set THERMOCHIMICA_DIR (a Thermochimica checkout) and SEALED_DIR (the sealed folder, outside the repo).
# The committed .ti files carry these names in place of the absolute paths they were run with.
source ~/miniforge3/etc/profile.d/conda.sh && conda activate thermochimica
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "${THERMOCHIMICA_DIR:?set THERMOCHIMICA_DIR}"
RAW="${SEALED_DIR:?set SEALED_DIR}/thermochimica_raw"
for f in "$HERE"/ti/*.ti; do
  id=$(basename "$f" .ti)
  timeout 120 ./bin/InputScriptMode "$f" > "$RAW/$id.log" 2>&1
  echo "exit=$?" >> "$RAW/$id.log"
done
