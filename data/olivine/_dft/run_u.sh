#!/bin/bash
set -u
R=/mnt/c/Users/busta/Code/mqmqa/data/olivine/_dft/runs_u
export OMP_NUM_THREADS=1
for d in fa x50_a; do
  cd "$R/$d" || exit 1; rm -rf out pw.out pw.err
  echo "=== START $d $(date +%H:%M:%S) ==="
  mpirun --use-hwthread-cpus -np 14 pw.x -in pw.in > pw.out 2>pw.err
  echo "=== END $d rc=$? $(date +%H:%M:%S) :: $(grep '^!' pw.out | tail -1) ==="
done
touch "$R/ALL_DONE"; echo "U DONE $(date +%H:%M:%S)"
