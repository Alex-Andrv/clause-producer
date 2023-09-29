#!/bin/bash
set -eux

AAAI=$HOME/AAAI-24/AAAI-2024-Supplementary

# Find backdoors
backdoor-searcher original.cnf -ea-seed=42 -ea-instance-size=10 -ea-num-runs=100 -ea-num-iters=1000 2>&1 | tee log_backdoor-searcher_original.log

# Rename found backdoors
mv backdoors.txt backdoors_original.txt

# Calculate rho
conda run -n pysat --no-capture-output python $AAAI/scripts/rho.py --cnf original.cnf --backdoors backdoors_original.txt -o data_rho_original.csv

# Minimize characteristic function
conda run -n pysat --no-capture-output python $AAAI/scripts/minimize.py --cnf original.cnf --backdoors backdoors_original.txt -o derived_original.txt 2>&1 | tee log_minimize_original.log

# Merge CNF with derived clauses
cat original.cnf derived_original.txt > with-derived_original.cnf

# Minimize characteristic function using limited solver
conda run -n pysat --no-capture-output python $AAAI/scripts/minimize.py --cnf original.cnf --backdoors backdoors_original.txt -o derived_original_limited.txt --num-confl 1000 2>&1 | tee log_minimize_original_limited.log

# Merge CNF with derived clauses
cat original.cnf derived_original_limited.txt > with-derived_original_limited.cnf
