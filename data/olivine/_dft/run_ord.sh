#!/bin/bash
set -u; R=/mnt/c/Users/busta/Code/mqmqa/data/olivine/_dft/runs_u; export OMP_NUM_THREADS=1
for d in ord2 ord3 ord4 ord5; do
  cd "$R/$d"; rm -rf out pw.out pw.err
  ( mpirun --use-hwthread-cpus -np 3 pw.x -in pw.in > pw.out 2>pw.err; echo "END $d rc=$? $(grep '^!' pw.out|tail -1)" >> "$R/ord_progress.log" ) &
done
wait
touch "$R/ORD_DONE"; echo "ORD DONE $(date +%H:%M:%S)"
