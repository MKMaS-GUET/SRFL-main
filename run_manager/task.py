from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

@dataclass
class Task:
    question_id: int = field(init=False)
    db_id: str = field(init=False)
    question: str = field(init=False)
    evidence: str = field(init=False)
    SQL: Optional[str] = field(init=False, default=None)
    difficulty: Optional[str] = field(init=False, default=None)
    previous_sql: Optional[str] = field(init=False, default=None)

    def __init__(self, task_data: Dict[str, Any], is_experiments: str):
        self.question_id = task_data["question_id"]
        self.db_id = task_data["db_id"]
        self.question = task_data["question"]
        self.evidence = task_data["evidence"]
        self.SQL = task_data.get("SQL")
        self.difficulty = task_data.get("difficulty")
        if is_experiments == "True":
            self.previous_sql = task_data["previous_sql"]