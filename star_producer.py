import glob
import os
import subprocess
from time import sleep

import click
import redis
import tqdm
import os

from config import REDIS_HOST, REDIS_PORT, REDIS_DECODE_RESPONSES

def get_redis_connection():
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=REDIS_DECODE_RESPONSES)


def parse_clause(clause_str: str):
    clause = clause_str.split()
    id_del = False
    if clause[0] == 'd':
        id_del = True
        clause = clause[1:]
    return id_del, list(map(int, clause[:-1]))


def get_learners_with_kissat_compatible(last_processed_learnt):
    con = get_redis_connection()
    value = con.get(f'from_kissat:{last_processed_learnt}')
    add_clauses = []
    delete_clauses = []
    read_learnt = 0
    while value is not None:
        id_del, clause = parse_clause(value)
        if id_del:
            delete_clauses.append(clause)
        else:
            add_clauses.append(clause)
        read_learnt += 1
        value = con.get(f'from_kissat:{last_processed_learnt + read_learnt}')
    con.close()
    return read_learnt, add_clauses, delete_clauses

def parse_clauses_with_assertion(line):
    clause_with_zero = line.split()
    assert clause_with_zero[-1] == '0'
    return clause_with_zero[:-1]

def get_learnts(last_processed_learnt, buffer_size):
    con = get_redis_connection()
    add_clauses = []
    delete_clauses = []
    read_learnt = 0

    pipe = con.pipeline()
    while True:
        for i in range(buffer_size):
            pipe.get(f'from_minisat:{last_processed_learnt + read_learnt + i}')
        result = pipe.execute()
        for i, clause in enumerate(result):
            if clause:
                add_clauses.append(parse_clauses_with_assertion(clause))
            else:
                con.close()
                return read_learnt + i, add_clauses, delete_clauses
        read_learnt += buffer_size




def read_original_clauses(path_cnf):
    from scripts.common import parse_backdoors
    return parse_backdoors(path_cnf)


def find_backdoors(path_tmp_dir,
                   combine_path_cnf,
                   ea_num_runs,
                   ea_seed,
                   ea_instance_size,
                   ea_num_iters):
    # Команда, которую вы хотите выполнить
    log_backdoor = os.path.join(path_tmp_dir, "log_backdoor-searcher_original.log")
    backdoor_path = os.path.join(path_tmp_dir, "backdoor_path.txt")

    if os.path.exists(backdoor_path):
        os.remove(backdoor_path)
        print(f"{backdoor_path} has been removed.")
    else:
        print(f"{backdoor_path} does not exist.")

    command = f"./backdoor-searcher/build/minisat {combine_path_cnf} -ea-num-runs={ea_num_runs} -ea-seed={ea_seed} -ea-instance-size={ea_instance_size} -ea-num-iters={ea_num_iters} -backdoor-path={backdoor_path} 2>&1 | tee {log_backdoor}"

    # Выполнение команды
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Дождитесь выполнения команды и получите выходные данные и ошибки
    stdout, stderr = process.communicate()

    # Вывод результатов выполнения команды
    print("Стандартный вывод:")
    print(stdout.decode())

    print("Стандартная ошибка:")
    print(stderr.decode())

    # Дождитесь завершения команды и получите код завершения
    return_code = process.wait()
    print(f"Код завершения: {return_code}")
    return backdoor_path


def combine(path_cnf, out_learnts_path, combine_path):
    command = f"cat {path_cnf} {out_learnts_path} > {combine_path}"
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()


def minimize(combine_path_cnf, backdoors_path, path_tmp_dir):
    derived_clauses = os.path.join(path_tmp_dir, "derived_original.txt")
    # вот тут бага так как pysat может быть не установлен на данный компиль
    command = f"python scripts/minimize.py --cnf {combine_path_cnf} --backdoors {backdoors_path} -o {derived_clauses}"
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    # Вывод результатов выполнения команды
    print("Стандартный вывод:")
    print(stdout.decode())

    print("Стандартная ошибка:")
    print(stderr.decode())

    return derived_clauses


def find_minimize_backdoors(path_cnf, out_learnts_path, path_tmp_dir,
                            ea_num_runs,
                            ea_seed,
                            ea_instance_size,
                            ea_num_iters):
    combine_path_cnf = os.path.join(path_tmp_dir, "combine.cnf")
    combine(path_cnf, out_learnts_path, combine_path_cnf)

    backdoors_path = find_backdoors(path_tmp_dir, combine_path_cnf, ea_num_runs,
                                    ea_seed,
                                    ea_instance_size,
                                    ea_num_iters)
    minimize_backdoors_path = minimize(combine_path_cnf, backdoors_path, path_tmp_dir)
    from util.DIMACS_parser import parse_cnf
    with open(minimize_backdoors_path, 'r') as file:
        clauses, _, _ = parse_cnf(file)
        return clauses


