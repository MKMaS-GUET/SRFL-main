import inspect
from threading import Lock
from llm.llm_models import get_llm_chain
from llm.llm_prompts import get_llm_prompt
from llm.llm_parsers import get_llm_parser
from typing import Dict, List, Any, Tuple

class PipelineManager:
    _instance = None
    _lock = Lock()

    def __new__(cls, pipeline_setup: Dict[str, Any] = None):
        if pipeline_setup is not None:
            with cls._lock:
                cls._instance = super(PipelineManager, cls).__new__(cls)
                cls._instance.pipeline_setup = pipeline_setup
                cls._instance._init(pipeline_setup)
        elif cls._instance is None:
            raise ValueError("pipeline_setup dictionary must be provided for initialization")
        return cls._instance
    
    def _init(self, pipeline_setup: Dict[str, Any]):
        self.keyword_extraction = pipeline_setup.get("keyword_extraction", {})
        self.schema_filter = pipeline_setup.get("schema_filter", {})
        self.sql_generation = pipeline_setup.get("sql_generation", {})
        self.self_reflexion = pipeline_setup.get("self_reflexion", {})
    
    def get_engine_prompt_parser(self, **kwargs: Any) -> Tuple[Any, Any, Any]:
        frame = inspect.currentframe()
        caller_frame = frame.f_back
        node_name = caller_frame.f_code.co_name
        
        if node_name == "evaluate" or node_name == "actor_generate_sql" or node_name == "generate_feedback_mems":
            node_setup = self.pipeline_setup.get("self_reflexion", {})
        else:
            node_setup = self.pipeline_setup.get(node_name, {})

        try:
            engine_name = node_setup["engine"]
        except KeyError:
            raise ValueError(f"Engine not specified for node {node_name}")
        
        temperature = node_setup.get("temperature", 0)
        base_uri = node_setup.get("base_uri", None)
        engine = get_llm_chain(engine_name, temperature, base_uri)

        if node_name == "sql_generation":
            engine_name = self.sql_generation.get("engine", None)
            if engine_name == "finetuned_nl2sql":
                template_name = "finetuned_candidate_generation"
                parser_name = "finetuned_candidate_generation"
            else:
                template_name = node_name
                parser_name = node_name
        else:
            template_name = node_name
            parser_name = node_name
        prompt = get_llm_prompt(template_name, **kwargs)
        parser = get_llm_parser(parser_name)

        return engine, prompt, parser