#!/bin/bash
set -eux

for t in 60 600 1200 1800 3600; do
    ~/AAAI-24/kissat-3.1.0/build/kissat --no-binary --time=${t} original.cnf proof_kissat310_${t}s.drat 2>&1 > log_proof_kissat310_${t}s.log
done
