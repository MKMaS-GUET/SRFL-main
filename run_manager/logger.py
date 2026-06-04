import logging
import json
from pathlib import Path
from threading import Lock
from typing import Dict, List, Any, Union

class Logger:
    _instance = None
    _lock = Lock()
    
    def __new__(cls, db_id: str = None, question_id: str = None, result_directory: str = None):
        with cls._lock:
            if (db_id is not None) and (question_id is not None):
                cls._instance = super(Logger, cls).__new__(cls)
                cls._instance._init(db_id, question_id, result_directory)
            else:
                if cls._instance is None:
                    raise ValueError("Logger instance has not been initialized.")
            return cls._instance
    
    def _init(self, db_id: str, question_id: str, result_directory: str):
        self.db_id = db_id
        self.question_id = question_id
        self.result_directory = Path(result_directory)
    
    def set_log_level(self, log_level: str):
        log_level_attr = getattr(logging, log_level.upper(), None)
        if log_level_attr is None:
            raise ValueError(f"Invalid log level: {log_level}")
        logging.basicConfig(level=log_level_attr, format='%(levelname)s: %(message)s')
    
    def log(self, message: str, log_level: str = "info"):
        log_method = getattr(logging, log_level, None)
        if log_method is None:
            raise ValueError(f"Invalid log level: {log_level}")
        log_method(message)
    
    def log_conversation(self, text: Union[str, List[Any], Dict[str, Any], bool], _from: str, step: int):
        log_file_path = self.result_directory / "logs" / f"{self.question_id}_{self.db_id}.log"
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        with log_file_path.open("a") as file:
            file.write(f"############################## {_from} at step {step} ##############################\n\n")
            if isinstance(text, str):
                file.write(text)
            elif isinstance(text, (list, dict)):
                formatted_text = json.dumps(text, indent=4)
                file.write(formatted_text)
            elif isinstance(text, bool):
                file.write(str(text))
            file.write("\n\n")
    
    def dump_history_to_file(self, execution_history: List[Dict[str, Any]]):
        file_path = self.result_directory / f"{self.question_id}_{self.db_id}.json"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w") as file:
            json.dump(execution_history, file, indent=4)