import logging
import re
from langchain_core.output_parsers.base import BaseOutputParser
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field
from typing import Dict, List, Any

class PythonListOutputParser(BaseOutputParser):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def parse(self, output: str) -> Any:
        logging.debug(f"Parsing output with PythonListOutputParser: {output}")
        if "```python" in output:
            output = output.split("```python")[1].split("```")[0]
        output = re.sub(r"^\s+", "", output)
        return eval(output)

class SQLGenerationOutputParser(BaseModel):
    chain_of_thought_reasoning: str = Field(description="Your thought process on how you arrived at the final SQL query.")
    SQL: str = Field(description="The generated SQL query in a single string.")

class SelfReflectionOutputParser(BaseModel):
    feedback: str = Field(description="Specific, actionable steps to modify the SQL query to align with the question's intent.")

class MemoryGenerationParser(BaseModel):
    step: str = Field(description="The step you must check when generating SQL statements.")

def get_llm_parser(parser_name: str):
    parser_configs = {
        "keyword_extraction": PythonListOutputParser,
        "sql_generation": lambda: JsonOutputParser(pydantic_object=SQLGenerationOutputParser),
        "actor_generate_sql": lambda: JsonOutputParser(pydantic_object=SQLGenerationOutputParser),
        "generate_feedback_mems": lambda: JsonOutputParser(pydantic_object=SelfReflectionOutputParser),
        "feedback_summarize": lambda: JsonOutputParser(pydantic_object=MemoryGenerationParser)
    }

    if parser_name not in parser_configs:
        logging.error(f"Invalid parser name: {parser_name}")
        raise ValueError(f"Invalid parser name: {parser_name}")
    
    logging.info(f"Retrieving parser for: {parser_name}")
    parser = parser_configs[parser_name]() if callable(parser_configs[parser_name]) else parser_configs[parser_name]
    return parser