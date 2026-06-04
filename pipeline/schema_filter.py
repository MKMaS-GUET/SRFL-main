import difflib
import logging
from pipeline.utils import node_decorator, get_last_node_result
from database_utils.database_manager import DatabaseManager
from typing import Dict, List, Any

FILTER_THRESHOLD = 0.9

@node_decorator(check_schema_status=True)
def schema_filter(task: Any, tentative_schema: Dict[str, Any], execution_history: Dict[str, Any]) -> Dict[str, Any]:
    logging.info("Start schema filting")
    keywords = get_last_node_result(execution_history, "keyword_extraction")["keywords"]
    for keyword in keywords:
        potential_column_names = keyword_decomposition(keyword)
        all_schema = DatabaseManager().get_db_schema()
        relevant_schema = irrelevant_schema_filter(all_schema, potential_column_names)
        update_tentative_schema(tentative_schema, relevant_schema)

    result = {"tentative_schema": tentative_schema}
    logging.info("schema filter finish")

    return result

def irrelevant_schema_filter(schema: Dict[str, List[str]], potential_column_names: List[str]) -> Dict[str, List[str]]:
    result = {}
    for table_name, columns in schema.items():
        relevant_columns = []
        for column in columns:
            save_column = False
            for potential_column_name in potential_column_names:
                potential_column_name = potential_column_name.replace(" ", "").replace("_", "").rstrip("s")
                column = column.replace(" ", "").replace("_", "").rstrip("s")
                match_result = difflib.SequenceMatcher(None, column, potential_column_name).ratio()
                if match_result > FILTER_THRESHOLD:
                    save_column = True
            if save_column:
                relevant_columns.append(column)
        result[table_name] = relevant_columns
    
    return result

def update_tentative_schema(tentative_schema: Dict[str, List[str]], relevant_schema: Dict[str, List[str]]) -> None:
    for table_name, columns in relevant_schema.items():
        target_table_name = next((t for t in tentative_schema.keys() if t.lower() == table_name.lower()), None)
        if target_table_name:
            for column in columns:
                if column.lower() not in [c.lower() for c in tentative_schema[target_table_name]]:
                    tentative_schema[target_table_name].append(column)
        else:
            tentative_schema[table_name] = columns

def divied_by_equal_sign(keyword: str) -> str:
    if "=" in keyword:
        left_equal = keyword.find("=")
        column_part = keyword[:left_equal].strip()
        return column_part
    return None

def _extract_paranthesis(keyword: str) -> List[str]:
    paranthesis_matches = []
    open_paranthesis = []
    for i, char in enumerate(keyword):
        if char == "(":
            open_paranthesis.append(i)
        elif char == ")" and open_paranthesis:
            start = open_paranthesis.pop()
            found_string = keyword[start:i + 1]
            if found_string:
                paranthesis_matches.append(found_string)
    return paranthesis_matches
    
def keyword_decomposition(keyword: str) -> List[str]:
    potential_column_names = []
    keyword = keyword.strip()
    potential_column_names.append(keyword)

    _column = divied_by_equal_sign(keyword=keyword)
    if _column:
        potential_column_names.append(_column)

    potential_column_names.extend(_extract_paranthesis(keyword))

    if " " in keyword:
        potential_column_names.extend(part.strip() for part in keyword.split())

    return potential_column_names