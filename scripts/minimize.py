import time

import click
from pysat.formula import CNF
from pysat.solvers import Solver

from common import *

print = click.echo

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"], max_content_width=999, show_default=True)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option("--cnf", "path_cnf", required=True, type=click.Path(exists=True), help="File with CNF")
@click.option("--backdoors", "path_backdoors", required=True, type=click.Path(exists=True), help="File with backdoors")
@click.option("-o", "--output", "path_output", type=click.Path(), help="Output file")
@click.option("--limit", "limit_backdoors", type=int, help="Number of backdoors to use (prefix size)")
@click.option("--add-units", "is_add_derived_units", is_flag=True, help="Add derived units to the solver")
@click.option(
    "--num-confl",
    type=int,
    default=0,
    show_default=True,
    help="Number of conflicts in 'solve_limited' (0 for using 'propagate')",
)
@click.option(
    "--allow-duplicates/--no-duplicates", "is_allow_duplicates", default=True, help="Dump clauses which already present in CNF"
)
def cli(
    path_cnf,
    path_backdoors,
    path_output,
    limit_backdoors,
    is_add_derived_units,
    num_confl,
    is_allow_duplicates,
):
    time_start = time.time()

    print(f"Loading CNF from '{path_cnf}'...")
    cnf = CNF(from_file=path_cnf)
    print(f"CNF clauses: {len(cnf.clauses)}")
    print(f"CNF variables: {cnf.nv}")

    print(f"Grouping CNF clauses by size...")
    cnf_units = []
    cnf_binary = []
    cnf_ternary = []
    cnf_large = []
    for clause in cnf.clauses:
        if len(clause) == 1:
            cnf_units.append(clause[0])
        elif len(clause) == 2:
            cnf_binary.append(tuple(sorted(clause, key=abs)))
        elif len(clause) == 3:
            cnf_ternary.append(tuple(sorted(clause, key=abs)))
        else:
            cnf_large.append(tuple(sorted(clause, key=abs)))
    print(f"CNF unit clauses: {len(cnf_units)}")
    print(f"CNF binary clauses: {len(cnf_binary)}")
    print(f"CNF ternary clauses: {len(cnf_ternary)}")
    print(f"CNF large clauses: {len(cnf_large)}")

    print()
    print(f"Loading backdoors from '{path_backdoors}'...")
    backdoors = parse_backdoors(path_backdoors)
    print(f"Total backdoors: {len(backdoors)}")
    if backdoors:
        print(f"First backdoor size: {len(backdoors[0])}")

    all_backdoors = backdoors
    if limit_backdoors is not None:
        print(f"Limiting to {limit_backdoors} backdoors")
        backdoors = backdoors[:limit_backdoors]

    unique_variables = sorted(multiunion(backdoors), key=abs)
    print(f"Total variables in {len(backdoors)} backdoors: {sum(map(len, backdoors))}")
    print(f"Unique variables in {len(backdoors)} backdoors: {len(unique_variables)}")

    print()
    is_using_solve_limited = num_confl > 0
    if is_using_solve_limited:
        print(f"Note: using 'propagate' and 'solve_limited({num_confl=})'")
        solver_limited = Solver("cadical153", bootstrap_with=cnf)
    else:
        print(f"Note: using 'propagate' only")

    rho_per_backdoor = []

    units_per_backdoor = []
    new_units_per_backdoor = []
    unique_units = set()

    binary_per_backdoor = []
    new_binary_per_backdoor = []
    unique_binary = set()

    ternary_per_backdoor = []
    new_ternary_per_backdoor = []
    unique_ternary = set()

    large_per_backdoor = []
    new_large_per_backdoor = []
    unique_large = set()

    with Solver("glucose42", bootstrap_with=cnf) as solver:
        for i, variables in enumerate(backdoors):
            print()
            print(f"=== [{i+1}/{len(backdoors)}] " + "-" * 42)

            # Convert to 1-based:
            variables = [v + 1 for v in variables]

            print(f"Backdoor with {len(variables)} variables: {variables}")

            print(f"Partioning tasks...")
            hard, easy = partition_tasks(solver, variables)
            assert len(hard) + len(easy) == 2 ** len(variables)
            print(f"Total 2^{len(variables)} = {2**len(variables)} tasks: {len(hard)} hard and {len(easy)} easy")

            if is_using_solve_limited:
                print(f"Determining semi-easy tasks using 'solve_limited({num_confl=})'...")
                time_start_semieasy = time.time()
                semieasy = determine_semieasy_tasks(solver_limited, hard, num_confl)
                print(f"... done in {time.time() - time_start_semieasy:.3f} s")
                print(f"Semi-easy tasks: {len(semieasy)}")
                easy += semieasy

            rho = len(easy) / 2 ** len(variables)
            print(f"rho = {len(easy)}/{2**len(variables)} = {rho}")
            rho_per_backdoor.append(rho)

            # print()
            print(f"Minimizing characteristic function...")
            clauses = backdoor_to_clauses_via_easy(variables, easy)

            units = sorted((c[0] for c in clauses if len(c) == 1), key=abs)
            units_per_backdoor.append(units)
            for unit in units:
                if -unit in unique_units:
                    raise RuntimeError(f"Wow! {unit}")
            new_units = [x for x in units if x not in unique_units]
            new_units_per_backdoor.append(new_units)
            unique_units.update(units)
            print(f"Derived {len(units)} ({len(new_units)} new, {sum(1 for x in units if x in cnf_units)} in cnf) units: {units}")

            binary = sorted(tuple(sorted(c, key=abs)) for c in clauses if len(c) == 2)
            binary_per_backdoor.append(binary)
            new_binary = [x for x in binary if x not in unique_binary]
            new_binary_per_backdoor.append(new_binary)
            unique_binary.update(binary)
            print(
                f"Derived {len(binary)} ({len(new_binary)} new, {sum(1 for c in binary if c in cnf_binary)} in cnf) binary clauses: {binary}"
            )

            ternary = sorted(tuple(sorted(c, key=abs)) for c in clauses if len(c) == 3)
            ternary_per_backdoor.append(ternary)
            new_ternary = [x for x in ternary if x not in unique_ternary]
            new_ternary_per_backdoor.append(new_ternary)
            unique_ternary.update(ternary)
            print(
                f"Derived {len(ternary)} ({len(new_ternary)} new, {sum(1 for c in ternary if c in cnf_ternary)} in cnf) ternary clauses: {ternary}"
            )

            large = sorted(tuple(sorted(c, key=abs)) for c in clauses if len(c) > 3)
            large_per_backdoor.append(large)
            new_large = [x for x in large if x not in unique_large]
            new_large_per_backdoor.append(new_large)
            unique_large.update(large)
            print(f"Derived {len(large)} ({len(new_large)} new, {sum(1 for c in large if c in cnf_large)} in cnf) large clauses: {large}")

            if is_add_derived_units:
                for unit in new_units:
                    solver.add_clause([unit])

    if is_using_solve_limited:
        solver_limited.delete()
        del solver_limited

    print()
    print("=" * 42)
    print()

    print(f"{rho_per_backdoor = }")
    print(f"{units_per_backdoor = }")
    print(f"{new_units_per_backdoor = }")
    print(f"{binary_per_backdoor = }")
    print(f"{new_binary_per_backdoor = }")
    print(f"{ternary_per_backdoor = }")
    print(f"{new_ternary_per_backdoor = }")
    print(f"{large_per_backdoor = }")
    print(f"{new_large_per_backdoor = }")

    if path_output:
        print()
        print(f"Writing results to '{path_output}'...")
        with open(path_output, "w") as f:
            for unit in unique_units:
                if not is_allow_duplicates and unit in cnf_units:
                    # skip duplicate
                    continue
                f.write(f"{unit} 0\n")
            for c in unique_binary:
                if not is_allow_duplicates and c in cnf_binary:
                    # skip duplicate
                    continue
                f.write(" ".join(map(str, c)) + " 0\n")
            for c in unique_ternary:
                if not is_allow_duplicates and c in cnf_ternary:
                    # skip duplicate
                    continue
                f.write(" ".join(map(str, c)) + " 0\n")
            for c in unique_large:
                if not is_allow_duplicates and c in cnf_large:
                    # skip duplicate
                    continue
                f.write(" ".join(map(str, c)) + " 0\n")

    print()
    print(f"Total variables in {len(backdoors)} backdoors: {sum(map(len, backdoors))}")
    print(f"Unique variables in {len(backdoors)} backdoors: {len(unique_variables)}")
    print(
        f"Total derived (non-unique) {sum(map(len, units_per_backdoor))} units, {sum(map(len, binary_per_backdoor))} binary, {sum(map(len, ternary_per_backdoor))} ternary, and {sum(map(len, large_per_backdoor))} larger clauses"
    )

    unique_units = sorted(unique_units, key=abs)
    print(f"Derived {len(unique_units)} ({sum(1 for x in unique_units if x in cnf_units)} in cnf) unique units: {unique_units}")
    print(f"Derived {len(unique_binary)} ({sum(1 for c in unique_binary if c in cnf_binary)} in cnf) unique binary")
    print(f"Derived {len(unique_ternary)} ({sum(1 for c in unique_ternary if c in cnf_ternary)} in cnf) unique ternary")
    print(f"Derived {len(unique_large)} ({sum(1 for c in unique_large if c in cnf_large)} in cnf) unique large")
    print(
        f"Total derived {len(unique_units)+len(unique_binary)+len(unique_ternary)+len(unique_large)} ({sum(1 for x in unique_units if x in cnf_units) + sum(1 for c in unique_binary if c in cnf_binary) + sum(1 for c in unique_ternary if c in cnf_ternary) + sum(1 for c in unique_large if c in cnf_large)} in cnf) unique clauses"
    )

    # print("New:")
    # for new_units in new_units_per_backdoor:
    #     print(f"  {new_units}")
    # print("Units:")
    # for units in units_per_backdoor:
    #     print(f"  {units}")

    print()
    print(f"All done in {time.time() - time_start:.1f} s")


if __name__ == "__main__":
    cli()
