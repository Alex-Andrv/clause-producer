import glob
import itertools
import os
import subprocess
from time import sleep

import click
import redis
import tqdm
import os
import shutil

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

    if process.returncode == 0:
        print("Find backdoors process was successful")
    else:
        raise Exception(f"There are exception during find backdoors files "
                        f"path_tmp_dir = {path_tmp_dir}, "
                        f"combine_path_cnf = {combine_path_cnf} "
                        f"ea_num_runs = {ea_num_runs} "
                        f"ea_seed = {ea_seed} "
                        f"ea_instance_size = {ea_instance_size} "
                        f"ea_num_iters = {ea_num_iters}: \n"
                        f"ERROR: {stderr.decode('utf-8')}"
                        f"STDOUT: {stdout.decode('utf-8')}")
    return backdoor_path


def combine(path_cnf, out_learnts_path, combine_path):
    command = f"cat {path_cnf} {out_learnts_path} > {combine_path}"
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if process.returncode == 0:
        print("The combination process was successful")
    else:
        raise Exception(f"There are exception during combination files path_cnf={path_cnf}, "
                        f"out_learnts_path={out_learnts_path}: \n"
                        f"ERROR: {stderr.decode('utf-8')}"
                        f"STDOUT: {stdout.decode('utf-8')}")


def minimize(combine_path_cnf, backdoors_path, path_tmp_dir, log_dir):
    derived_clauses = os.path.join(path_tmp_dir, "derived_original.txt")
    # вот тут бага так как pysat может быть не установлен на данный компиль
    command = f"python scripts/minimize.py --cnf {combine_path_cnf} --backdoors {backdoors_path} -o {derived_clauses}"
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if process.returncode == 0:
        with open(log_dir + "/minimize_strout", 'w') as minimize_stdout_file:
            minimize_stdout_file.write(stdout.decode('utf-8'))
        print("The minimize process was successful")
    else:
        raise Exception(f"There are exception during minimize files "
                        f"combine_path_cnf = {combine_path_cnf}, "
                        f"backdoors_path = {backdoors_path} "
                        f"path_tmp_dir = {path_tmp_dir}: \n"
                        f"ERROR: {stderr.decode('utf-8')}"
                        f"STDOUT: {stdout.decode('utf-8')}")

    return derived_clauses


def copy_to(file, to_dir):
    try:
        shutil.copy(file, to_dir)
        print(f"File '{file}' copied to '{to_dir}' successfully.")
    except FileNotFoundError as e:
        print(f"File '{file}' not found.")
        raise e
    except IsADirectoryError as e:
        print(f"'{to_dir}' is not a valid directory.")
        raise e
    except PermissionError as e:
        print(f"You don't have permission to copy to '{to_dir}'.")
        raise e
    except Exception as e:
        print(f"An error occurred: {e}")
        raise e


def find_minimize_backdoors(path_cnf, out_learnts_path, path_tmp_dir,
                            ea_num_runs,
                            ea_seed,
                            ea_instance_size,
                            ea_num_iters,
                            log_dir):
    combine_path_cnf = os.path.join(path_tmp_dir, "combine.cnf")
    combine(path_cnf, out_learnts_path, combine_path_cnf)

    backdoors_path = find_backdoors(path_tmp_dir, combine_path_cnf, ea_num_runs,
                                    ea_seed,
                                    ea_instance_size,
                                    ea_num_iters)

    copy_to(backdoors_path, log_dir)

    minimize_backdoors_path = minimize(combine_path_cnf, backdoors_path, path_tmp_dir, log_dir)

    copy_to(minimize_backdoors_path, log_dir)


    from util.DIMACS_parser import parse_cnf
    with open(minimize_backdoors_path, 'r') as minimize_file:
        minimize_clauses, _, _ = parse_cnf(minimize_file)
        return minimize_clauses


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
    if not os.path.exists(path_output):
        # Файл не существует, создаем его и записываем в него
        print(f"Writing {len(learnts)} extracted clauses to new file'{path_output}'...")
        with open(path_output, "w") as file:
            for clause in tqdm.tqdm(learnts):
                file.write(" ".join(map(str, clause)) + " 0\n")
    else:
        # Файл существует, дописываем в конец
        print(f"Writing {len(learnts)} extracted clauses to end file '{path_output}'...")
        with open(path_output, "a") as file:
            for clause in tqdm.tqdm(learnts):
                file.write(" ".join(map(str, clause)) + " 0\n")
    return path_output


def save_learnt(out_file, learnts):
    with open(out_file, "w") as out_file:
        for learnt in learnts:
            # if len(learnt) != 1:
            for c in learnt:
                out_file.write(c + " ")
            out_file.write("0\n")


def clean_dir(path_dir):
    # Используйте glob.glob() для получения списка файлов в директории
    files = glob.glob(path_dir + '/*')

    # Пройдитесь по списку файлов и удалите их
    for file in files:
        try:
            if os.path.isdir(file):
                shutil.rmtree(file)  # Удаление файла
            else:
                os.remove(file)
            print(f'The {file} has been successfully deleted')
        except Exception as e:
            print(f'Error when deleting file {file}: {e}')
            raise e


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


