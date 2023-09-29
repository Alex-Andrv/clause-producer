import contextlib
import gzip
import mmap
import os
import re
from itertools import product
from typing import List, Iterable
import tqdm


def bool2int(b):
    return 1 if b else 0


def bool2sign(b):
    return -1 if b else 1


def signed(x, s):
    return bool2sign(s) * x


def multiunion(iterables):
    xs = set()
    for ys in iterables:
        xs.update(ys)
    return xs


def sorted_clauses(clauses):
    result = [sorted(clause, key=abs) for clause in clauses]
    result.sort(key=lambda c: (len(c), tuple(map(abs, c))))
    return result


def parse_backdoors(path) -> List[List[int]]:
    backdoors = []
    with open(path, "r") as f:
        RE = re.compile(r"\[(\d+(?:, \d+)*)\]")
        for line in f:
            if m := RE.search(line):
                variables = [int(x) for x in m.group(1).split(", ")]
                assert all(v >= 0 for v in variables), "Variables must be non-negative"
                backdoors.append(variables)
    return backdoors


def partition_tasks(solver, variables):
    """
    Partition tasks into "hard" and "easy" categories based
    on their solvability using only Unit Propagation.

    ### Returns:
        `Tuple[List[List[Literal]], List[List[Literal]]]`: A tuple containing two lists.
        - The first list contains "hard" task assignments (cubes),
        where assumptions do not lead to immediate UNSAT using only Unit Propagation.
        - The second list contains "easy" task assignments (cubes),
        where assumptions lead to a conflict (UNSAT) via Unit Propagation.
    """

    hard = []
    easy = []

    for assignment in product([False, True], repeat=len(variables)):
        assumptions = [signed(variables[i], s) for i, s in enumerate(assignment)]
        (result, _) = solver.propagate(assumptions)
        # 'result' is True if there is NO conflict, which corresponds to a "hard" task
        # 'result' is False when there IS a conflict, which corresponds to an "easy" task

        if result == True:
            # print(f"Found hard task: {assumptions}")
            hard.append(assumptions)
        elif result == False:
            # print(f"Found easy task: {assumptions}")
            easy.append(assumptions)

    return hard, easy


def determine_semieasy_tasks(solver, hard_tasks, num_confl=1000):
    semieasy = []

    for cube in hard_tasks:
        solver.conf_budget(num_confl)
        result = solver.solve_limited(cube)
        # 'result' is True if the problem is SAT
        # 'result' is False if the problem is UNSAT
        # 'result' is None if the solver could not prove UNSAT using a given budget
        if result == False:
            semieasy.append(cube)
        if result == True:
            raise ValueError("Unexpected SAT")

    return semieasy


def perform_probing(solver, variables, is_add_units=False) -> List[int]:
    """
    Performs failed literal probing.

    ### Usage:
    ```
    with Solver("g4", bootstrap_with=cnf) as solver:
        units = perform_probing(solver, variables)
    ```

    ### Returns:
        `List[int]`: A list of derived units. The negation of each unit is
        a literal whose substitution leads to a conflict via Unit Propagation.
    """

    units = set()

    for x in variables:
        for s in [False, True]:
            lit = signed(x, s)
            # if -lit in units:
            #     # Skip the already failed literal
            #     print(f"Skipping the already failed literal {lit} ({-lit} leads to a conflict)")
            #     raise ValueError("!")
            #     continue

            (result, _) = solver.propagate(assumptions=[lit])
            # 'result' is True if there is NO conflict
            # 'result' is False when there IS a conflict

            if result == False:
                units.add(-lit)

            if is_add_units:
                solver.add_clause([-lit])

    return sorted(units, key=abs)


def perform_probing_limited(solver, variables, num_confl=1000) -> List[int]:
    units = set()

    for x in variables:
        for s in [False, True]:
            lit = signed(x, s)
            solver.conf_budget(num_confl)
            result = solver.solve_limited(assumptions=[lit])
            # 'result' is True if the problem is SAT
            # 'result' is False if the problem is UNSAT
            # 'result' is None if the solver could not prove UNSAT using a given budget

            if result == False:
                units.add(-lit)
            if result == True:
                raise ValueError("Unexpected SAT")

    return sorted(units, key=abs)


def cubes_to_dnf(variables, cubes):
    from pyeda.inter import exprvar, And, Or

    print(f"Converting {len(cubes)} cubes over {len(variables)} variables into DNF...")

    for cube in cubes:
        assert variables == [abs(lit) for lit in cube], f"cube={cube}, vars={variables}"

    var_map = dict()
    cubes_expr = []

    for cube in cubes:
        lits_expr = []
        for lit in cube:
            var = abs(lit)
            if var not in var_map:
                var_map[var] = exprvar("x", var)
            if lit < 0:
                lits_expr.append(~var_map[var])
            else:
                lits_expr.append(var_map[var])
        cubes_expr.append(And(*lits_expr))

    dnf = Or(*cubes_expr)
    assert dnf.is_dnf()
    return dnf


