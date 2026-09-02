#!/bin/bash
set -u; R=/mnt/c/Users/busta/Code/mqmqa/data/olivine/_dft/runs_u; export OMP_NUM_THREADS=1
cd "$R/sqs"; rm -rf out pw.out pw.err
mpirun --use-hwthread-cpus -np 10 pw.x -in pw.in > pw.out 2>pw.err
echo "SQS END rc=$? $(grep '^!' pw.out|tail -1)" >> "$R/sqs_progress.log"
touch "$R/SQS_DONE"; echo "SQS DONE $(date +%H:%M:%S)"
