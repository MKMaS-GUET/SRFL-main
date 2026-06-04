import os
from threading import Lock
from pathlib import Path
from dotenv import load_dotenv
from database_utils.execution import *
from database_utils.utils import get_db_schema, get_database_schema_string, get_sql_columns_dict
from typing import Dict, List, Any, Callable

load_dotenv(override=True)
DB_ROOT_PATH=Path(os.getenv("DB_ROOT_PATH"))

class DatabaseManager:
    _instance = None
    _lock = Lock()

    def __new__(cls, db_mode=None, db_id=None):
        if (db_mode is not None) and (db_id is not None):
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(DatabaseManager, cls).__new__(cls)
                    cls._instance._init(db_mode, db_id)
                elif cls._instance.db_id != db_id:
                    cls._instance._init(db_mode, db_id)
                return cls._instance
        else:
            if cls._instance is None:
                raise ValueError("DatabaseManager instance has not been initialized yet.")
            return cls._instance
    
    def _init(self, db_mode: str, db_id: str):
        self.db_mode = db_mode
        self.db_id = db_id
        self.lsh = None
        self.minhashes = None
        self.vector_db = None
        self._set_paths()
    
    def _set_paths(self):
        self.db_path = DB_ROOT_PATH / f"{self.db_mode}_databases" / self.db_id / f"{self.db_id}.sqlite"
        self.db_directory_path = DB_ROOT_PATH / f"{self.db_mode}_databases" / self.db_id
    
    @classmethod
    def add_methods_to_class(cls, funcs: List[Callable]):
        for func in funcs:
            method = cls.with_db_path(func)
            setattr(cls, func.__name__, method)
    
    @staticmethod
    def with_db_path(func: Callable):
        def wrapper(self, *args, **kwargs):
            return func(self.db_path, *args, **kwargs)
        return wrapper

functions_to_add = [
    execute_sql,
    get_db_schema,
    get_database_schema_string,
    aggregate_sqls,
    evaluate_sql,
    get_sql_columns_dict,
    get_sql_result
]
DatabaseManager.add_methods_to_class(functions_to_add)