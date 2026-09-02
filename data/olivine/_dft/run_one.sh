#!/bin/bash
set -u; N=$1; R=/mnt/c/Users/busta/Code/mqmqa/data/olivine/_dft/runs_u; export OMP_NUM_THREADS=1
cd "$R/$N"; rm -rf out pw.out pw.err
mpirun --use-hwthread-cpus -np 10 pw.x -in pw.in > pw.out 2>pw.err
echo "$N END rc=$? $(grep '^!' pw.out|tail -1)" >> "$R/resume_progress.log"
touch "$R/${N}_DONE"; echo "$N DONE $(date +%H:%M:%S)"
