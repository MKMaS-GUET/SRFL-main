import logging
import re
from database_utils.execution import execute_sql
from sqlglot.optimizer.qualify import qualify, exp
from sqlglot import parse_one
from typing import Dict, List, Any, Optional

#=================== Retrieves the schema of the database ===================#
def get_db_schema(db_path: str) -> Dict[str, List[str]]:
    try:
        table_names = get_tables_from_db(db_path)
        return {table_name: get_columns_from_table(table_name, db_path) for table_name in table_names}
    except Exception as e:
        logging.error(f"Error in get_db_schema: {e}")
        raise e

def get_tables_from_db(db_path: str) -> List[str]:
    try:
        raw_table_names = execute_sql(db_path, "SELECT name FROM sqlite_master WHERE type='table';")
        return [table[0].replace('\"', '').replace('`', '') for table in raw_table_names if table[0] != "sqlite_sequence"]
    except Exception as e:
        logging.error(f"Error in get_db_all_tables: {e}")
        raise e

def get_columns_from_table(table_name: str, db_path: str) -> List[str]:
    try:
        table_info_rows = execute_sql(db_path, f"PRAGMA table_info(`{table_name}`);")
        return [row[1].replace('\"', '').replace('`', '') for row in table_info_rows]
    except Exception as e:
        logging.error(f"Error in get_table_all_columns: {e}\nTable: {table_name}")
        raise e
    
#===================== Generate database schema string ======================#
def get_database_schema_string(db_path: str, tentative_schema: Dict[str, Any], ) -> str:
    all_schema = get_db_schema(db_path=db_path)
    original_schema_string = get_original_schema_string(schema=all_schema, db_path=db_path)

    filtered_ddl = {}
    for table_name, allowed_columns in tentative_schema.items():
        original_ddl = original_schema_string.get(table_name)
        if original_ddl:
            filtered_ddl[table_name] = _filter_column_definitions(original_ddl, allowed_columns)
    
    return "\n\n".join(filtered_ddl.values())

def get_original_schema_string(schema: Dict[str, List[str]], db_path: str) -> Dict[str, str]:
    original_schema_string = {}
    for table_name in schema.keys():
        result = execute_sql(db_path=db_path,
                                          sql=f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}';",
                                          fetch="one")
        table_schema_string = result[0] if isinstance(result, tuple) else result
        original_schema_string[table_name] = table_schema_string
    
    return original_schema_string

def _filter_column_definitions(ddl: str, allowed_columns: List[str]) -> str:
    create_table_match = re.match(r'CREATE TABLE "?`?([\w -]+)`?"?\s*\((.*)\)', ddl, re.DOTALL)
    if not create_table_match:
        return ddl
    
    table_name = create_table_match.group(1).strip()
    column_definitions = create_table_match.group(2).strip()
    filtered_columns = []

    for column_def in re.split(r',\s*(?![^()]*\))', column_definitions):
        column_def = column_def.strip()
        if column_def.startswith('`'):
            column_name = column_def.split('`')[1]
        elif column_def.startswith('"'):
            column_name = column_def.split('"')[1]
        else:
            column_name = column_def.split(' ')[0]

        if column_name in allowed_columns or any(
            keyword in column_def.lower() for keyword in ["primary key", "foreign key", "unique"]
        ):
            filtered_columns.append(column_def)
    
    new_column_definitions = ",\n  ".join(filtered_columns)
    return f"CREATE TABLE {table_name} (\n  {new_column_definitions}\n);"

#===================== retrieval columns throught sql =======================#
def get_sql_columns_dict(db_path: str, sql: str) -> Dict[str, List[str]]:
    sql = qualify(parse_one(sql, read='sqlite'), qualify_columns=True, validate_qualify_columns=False) if isinstance(sql, str) else sql
    columns_dict = {}

    sub_queries = [subq for subq in sql.find_all(exp.Subquery) if subq != sql]
    for sub_query in sub_queries:
        subq_columns_dict = get_sql_columns_dict(db_path, sub_query)
        for table, columns in subq_columns_dict.items():
            if table not in columns_dict:
                columns_dict[table] = columns
            else:
                columns_dict[table].extend([col for col in columns if col.lower() not in [c.lower() for c in columns_dict[table]]])

    for column in sql.find_all(exp.Column):
        column_name = column.name
        table_alias = column.table
        table = _get_table_with_alias(sql, table_alias) if table_alias else None
        table_name = table.name if table else None

        if not table_name:
            candidate_tables = [t for t in sql.find_all(exp.Table) if _get_main_parent(t) == _get_main_parent(column)]
            for candidate_table in candidate_tables:
                table_columns = get_columns_from_table(table_name=candidate_table.name, db_path=db_path)
                if column_name.lower() in [col.lower() for col in table_columns]:
                    table_name = candidate_table.name
                    break

        if table_name:
            if table_name not in columns_dict:
                columns_dict[table_name] = []
            if column_name.lower() not in [c.lower() for c in columns_dict[table_name]]:
                columns_dict[table_name].append(column_name)

    return columns_dict

def _get_table_with_alias(parsed_sql: exp.Expression, alias: str) -> Optional[exp.Table]:
    return next((table for table in parsed_sql.find_all(exp.Table) if table.alias == alias), None)

def _get_main_parent(expression: exp.Expression) -> Optional[exp.Expression]:
    parent = expression.parent
    while parent and not isinstance(parent, exp.Subquery):
        parent = parent.parent
    return parent

