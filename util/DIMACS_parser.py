def parse_cnf(file):
    clauses = []

    var = 0
    clause_size = 0
    lines = file.readlines()
    for line in lines:
        words = line.split()
        if words[0] == "p":
            var = int(words[2])
            clause_size = int(words[3])
        elif words[0] != "c":
            assert words[len(words) - 1] == '0'
            words = list(map(int, words))
            clauses.append(words[:-1])
    return clauses, var, clause_size


def parse_cs_cnf(file):
    clauses = []
    cardinality_constraints = []
    var = 0
    all_clause_size = 0
    clause_size = 0
    cardinality_constraint_size = 0
    lines = file.readlines()
    for line in lines:
        words = line.split()
        if words[0] == "p":
            var = int(words[2])
            all_clause_size = int(words[3])
        elif words[0] != "c":
            if words[len(words) - 1] == '0':
                words = list(map(int, words))
                clauses.append(words[:-1])
                clause_size += 1
            else:
                assert words[len(words) - 2] == "#"
                assert words[len(words) - 4] == ">=" or words[len(words) - 4] == "<="
                ref = int(words.pop(len(words) - 1))
                words.pop(len(words) - 1) # remove #
                b = int(words.pop(len(words) - 1)) # remove b
                op = words.pop(len(words) - 1) # remove >=
                words = list(map(int, words))
                if op == ">=":
                    cardinality_constraint = (words, max(b, 0), ref)
                else:
                    cardinality_constraint = (words, max(b + 1, 0), -ref)
                if cardinality_constraint[1] <= 0:
                    clauses.append([cardinality_constraint[2]])
                    clause_size += 1
                else:
                    cardinality_constraints.append(cardinality_constraint)
                    cardinality_constraint_size += 1
    assert all_clause_size == clause_size + cardinality_constraint_size
    return clauses, cardinality_constraints, var, clause_size, clause_size, cardinality_constraint_size
