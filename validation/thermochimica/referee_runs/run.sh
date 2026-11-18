#!/usr/bin/env bash
# Written by referee.py. Set THERMOCHIMICA_DIR to a Thermochimica checkout; the committed .ti files
# carry THERMOCHIMICA_DIR and REPO_DIR in place of the absolute paths they were run with.
source ~/miniforge3/etc/profile.d/conda.sh
conda activate thermochimica
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "${THERMOCHIMICA_DIR:?set THERMOCHIMICA_DIR}"
for f in "$HERE"/*.ti; do
  id=$(basename "$f" .ti)
  if [ ! -f "$HERE/$id.json" ]; then
    timeout 120 ./bin/InputScriptMode "$f" > "$HERE/$id.log" 2>&1
  fi
done
