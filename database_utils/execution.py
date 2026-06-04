import sqlite3
import logging
import random
from func_timeout import func_timeout, FunctionTimedOut
from typing import Dict, List, Any, Union

def execute_sql(db_path: str, sql: str, fetch: Union[str, int] = "all") -> Any:
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            if fetch == "all":
                return cursor.fetchall()
            elif fetch == "one":
                return cursor.fetchone()
            elif fetch == "random":
                samples = cursor.fetchmany(10)
                return random.choice(samples) if samples else []
            elif isinstance(fetch, int):
                return cursor.fetchmany(fetch)
            else:
                raise ValueError("Invalid fetch argument. Must be 'all', 'one', 'random', or an integer.")
    except Exception as e:
        logging.error(f"Error in execute_sql: {e}\nSQL: {sql}")
        raise e

def get_sql_result(db_path: str, sql: str, max_returned_rows: int = 30) -> Dict[str, Any]:
    try:
        result = func_timeout(30, execute_sql, args=(db_path, sql, max_returned_rows))
        # result = execute_sql(db_path=db_path, sql=sql, fetch=max_returned_rows)
        return {"SQL": sql, "RESULT": result, "STATUS": "CORRECT"}
    except Exception as e:
        logging.error(f"Error in validate_sql_query: {e}")
        return {"SQL": sql, "RESULT": str(e), "STATUS": "ERROR"}
    except FunctionTimedOut as e:
        logging.warning("Execution timed out")
        return {"SQL": sql, "RESULT": str(e), "STATUS": "ERROR"}

def aggregate_sqls(db_path: str, sqls: List[str]) -> str:
    results = [get_sql_result(db_path=db_path, sql=sql) for sql in sqls]
    aggregate_result = {}

    for result in results:
        if result['STATUS'] == 'CORRECT':
            key = frozenset(tuple(row) for row in result['RESULT'])
            if key in aggregate_result:
                aggregate_result[key].append(result['SQL'])
            else:
                aggregate_result[key] = [result['SQL']]
    
    if aggregate_result:
        largest_cluster = max(aggregate_result.values(), key=len, default=[])
        if largest_cluster:
            return min(largest_cluster, key=len)

def evaluate_sql(db_path: str, pred_sql: str, gold_sql: str, timeout: int=30) -> Dict[str, Union[int, str]]:
    pred_sql = pred_sql.replace('\n', ' ').replace('"', "'").strip("`.")
    try:
        result = func_timeout(timeout, compare_sql_execute_result, args=(db_path, pred_sql, gold_sql))
        error = "incorrect answer" if result == 0 else "--"
    except FunctionTimedOut as e:
        logging.warning("Comparison timed out.")
        error = "timeout"
        result = 0
    except Exception as e:
        logging.error(f"Error in compare_sqls: {e}")
        error = str(e)
        result = 0
    return {'result': result, 'error': error}

def compare_sql_execute_result(db_path: str, pred_sql: str, gold_sql: str) -> int:
    try:
        pred_result = execute_sql(db_path=db_path, sql=pred_sql)
        gold_result = execute_sql(db_path=db_path, sql=gold_sql)
        return int(set(pred_result) == set(gold_result))
    except Exception as e:
        logging.critical(f"Error comparing SQL outcomes: {e}")
        raise e