def save_backdoors(last_produced_clause, backdoors):
    con = get_redis_connection()
    for i, backdoor in enumerate(backdoors):
        key = f'to_minisat:{last_produced_clause + i}'
        value = " ".join(map(str, backdoor)) + " 0"
        con.set(key, value)
    con.close()


def save_in_drat_file(tmp_dir, learnts_file_name, learnts):
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)
    path_output = os.path.join(tmp_dir, learnts_file_name)
    if path_output:
        print(f"Writing {len(learnts)} extracted clauses to '{path_output}'...")
        with open(path_output, "w") as f:
            for clause in tqdm.tqdm(learnts):
                f.write(" ".join(map(str, clause)) + " 0\n")
    return path_output

def save_learnt(out_file, learnts):
    with open(out_file, "w") as out_file:
        for learnt in learnts:
            # if len(learnt) != 1:
            for c in learnt:
                out_file.write(c + " ")
            out_file.write("0\n")

def clean_tmp(path_tmp_dir):
    # Используйте glob.glob() для получения списка файлов в директории
    files = glob.glob(path_tmp_dir + '/*')

    # Пройдитесь по списку файлов и удалите их
    for file in files:
        try:
            os.remove(file)  # Удаление файла
            print(f'Файл {file} успешно удален')
        except Exception as e:
            print(f'Ошибка при удалении файла {file}: {e}')

def clean_redis():
    con = get_redis_connection()
    con.flushdb()
    con.close()

def check_clauses(clauses, lits, errmsg):
    for clause in clauses:
        id = False
        for c in clause:
            if int(c) in lits:
                id = True
                continue
        assert id, errmsg

print = click.echo

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"], max_content_width=999, show_default=True)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option("--cnf", "path_cnf", required=True, type=click.Path(exists=True), help="File with CNF")
@click.option("--tmp", "path_tmp_dir", required=True, type=click.Path(exists=False), help="Path temporary directory")
@click.option("--ea-num-runs", "ea_num_runs", default=2, show_default=True, type=int, help="Count backdoors")
@click.option("--ea-seed", "ea_seed", default=42, show_default=True, type=int, help="seed")
@click.option("--ea-instance-size", "ea_instance_size", default=10, show_default=True, type=int,
              help="Size of backdoor")
@click.option("--ea-num-iters", "ea_num_iters", default=2000, show_default=True, type=int,
              help="Count iteration for one backdoor")
@click.option("--validation", "validation", default=False, show_default=False, type=bool,
              help="Add validation before adding to redis. Only works for problems with solution 1 sat")
@click.option("--validation-sat-path", "validation_sat_path", default="validation_sat_cnf.txt", type=click.Path(exists=True), help="File with one sat solution")
@click.option("--buffer-size", "buffer_size", default=1000, show_default=True, type=int, help="redis buffer size")
def start_producer(path_cnf,
                   path_tmp_dir,
                   ea_num_runs,
                   ea_seed,
                   ea_instance_size,
                   ea_num_iters,
                   validation,
                   validation_sat_path,
                   buffer_size):
    last_processed_learnt = 0
    last_produced_clause = 0
    learnts = []
    if validation:
        with open(validation_sat_path, 'r') as file:
            lits = set(map(int, file.readline().split()))
    clean_tmp(path_tmp_dir)
    # clean_redis()
    while True:
        read_learnt, add_clauses, delete_clauses = get_learnts(last_processed_learnt, buffer_size)

        if validation:
            check_clauses(add_clauses, lits, "invalid claus from minisat")

        # save_learnt("validation_sat_cnf.txt", add_clauses)
        if len(add_clauses) == 0:
            sleep(10)
            continue
        # TODO в текущей реализации мы игнорируем удаленные клозы
        last_processed_learnt += read_learnt
        learnts.extend(add_clauses)
        out_learnts_path = save_in_drat_file(path_tmp_dir, "drat.txt", learnts)

        minimize_backdoors: list = find_minimize_backdoors(path_cnf, out_learnts_path, path_tmp_dir,
                                                           ea_num_runs,
                                                           ea_seed,
                                                           ea_instance_size,
                                                           ea_num_iters)
        save_backdoors(last_produced_clause, minimize_backdoors)
        print("save")
        last_produced_clause += len(minimize_backdoors)
        learnts.extend(minimize_backdoors)

        if validation:
            check_clauses(minimize_backdoors, lits, "invalid claus to minisat")


if __name__ == "__main__":

    # process = subprocess.Popen("which -a python", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # stdout, stderr = process.communicate()
    # print("------------------------------")
    # print(stdout)
    start_producer()