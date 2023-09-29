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
def cli(
    path_cnf,
    path_backdoors,
    path_output,
    limit_backdoors,
    is_add_derived_units,
    num_confl,
):
    time_start = time.time()

    print(f"Loading CNF from '{path_cnf}'...")
    cnf = CNF(from_file=path_cnf)
    print(f"CNF clauses: {len(cnf.clauses)}")
    print(f"CNF variables: {cnf.nv}")

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
    unique_derived_units = set()
    units_per_backdoor = []
    new_units_per_backdoor = []

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

            rho = len(easy) / 2 ** len(variables)
            print(f"rho = {len(easy)}/{2**len(variables)} = {rho}")
            rho_per_backdoor.append(rho)

            print()
            if is_using_solve_limited:
                print(f"Performing failed literal probing using 'solve_limited({num_confl=})'...")
                time_start_limited = time.time()
                units = perform_probing_limited(solver_limited, variables)
                print(f"... done in {time.time() - time_start_limited:.3f} s")
            else:
                print(f"Performing failed literal probing using 'propagate'...")
                units = perform_probing(solver, variables)
            print(f"Derived {len(units)} units: {units}")
            for unit in units:
                if -unit in unique_derived_units:
                    raise RuntimeError("Wow!")
            new_units = [x for x in units if x not in unique_derived_units]
            print(f"{len(new_units)} new units: {new_units}")
            unique_derived_units.update(units)
            units_per_backdoor.append(units)
            new_units_per_backdoor.append(new_units)

            if is_add_derived_units:
                for unit in new_units:
                    solver.add_clause([unit])

    if is_using_solve_limited:
        solver_limited.delete()
        del solver_limited

    print()
    print("=" * 42)
    print()

    print(f"Total variables in {len(backdoors)} backdoors: {sum(map(len, backdoors))}")
    print(f"Unique variables in {len(backdoors)} backdoors: {len(unique_variables)}")

    unique_derived_units = sorted(unique_derived_units, key=abs)
    print(f"Total {len(unique_derived_units)} unique derived units: {unique_derived_units}")

    if len(backdoors) <= 30:
        print("New:")
        for new_units in new_units_per_backdoor:
            print(f"  {new_units}")
        print("Units:")
        for units in units_per_backdoor:
            print(f"  {units}")

    if path_output:
        print(f"Writing derived units to '{path_output}'...")
        with open(path_output, "w") as f:
            s = " ".join(map(str, unique_derived_units))
            f.write(f"{s}\n")

    print()
    print(f"All done in {time.time() - time_start:.1f} s")


if __name__ == "__main__":
    cli()
