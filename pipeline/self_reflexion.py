import logging
import time
from run_manager.logger import Logger
from run_manager.memory import Memory
from llm.llm_models import async_llm_chain_call
from database_utils.database_manager import DatabaseManager
from pipeline.pipeline_manager import PipelineManager
from pipeline.utils import node_decorator, get_last_node_result
from func_timeout import func_timeout, FunctionTimedOut
from typing import Dict, List, Any

MAX_REFLEXION_TIMES = 2

@node_decorator(check_schema_status=False)
def self_reflexion(task: Any, tentative_schema: Dict[str, Any], execution_history: Dict[str, Any]) -> str:
    """
    Self-reflection loop for SQL generation and evaluation.

    Args:
        task (Any): Task containing details like question and metadata.
        tentative_schema (Dict[str, Any]): Schema details for SQL generation.
        execution_history (Dict[str, Any]): Execution history, including generated SQL.

    Returns:
        str: Final SQL query that passes evaluation.
    """
    logging.info(f"LLM self reflexion start for question: {task.question_id}")

    if task.previous_sql is not None:
        first_time_sql = task.previous_sql
    else:
        first_time_sql = get_last_node_result(execution_history, "sql_generation")["SQL"]

    if first_time_sql is None:
        raise ValueError(f"Initial SQL generation is incomplete for task {task.question_id}. Self-reflexion cannot begin.")

    actor = Actor(task=task, tentative_schema=tentative_schema)
    evaluator = Evaluator(task=task, current_sql=first_time_sql)
    self_reflection = SelfReflection(task=task, tentative_schema=tentative_schema)

    current_sql = first_time_sql
    iteration_count = 1
    while iteration_count <= MAX_REFLEXION_TIMES:
        logging.info(f"Iteration {iteration_count}: Evaluating SQL")

        evaluation_result = evaluator.evaluate()

        if evaluation_result["judgment"] == "Valid":
            if iteration_count > 1:
                Memory().update_memory(incorrect_sql=actor.short_term_mems, correct_sql=current_sql, question=task.question)
            logging.info("SQL passed evaluation")
            return {"SQL": current_sql}
        
        logging.info("SQL failed evaluation. Generating feedback.")
        sql_error = evaluation_result["message"]
        current_sql_feedback = self_reflection.generate_feedback_mems(sql=current_sql, sql_error=sql_error)

        long_term_mems = Memory().get_exist_memory(current_sql_feedback)

        logging.info("Generating new SQL using actor.")
        actor.short_term_mems.append(current_sql)
        actor.check_mems_length()

        current_sql = actor.actor_generate_sql(long_term_mems)
        evaluator.sql = current_sql
        iteration_count += 1
    
    evaluation_result = evaluator.evaluate()
    if evaluation_result["judgment"] == "Valid":
        if iteration_count > 1:
            Memory().update_memory(incorrect_sql=actor.short_term_mems, correct_sql=current_sql, question=task.question)
        logging.info("SQL passed evaluation")
        return {"SQL": current_sql}

    logging.error("Max iterations reached. Could not generate a valid SQL query.")
    return {"SQL": current_sql}

class Actor:
    def __init__(self, task: Any, tentative_schema: Dict[str, Any]) -> None:
        self.short_term_mems: List[str] = []
        self.task = task
        self.tentative_schema = tentative_schema
    
    def actor_generate_sql(self, long_term_mems) -> str:
        logging.info(f"Actor start working for task: {self.task.question_id}")
        request_kwargs = {
            "QUESTION": self.task.question,
            "HINT": self.task.evidence
        }

        try:
            db_schema_string = DatabaseManager().get_database_schema_string(self.tentative_schema)
            engine, prompt, parser = PipelineManager().get_engine_prompt_parser(
                schema_string=db_schema_string, 
                long_term_mems=long_term_mems, 
                short_term_mems=self.short_term_mems
                )
            sampling_count = PipelineManager().self_reflexion.get("sampling_count", 1)
            response = async_llm_chain_call(
                engine=engine, 
                prompt=prompt, 
                parser=parser, 
                request_list=[request_kwargs], 
                step="actor_generate_sql", 
                sampling_count=sampling_count
                )[0]

            sqls = [res["SQL"] for res in response]
            sql = DatabaseManager().aggregate_sqls(sqls)

            result = next(res for res in response if res["SQL"] == sql)["SQL"]
            if result is None:
                raise ValueError("No valid SQL found in the response.")

            logging.info("Actor's work complete")
            return result
        except Exception as e:
            logging.error(f"Failed to generate SQL for task {self.task.question_id}: {e}")
            raise RuntimeError(f"Actor failed to generate SQL for task {self.task.question_id}.") from e
    
    def check_mems_length(self, max_mems_length: int = 5) -> None:
        if len(self.short_term_mems) > max_mems_length:
            self.short_term_mems.pop(0)

