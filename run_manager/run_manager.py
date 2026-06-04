import os
import json
import logging
from pathlib import Path
from multiprocessing import Pool
from run_manager.logger import Logger
from run_manager.task import Task
from run_manager.memory import Memory
from run_manager.statistics_manager import StatisticsManager
from database_utils.database_manager import DatabaseManager
from pipeline.pipeline_manager import PipelineManager
from pipeline.workflow_builder import build_pipeline
from typing import Dict, List, Any, Tuple

class RunManager:
    RESULT_ROOT_PATH = "/opt/data/private/results"
    
    def __init__(self, args: Any):
        self.args = args
        self.tasks: List[Task] = []
        self.total_number_of_tasks = 0
        self.processed_tasks = 0

        self.result_directory = self.get_result_directory()
        self.statistics_manager = StatisticsManager(self.result_directory)
        self.memory = Memory(max_memory_count=self.args.max_memory_count)
        
    def get_result_directory(self) -> str:
        data_mode = self.args.data_mode
        pipeline_nodes = self.args.pipeline_nodes
        dataset_name = Path(self.args.data_path).stem
        run_folder_name = str(self.args.run_start_time)
        run_folder_path = Path(self.RESULT_ROOT_PATH) / data_mode / pipeline_nodes / dataset_name / run_folder_name
        
        run_folder_path.mkdir(parents=True, exist_ok=True)
        
        arg_file_path = run_folder_path / "-args.json"
        with arg_file_path.open('w') as file:
            json.dump(vars(self.args), file, indent=4)
        
        log_folder_path = run_folder_path / "logs"
        log_folder_path.mkdir(exist_ok=True)
        
        return str(run_folder_path)
    
    def initialize_tasks(self, dataset: List[Dict[str, Any]]):
        for i, data in enumerate(dataset):
            if "question_id" not in data:
                data = {"question_id": i, **data}
            task = Task(data, self.args.is_experiments)
            self.tasks.append(task)
        self.total_number_of_tasks = len(self.tasks)
        print(f"Total number of tasks: {self.total_number_of_tasks}")
    
    def run_tasks(self):
        for task in self.tasks:
            log = self.worker(task=task)
            self.task_done(log)
    
    def worker(self, task: Task) -> Tuple[Any, str, int]:
        database_manager = DatabaseManager(db_mode=self.args.data_mode, db_id=task.db_id)
        logger = Logger(db_id=task.db_id, question_id=task.question_id, result_directory=self.result_directory)
        logger.set_log_level(self.args.log_level)
        logger.log(f"Processing task: {task.db_id} {task.question_id}", "info")
        pipeline_manager = PipelineManager(json.loads(self.args.pipeline_setup))
        try:
            tentative_schema, execution_history = self.load_checkpoint(task.db_id, task.question_id)
            initial_state = {"keys": {"task": task, "tentative_schema": tentative_schema, "execution_history": execution_history}}
            self.compile = build_pipeline(self.args.pipeline_nodes)
            for state in self.compile.stream(initial_state):
                continue
            return state['__end__'], task.db_id, task.question_id
        except Exception as e:
            logger.log(f"Error processing task: {task.db_id} {task.question_id}\n{e}", "error")
            return None, task.db_id, task.question_id
    
    def task_done(self, log: Tuple[Any, str, int]):
        logging.info("One task is finished,start statistic")
        state, db_id, question_id = log
        if state is None:
            return
        evaluation_result = state["keys"]['execution_history'][-1]
        if evaluation_result.get("node_type") == "evaluation":
            for evaluation_for, result in evaluation_result.items():
                if evaluation_for in ['node_type', 'status']:
                    continue
                self.statistics_manager.update_stats(db_id, question_id, evaluation_for, result)
            self.statistics_manager.dump_statistics_to_file()
        self.processed_tasks += 1
        self.plot_progress()
    
    def plot_progress(self, bar_length: int = 100):
        processed_ratio = self.processed_tasks / self.total_number_of_tasks
        progress_length = int(processed_ratio * bar_length)
        print(f"[{'=' * progress_length}>{' ' * (bar_length - progress_length)}] {self.processed_tasks}/{self.total_number_of_tasks}")
    
    def generate_sql_files(self):
        logging.info("generating sql files for one task")
        sqls = {}
        for file in os.listdir(self.result_directory):
            if file.endswith(".json") and "_" in file:
                _index = file.find("_")
                question_id = int(file[:_index])
                db_id = file[_index + 1:-5]
                with open(os.path.join(self.result_directory, file), 'r') as f:
                    exec_history = json.load(f)
                    for step in exec_history:
                        if "SQL" in step:
                            node_type = step["node_type"]
                            if node_type not in sqls:
                                sqls[node_type] = {}
                            sqls[node_type][question_id] = step["SQL"]
        for key, value in sqls.items():
            with open(os.path.join(self.result_directory, f"-{key}.json"), 'w') as f:
                json.dump(value, f, indent=4)
    
    def load_checkpoint(self, db_id, question_id) -> Dict[str, List[str]]:
        tentative_schema = DatabaseManager().get_db_schema()
        execution_history = []

        return tentative_schema, execution_history