import time

import click
import tqdm

from common import *

print = click.echo

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"], max_content_width=999, show_default=True)


@click.command(context_settings=CONTEXT_SETTINGS)
# @click.option("--cnf", "path_cnf", required=True, type=click.Path(exists=True), help="File with CNF")
@click.option("--drat", "path_drat", required=True, type=click.Path(exists=True), help="File with DRAT proof")
@click.option("-o", "--output", "path_output", type=click.Path(), help="Output file with extracted clauses")
@click.option("--limit", type=int, help="Maximum number of extracted clauses")
@click.option("--max-size", type=int, help="Maximum size of learnt clauses")
@click.option("--sort", "is_sort", is_flag=True, help="Sort the extracted clauses")
def cli(
    # path_cnf,
    path_drat,
    path_output,
    limit,
    max_size,
    is_sort,
):
    time_start = time.time()

    # print(f"Loading CNF from '{path_cnf}'...")
    # cnf = CNF(from_file=path_cnf)
    # print(f"CNF clauses: {len(cnf.clauses)}")
    # print(f"CNF variables: {cnf.nv}")

    print()
    print(f"Extracting clauses{f' (max-size = {max_size})' if max_size else ''} from '{path_drat}'...")
    clauses = []

    with parse_binary_drat_mmap_tqdm(path_drat) as parser:
        for mode, clause in parser:
            if mode == "a":
                # 'added' clause
                if max_size and len(clause) > max_size:
                    # skip large clauses
                    pass
                else:
                    clauses.append(clause)
            elif mode == "d":
                # ignore 'deleted' clauses
                pass
            else:
                raise ValueError(f"Bad clause mode: '{mode}'")

            if limit and len(clauses) >= limit:
                parser.t.write(f"Reached limit {limit} of extracted clauses")
                break

    print(f"# last clause = {clause}")

    # Report extracted clauses
    print(f"Exracted {len(clauses)} clauses")
    if clauses:
        print(f"First added clause: {clauses[0]}")
        print(f"Last added clause: {clauses[-1]}")

    # Sort extracted clauses
    if is_sort:
        print(f"Sorting {len(clauses)} clauses...")
        clauses = sorted_clauses(clauses)

    # Dump extracted clauses
    if path_output:
        print(f"Writing {len(clauses)} extracted clauses to '{path_output}'...")
        with open(path_output, "w") as f:
            for clause in tqdm.tqdm(clauses):
                f.write(" ".join(map(str, clause)) + " 0\n")

    print()
    print(f"All done in {time.time() - time_start:.1f} s")


if __name__ == "__main__":
    cli()
