#!/bin/bash
set -eux

# Original
~/AAAI-24/kissat-3.1.0/build/kissat --relaxed --no-color original.cnf 2>&1 > log_kissat310_original.log &

# With derived (propagate)
~/AAAI-24/kissat-3.1.0/build/kissat --relaxed --no-color with-derived_original.cnf 2>&1 > log_kissat310_with-derived_original.log &

# With derived (solve_limited)
~/AAAI-24/kissat-3.1.0/build/kissat --relaxed --no-color with-derived_original_limited.cnf 2>&1 > log_kissat310_with-derived_original_limited.log &

wait