def _get_learnt_set(learnts, filter_function):
    return set(map(lambda learnt: tuple(sorted(learnt)), filter(filter_function, learnts)))


def _get_statistics(derived, learnts):
    units = _get_learnt_set(learnts, lambda learnt: len(learnt) == 1)
    binary = _get_learnt_set(learnts, lambda learnt: len(learnt) == 2)
    ternary = _get_learnt_set(learnts, lambda learnt: len(learnt) == 3)
    large = _get_learnt_set(learnts, lambda learnt: len(learnt) > 3)
    derived_units = _get_learnt_set(derived, lambda learnt: len(learnt) == 1)
    derived_binary = _get_learnt_set(derived, lambda learnt: len(learnt) == 2)
    derived_ternary = _get_learnt_set(derived, lambda learnt: len(learnt) == 3)
    derived_large = _get_learnt_set(derived, lambda learnt: len(learnt) > 3)

    return {
        "new_units": derived_units - units,
        "new_binary": derived_binary - binary,
        "new_ternary": derived_ternary - ternary,
        "new_large": derived_large - large,
    }


def save_statistics(minimize_clauses, learnts, add_clauses, log_dir):
    with open(log_dir + "/statistics", "w") as statistics_file:
        statistics_file.write(f"All minimized clause: {len(minimize_clauses)} \n")

        units = _get_learnt_set(minimize_clauses, lambda learnt: len(learnt) == 1)
        binary = _get_learnt_set(minimize_clauses, lambda learnt: len(learnt) == 2)
        ternary = _get_learnt_set(minimize_clauses, lambda learnt: len(learnt) == 3)
        large = _get_learnt_set(minimize_clauses, lambda learnt: len(learnt) > 3)
        split = {
            "new_units": units,
            "new_binary": binary,
            "new_ternary": ternary,
            "new_large": large,
        }
        for key, learnts_v in split.items():
            statistics_file.write(f"deriving {key} where {len(learnts_v)}: {learnts_v} \n")

        derived = _get_statistics(minimize_clauses, learnts)
        for key, learnts_v in derived.items():
            statistics_file.write(f"deriving unique {key} where {len(learnts_v)}: {learnts_v} \n")

        real_derived = _get_statistics(minimize_clauses, learnts + add_clauses)
        for key, learnts_v in real_derived.items():
            statistics_file.write(f"real deriving unique {key} where {len(learnts_v)}: {learnts_v} \n")



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
@click.option("--validation-sat-path", "validation_sat_path", default="validation_sat_cnf.txt",
              type=click.Path(exists=True), help="File with one sat solution")
@click.option("--buffer-size", "buffer_size", default=1000, show_default=True, type=int, help="redis buffer size")
@click.option("--root-log-dir", "root_log_dir", required=True, type=click.Path(exists=False),
              help="Path to the root log dir")
def start_producer(path_cnf,
                   path_tmp_dir,
                   ea_num_runs,
                   ea_seed,
                   ea_instance_size,
                   ea_num_iters,
                   validation,
                   validation_sat_path,
                   buffer_size,
                   root_log_dir):
    last_processed_learnt = 0
    last_produced_clause = 0
    learnts = []
    clean_dir(path_tmp_dir)
    clean_dir(root_log_dir)
    # clean_redis()
    read_learnt, add_clauses, delete_clauses = get_learnts(last_processed_learnt, buffer_size)
    for i in itertools.count():
        print(f'Iteration {i}: new learnts: {read_learnt}')
        log_dir = root_log_dir + f"/{i}"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        if len(add_clauses) == 0:
            print(f"Iteration {i}: no new learnts, sleep 10 seconds")
            sleep(10)
            continue
        # TODO в текущей реализации мы игнорируем удаленные клозы
        out_learnts_path = save_in_drat_file(path_tmp_dir, "drat.txt", add_clauses)
        learnts.extend(add_clauses)

        minimize_clauses = find_minimize_backdoors(path_cnf, out_learnts_path, path_tmp_dir,
                                                                     ea_num_runs,
                                                                     ea_seed,
                                                                     ea_instance_size,
                                                                     ea_num_iters,
                                                                     log_dir)

        save_backdoors(last_produced_clause, minimize_clauses)
        print(f"Iteration {i}: save backdoors")
        last_produced_clause += len(minimize_clauses)

        save_in_drat_file(path_tmp_dir, "drat.txt", minimize_clauses)

        last_processed_learnt += read_learnt
        read_learnt, add_clauses, delete_clauses = get_learnts(last_processed_learnt, buffer_size)
        # TODO make learnts set of tuple
        save_statistics(minimize_clauses, learnts, add_clauses, log_dir)

        learnts.extend(minimize_clauses)


if __name__ == "__main__":
    start_producer()
