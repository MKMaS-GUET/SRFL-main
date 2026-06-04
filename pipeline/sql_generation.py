import logging
from llm.llm_models import async_llm_chain_call
from pipeline.utils import node_decorator
from database_utils.database_manager import DatabaseManager
from pipeline.pipeline_manager import PipelineManager
from typing import Dict, List, Any

import json
import os
SQL_FILE_PATH="./results/ablation.json"

@node_decorator(check_schema_status=False)
def sql_generation(task: Any, tentative_schema: Dict[str, Any], execution_history: Dict[str, Any]) -> Dict[str, Any]:
    request_kwargs = {
        "QUESTION": task.question,
        "HINT": task.evidence
    }

    db_schema_string = DatabaseManager().get_database_schema_string(tentative_schema)

    logging.info("Fetching engine, prompt and parser")
    engine, prompt, parser = PipelineManager().get_engine_prompt_parser(schema_string=db_schema_string)

    sampling_count = PipelineManager().sql_generation.get("sampling_count", 1)
    response = async_llm_chain_call(
        engine=engine, 
        prompt=prompt, 
        parser=parser, 
        request_list=[request_kwargs], 
        step="sql_generate", 
        sampling_count=sampling_count
        )[0]

    sqls = [res["SQL"] for res in response]
    sql = DatabaseManager().aggregate_sqls(sqls)
    # save_sql_to_json(new_sql=sql, json_file_path=SQL_FILE_PATH, dataset_name=task.db_id)
    result = next(res for res in response if res["SQL"] == sql)

    logging.info("sql generation complete")
    return result

def save_sql_to_json(new_sql: str, json_file_path: str, dataset_name: str) -> None:
    """
    将新生成的SQL语句追加到JSON文件中
    
    参数:
        new_sql: 新生成的SQL语句
        json_file_path: JSON文件路径
        description: 可选的对SQL语句的描述
    """
    data: Dict[str, str] = {}

    if os.path.exists(json_file_path):
        try:
            with open(json_file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
        except json.JSONDecodeError:
            data = {}

    ''' 确定新条目的键（当前最大键值+1） '''
    max_key = -1
    for key in data.keys():
        try:
            key_num = int(key)
            if key_num > max_key:
                max_key = key_num
        except ValueError:
            continue
    
    new_key = str(max_key + 1)
    value = f"{new_sql}\t----- bird -----\t{dataset_name}"
    data[new_key] = value

    with open(json_file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)