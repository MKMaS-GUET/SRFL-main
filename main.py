import json
import re
import argparse
from datetime import datetime
from run_manager.run_manager import RunManager
from typing import Dict, List, Any

def args_parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('--data_mode', type=str, required=True)
    parser.add_argument('--data_path', type=str, required=True)
    parser.add_argument('--is_experiments', type=str, required=True)
    parser.add_argument('--pipeline_nodes', type=str, required=True)
    parser.add_argument('--pipeline_setup', type=str, required=True)
    parser.add_argument('--log_level', type=str, default='warning')
    parser.add_argument('--max_memory_count', type=int, default=10)
    args = parser.parse_args()
    args.run_start_time = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

    return args

def load_dataset(data_path: str) -> List[Dict[str, Any]]:
    with open(data_path, 'r') as file:
        dataset = json.load(file)
    return dataset

def load_experiments_dataset(data_path: str) -> List[Dict[str, Any]]:
    experiments_data_path = './results/self_reflexion_result.json'

    with open(data_path, 'r') as file:
        dataset = json.load(file)
    with open(experiments_data_path, 'r') as file:
        exper_set = json.load(file)
    
    def clean_previous_sql(sql_string: str) -> str:
        if r"\t----- bird -----\t" in sql_string:
            return re.split(r"\t----- bird -----\t", sql_string)[0]
        else:
            return sql_string

    for item in dataset:
        qid = str(item["question_id"])
        if qid in exper_set:
            cleaned_sql = clean_previous_sql(exper_set[qid])
            item["previous_sql"] = cleaned_sql
    
    return dataset

def main():
    args = args_parse()

    if args.is_experiments == "True":
        dataset = load_experiments_dataset(args.data_path)
    elif args.is_experiments == "False":
        dataset = load_dataset(args.data_path)

    runner = RunManager(args)
    runner.initialize_tasks(dataset)
    runner.run_tasks()
    runner.generate_sql_files()

if __name__ == '__main__':
    main()