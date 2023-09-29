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

    num_hard_per_backdoor = []
    num_easy_per_backdoor = []
    num_semi_per_backdoor = []
    rho_per_backdoor = []
    rho_t_per_backdoor = []

    with Solver("glucose42", bootstrap_with=cnf) as solver:
        for i, variables in enumerate(backdoors):
            print()
            print(f"=== [{i+1}/{len(backdoors)}] " + "-" * 42)

            # Convert to 1-based:
            variables = [v + 1 for v in variables]

            print(f"Backdoor with {len(variables)} variables: {variables}")

            print(f"Partioning 2^{len(variables)} = {2**len(variables)} tasks...")
            hard, easy = partition_tasks(solver, variables)
            assert len(hard) + len(easy) == 2 ** len(variables)
            print(f"Hard tasks: {len(hard)}")
            print(f"Easy tasks: {len(easy)}")
            num_hard_per_backdoor.append(len(hard))
            num_easy_per_backdoor.append(len(easy))

            rho = len(easy) / 2 ** len(variables)
            print(f"rho = {len(easy)}/{2**len(variables)} = {rho}")
            rho_per_backdoor.append(rho)

            if is_using_solve_limited:
                print(f"Determining semi-easy tasks using 'solve_limited({num_confl=})'...")
                time_start_semieasy = time.time()
                semieasy = determine_semieasy_tasks(solver_limited, hard, num_confl)
                print(f"... done in {time.time() - time_start_semieasy:.3f} s")
                print(f"Semi-easy tasks: {len(semieasy)}")
                num_semi_per_backdoor.append(len(semieasy))

                rho_t = (len(easy) + len(semieasy)) / 2 ** len(variables)
                print(f"rho_t = ({len(easy)}+{len(semieasy)})/{2**len(variables)} = {rho_t}")
                rho_t_per_backdoor.append(rho_t)
            else:
                num_semi_per_backdoor.append(0)
                rho_t_per_backdoor.append(rho)

    if is_using_solve_limited:
        solver_limited.delete()
        del solver_limited

    print()
    print("=" * 42)
    print()

    print(f"Total variables in {len(backdoors)} backdoors: {sum(map(len, backdoors))}")
    print(f"Unique variables in {len(backdoors)} backdoors: {len(unique_variables)}")

    print(f"hard: {num_hard_per_backdoor}")
    print(f"easy: {num_easy_per_backdoor}")
    if is_using_solve_limited:
        print(f"semi: {num_semi_per_backdoor}")

    print(f"rho: {rho_per_backdoor}")
    if is_using_solve_limited:
        print(f"rho_t: {rho_t_per_backdoor}")

    if path_output:
        print(f"Writing output to '{path_output}'...")
        with open(path_output, "w") as f:
            # Header:
            if is_using_solve_limited:
                f.write(f"index,hard,easy,semi,rho,rho_t\n")
            else:
                f.write(f"index,hard,easy,rho\n")

            # Data:
            for i in range(len(backdoors)):
                # variables = backdoors[i]
                num_hard = num_hard_per_backdoor[i]
                num_easy = num_easy_per_backdoor[i]
                rho = rho_per_backdoor[i]
                if is_using_solve_limited:
                    num_semi = num_semi_per_backdoor[i]
                    rho_t = rho_t_per_backdoor[i]
                    f.write(f"{i},{num_hard},{num_easy},{num_semi},{rho},{rho_t}\n")
                else:
                    f.write(f"{i},{num_hard},{num_easy},{rho}\n")

    print()
    print(f"All done in {time.time() - time_start:.1f} s")


if __name__ == "__main__":
    cli()
