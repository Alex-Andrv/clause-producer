# AAAI-2024-Supplementary

This repository contains the supplementary materials that allows the reproduction of experiments described in the article "On Connection between Probabilistic Backdoors and Learnt Clauses in SAT Solving" submitted to AAAI-24.

## Repository structure

```
AAAI-2024-Supplementary/
├── README.md
├── plots/
├── results/
└── scripts/
    ├── common.py
    ├── drat.py
    ├── minimize.py
    ├── probing.py
    ├── rho.py
    ├── analyze-boxplots-rho-learn.R
    ├── analyze-scatterplot.R
    ├── extract.sh
    ├── learn.sh
    ├── prepare.sh
    ├── run.sh
    └── solve.sh
```

`results/` folder contains the detailed Excel table (`.xlsx`) with all the results obtained on considered SAT Competition and multipliers instances.

`plots/` folder contains some plots visualizing some of the obtained results.

Python scripts:

- [`common.py`](scripts/common.py): Common Python code used across various scripts.
- [`rho.py`](scripts/rho.py): Python script for calculating the $\rho$ value for backdoors.
- [`drat.py`](scripts/drat.py): Python script for extracting learnt clauses from the binary DRAT file.
- [`minimize.py`](scripts/minimize.py): Python script for minimizing the characteristic function using the Espresso minimizer (via PyEDA toolkit).
- [`probing.py`](scripts/probing.py): Python script for conducting the "failed literal probing".

R scripts:
- [`analyze-boxplots-rho-learn.R`](scripts/analyze-boxplots-rho-learn.R): R script to plot the boxplots for the distrbution of rho value w.r.t. variable used learnt clauses.
- [`analyze-scatterplot.R`](scripts/analyze-scatterplot.R): R script to plot the scatterplot for the results on SAT Competition instances.

Shell scripts:

- [`extract.sh`](scripts/extract.sh): Shell script for extracting learnts from DRAT files for different timeouts (60s, ..., 3600s), merging them with original CNF, and running `backdoor-searcher`.
- [`learn.sh`](scripts/learn.sh): Shell script for obtaining DRAT files with different timeouts (60s, ..., 3600s).
- [`prepare.sh`](scripts/prepare.sh): Shell script for automatically preparing (linking CNF, scripts) the folder for the specified SAT-comp instance.
- [`run.sh`](scripts/run.sh): Shell script for **running the main pipeline**: searching backdoors using `backdoor-searcher`, and then minimizing the characteristic function using `minimize.py`.
- [`solve.sh`](scripts/solve.sh): Shell script for solving (using [Kissat 3.1.0](https://github.com/arminbiere/kissat/releases/tag/rel-3.1.0)) obtained augmented CNFs with clauses derived via characteristic function minimization.

## Usage examples

### Calculating $\rho$ for backdoors

```sh
python scripts/rho.py --cnf original.cnf --backdoors backdoors_original_1k.txt -o data_rho_original.csv
```

Options:

- `--cnf <PATH>`: Original CNF.
- `--backdoors <PATH>`: File with backdoors obtained using `backdoor-searcher`.
- `-o <PATH>`: Output file with results (statistics per each backdoor) in CSV format.

### Extracting learnt clauses from binary DRAT

```sh
python scripts/drat.py --drat proof_1h_cadical.drat -o learnts_1h-cadical_max10.txt --max-size 10
```

Options:

- `--drat <PATH>`: Binary DRAT file.
- `-o <PATH>`: Output file with extracted clauses.
- `--max-size <INT>`: Maximum size (number of literals) of extracted clauses.

### Minimizing characteristic function

```sh
python scripts/minimize.py --cnf original.cnf --backdoors backdoors_original_1k.txt -o derived_original.txt
```

Options:

- `--cnf <PATH>`: Original CNF.
- `--backdoors <PATH>`: File with backdoors obtained using `backdoor-searcher`.
- `-o <PATH>`: Output file with derived clauses.
- `--num-confl <INT>`: (optional) Maximum allowed number of conflicts for solving each hard sub-task in each backdoor. If not specified, only Unit Propagation is used for determining hard tasks.

### Failed Literal Probing

```sh
python scripts/probing.py --cnf original.cnf --backdoors backdoors_original_1k.txt -o derived_original.txt
```

Options:

- `--cnf <PATH>`: Original CNF.
- `--backdoors <PATH>`: File with backdoors obtained using `backdoor-searcher`.
- `-o <PATH>`: Output file with derived units.
- `--num-confl <INT>`: (optional) Maximum allowed number of conflicts for solving each hard sub-task in each backdoor. If not specified, only Unit Propagation is used for determining hard tasks.
