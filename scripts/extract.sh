#!/bin/bash
set -eux

AAAI=$HOME/AAAI-24/AAAI-2024-Supplementary

for t in 60 600 1200 1800 3600; do
    rg '^(-?[0-9]+ ){1,10}0$' proof_kissat310_${t}s.drat > learnts_kissat310_${t}s_max10.txt
    cat original.cnf learnts_kissat310_${t}s_max10.txt > with-learnts_kissat310_${t}s_max10.cnf
    backdoor-searcher with-learnts_kissat310_${t}s_max10.cnf -ea-seed=42 -ea-instance-size=10 -ea-num-runs=100 -ea-num-iters=1000 2>&1 | tee log_backdoor-searcher_with-learnts_kissat310_${t}s_max10.log
    mv backdoors.txt backdoors_with-learnts_kissat310_${t}s_max10.txt
    conda run -n pysat --no-capture-output python $AAAI/scripts/rho.py --cnf with-learnts_kissat310_${t}s_max10.cnf --backdoors backdoors_with-learnts_kissat310_${t}s_max10.txt -o data_rho_with-learnts_kissat310_${t}s_max10.csv
done