class Evaluator:
    def __init__(self, task: Any, current_sql: str) -> None:
        self.task = task
        self.sql = current_sql
    
    def evaluate(self, time_out: int = 30) -> Dict[str, Any]:
        logging.info(f"Evaluator start working for task: {self.task.question_id}")
        evaluate_result = {}

        if self.task.previous_sql is not None and self.sql == self.task.previous_sql:
            sql = self.task.previous_sql
            if sql == "SELECT * FROM table" or sql == "error":
                evaluate_result["judgment"] = "error"
                evaluate_result["message"] = "Previous experiments were unable to generate valid SQL statements"
                return evaluate_result

        try:
            execute_result = func_timeout(time_out, self.execute_current_sql)
        except FunctionTimedOut as e:
            evaluate_result["judgment"] = "error"
            evaluate_result["message"] = "SQL query execution time is too long."
            return evaluate_result
        except Exception as e:
            evaluate_result["judgment"] = "error"
            evaluate_result["message"] = str(e)
            return evaluate_result

        Logger().log_conversation(text=execute_result, _from="human", step="evaluate")

        if not execute_result or execute_result == []:
            evaluate_result["judgment"] = "error"
            evaluate_result["message"] = "SQL execution result is empty or None"
            return evaluate_result
        
        contains_valid_data = False
        for item in execute_result:
            # Check if any value in the tuple is not None
            if item is not None and any(val is not None for val in item):
                contains_valid_data = True
                break

        if contains_valid_data:
            evaluate_result["judgment"] = "Valid"
            evaluate_result["message"] = "SQL is valid"
        else:
            evaluate_result["judgment"] = "error"
            evaluate_result["message"] = "SQL execution result contains only None values"

        return evaluate_result

    def execute_current_sql(self) -> Any:
        try:
            current_sql_result = DatabaseManager().execute_sql(sql=self.sql, fetch="all")
            return current_sql_result
        except Exception as e:
            logging.error(f"Error executing SQL '{self.sql}': {e}")
            return {"result": str(e), "STATS": "ERROR"}

class SelfReflection:
    def __init__(self, task: Any, tentative_schema: Dict[str, Any]) -> None:
        self.task = task
        self.tentative_schema = tentative_schema
    
    def generate_feedback_mems(self, sql: str, sql_error: str) -> str:
        logging.info(f"SelfReflection start working for task: {self.task.question_id}")

        request_kwargs = {
            "SQL": sql,
            "QUESTION": self.task.question,
            "GUIDANCE": self.task.evidence
        }

        db_schema_string = DatabaseManager().get_database_schema_string(self.tentative_schema)
        engine, prompt, parser = PipelineManager().get_engine_prompt_parser(schema_string=db_schema_string, sql_error=sql_error)
        sampling_count = PipelineManager().self_reflexion.get("sampling_count", 1)
        response = async_llm_chain_call(
            engine=engine, 
            prompt=prompt, 
            parser=parser, 
            request_list=[request_kwargs], 
            step="Generate feedbacks", 
            sampling_count=sampling_count
            )[0]
        
        if not response or not isinstance(response[0], dict) or "feedback" not in response[0]:
            logging.error("Invalid response from async_llm_chain_call. Missing 'feedback'.")
            raise ValueError("Response from LLM does not contain 'feedback'.")

        feedback_dict = response[0]
        feedback = feedback_dict["feedback"]
        if not isinstance(feedback, str):
            logging.warning("Feedback is not a string. Converting to string format.")
            feedback = str(feedback)

        return feedback