def minimize_dnf(dnf):
    from pyeda.inter import espresso_exprs

    print(f"Minimizing DNF via Espresso...")
    min_dnf = espresso_exprs(dnf)
    return min_dnf


def cnf_to_clauses(cnf):
    print("Converting CNF into clauses...")

    assert cnf.is_cnf()

    litmap, nvars, clauses = cnf.encode_cnf()
    result = []
    for clause in clauses:
        c = []
        for lit in clause:
            v = litmap[abs(lit)].indices[0]  # 1-based variable index
            s = lit < 0  # sign
            c.append(signed(v, s))
        c.sort(key=lambda x: abs(x))
        result.append(c)

    clauses = result
    clauses.sort(key=lambda x: (len(x), tuple(map(abs, x))))
    print(
        f"Total {len(clauses)} clauses: {sum(1 for clause in clauses if len(clause) == 1)} units, {sum(1 for clause in clauses if len(clause) == 2)} binary, {sum(1 for clause in clauses if len(clause) == 3)} ternary, {sum(1 for clause in clauses if len(clause) > 3)} larger"
    )
    return clauses


def backdoor_to_clauses_via_easy(variables, easy):
    # Note: here, 'dnf' represents the negation of characteristic function,
    #       because we use "easy" tasks here.
    dnf = cubes_to_dnf(variables, easy)
    (min_dnf,) = minimize_dnf(dnf)
    min_cnf = (~min_dnf).to_cnf()  # here, we negate the function back
    clauses = cnf_to_clauses(min_cnf)
    return clauses


def backdoor_to_clauses_via_hard(variables, hard):
    dnf = cubes_to_dnf(variables, hard)
    (min_dnf,) = minimize_dnf(dnf)
    min_cnf = min_dnf.to_cnf()
    clauses = cnf_to_clauses(min_cnf)
    return clauses


def parse_binary_drat(path):
    def read_lit(file):
        lit = 0
        shift = 0
        while True:
            lc = file.read(1)
            if not lc:
                return
            lit |= (ord(lc) & 127) << shift
            shift += 7
            if ord(lc) <= 127:
                break

        if lit % 2:
            return -(lit >> 1)
        else:
            return lit >> 1

    with open_maybe_gzipped(path, "rb") as f:
        while True:
            b = f.read(1)

            # Handle EOF:
            if not b:
                return

            # Determine whether the clause was "added" or "deleted":
            if b == b"a":
                mode = "a"
            elif b == b"d":
                mode = "d"
            else:
                raise ValueError(f"Bad clause header: {mode}")

            # Read the clause:
            clause = []
            while True:
                lit = read_lit(f)
                if lit == 0:
                    # End of the clause
                    break
                elif lit is None:
                    raise ValueError("Could not read literal")
                else:
                    # Another literal in the clause
                    clause.append(lit)

            # Return the clause:
            yield (mode, clause)


def _parse_binary_drat_mmap(bs: Iterable[bytes]):
    state = 0
    # state = 0 -- reading the mode: b'a' or b'd'
    # state = 1 -- reading the clause
    mode = None  # "a" or "d", for user
    lit = 0
    shift = 0
    clause = []

    for b in bs:
        if state == 0:
            # Begin parsing a clause
            if b == b"a":
                mode = "a"
            elif b == b"d":
                mode = "d"
            else:
                raise ValueError(f"Bad clause header: {b}")
            clause = []
            lit = 0
            shift = 0
            state = 1

        elif state == 1:
            lit |= (ord(b) & 127) << shift
            shift += 7
            if ord(b) <= 127:
                # Finish parsing a literal
                if lit % 2:
                    lit = -(lit >> 1)
                else:
                    lit = lit >> 1

                if lit == 0:
                    # Finish parsing a clause
                    yield (mode, clause)
                    mode = None
                    state = 0
                else:
                    clause.append(lit)
                    # Reset parsing a literal
                    lit = 0
                    shift = 0

        else:
            raise ValueError(f"Bad state: {state}")


# @contextlib.contextmanager
# def parse_binary_drat_mmap(path):
#     with open(path, "rb") as f:
#         with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
#             yield _parse_binary_drat_mmap(mm)


@contextlib.contextmanager
def parse_binary_drat_mmap_tqdm(path: str):
    """
    A context manager that yields an object supporting
    lazy iteration over parsed data with tqdm progress.
    """

    class DratParserContext:
        def __init__(self, t):
            self.t = t

        def __iter__(self):
            return _parse_binary_drat_mmap(self.t)

    with open(path, "rb") as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            with tqdm.tqdm(mm) as t:
                yield DratParserContext(t)


def get_file_size(file):
    stat = os.stat(file.fileno())
    return stat.st_size


def open_maybe_gzipped(path, *args, **kwargs):
    is_gzip = False

    if path.endswith(".gz"):
        is_gzip = True
    # elif is_gz_file(path):
    #     is_gzip = True

    if is_gzip:
        return gzip.open(path, *args, **kwargs)
    else:
        return open(path, *args, **kwargs)


def is_gz_file(path):
    with open(path, "rb") as test_f:
        return test_f.read(2) == b"\x1f\x8b"
