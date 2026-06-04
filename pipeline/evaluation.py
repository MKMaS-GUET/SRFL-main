import logging
from run_manager.logger import Logger
from database_utils.database_manager import DatabaseManager
from pipeline.utils import node_decorator, get_last_node_result
from typing import Dict, List, Any

@node_decorator(check_schema_status=False)
def evaluation(task: Any, tentative_schema: Dict[str, Any], execution_history: Dict[str, Any]) -> Dict[str, Any]:
    logging.info("Starting evaluation") 
    gold_sql = task.SQL
    if task.previous_sql is not None:
        pred_and_revision_sql = {
            "previous_result": {"node_type": "previous_result", "SQL": task.previous_sql, "status": "success"},
            # "self_reflexion": get_last_node_result(execution_history, "self_reflexion")
        }
    else:
        pred_and_revision_sql = {
            "sql_generation": get_last_node_result(execution_history, "sql_generation"),
            "self_reflexion": get_last_node_result(execution_history, "self_reflexion")
        }
    result = {}

    for node_name, node_result in pred_and_revision_sql.items():
        pred_sql = "--"
        evaluation_result = {}

        try:
            if node_result["status"] == "success":
                pred_sql = node_result["SQL"]
                if node_name == "previous_result":
                    if pred_sql == "SELECT * FROM table":
                        response = {
                            "result": 0,
                            "error": "incorrect SQL"
                        }
                    elif pred_sql == "error":
                        response = {
                            "result": 0,
                            "error": "Previous expreiment error"
                        }
                    else:
                        response = DatabaseManager().evaluate_sql(pred_sql, gold_sql)
                else:
                    response = DatabaseManager().evaluate_sql(pred_sql, gold_sql)

                evaluation_result.update({
                    "result": response["result"],
                    "error": response["error"]
                })
            else:
                evaluation_result.update({
                    "result": "error happends during generation or revision",
                    "error": node_result["error"]
                })
        except Exception as e:
            Logger().log(
                f"Node 'evaluate_sql': {task.db_id}_{task.question_id}\n{type(e)}: {e}\n",
                "error",
            )
            evaluation_result.update({
                "reuslt": "error",
                "error": str(e)
            })
        
        evaluation_result.update({
            "Question": task.question,
            "Evidence": task.evidence,
            "pred_sql": pred_sql,
            "gold_sql": gold_sql
        })
        result[node_name] = evaluation_result
    
    logging.info("Evaluation completed successfully")
    return result