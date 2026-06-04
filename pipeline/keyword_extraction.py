import logging
from llm.llm_models import async_llm_chain_call
from pipeline.utils import node_decorator
from pipeline.pipeline_manager import PipelineManager
from typing import Dict, List, Any

@node_decorator(check_schema_status=False)
def keyword_extraction(task: Any, tentative_schema: Dict[str, Any], execution_history: Dict[str, Any]) -> Dict[str, List[str]]:
    request_kwargs = {
        "HINT": task.evidence,
        "QUESTION": task.question
    }

    logging.info("Fetching engine, prompt and parser")
    engine, prompt, parser = PipelineManager().get_engine_prompt_parser()
    logging.info("Initiating asynchronous LLM chain call for keyword extraction")
    response = async_llm_chain_call( 
        engine=engine,
        prompt=prompt,
        parser=parser,
        request_list=[request_kwargs],
        step="keyword_extraction",
        sampling_count=1
    )[0]
    keywords = response[0]
    result = {"keywords": keywords}
    logging.info(f"Keywords extracted: {keywords}")
    
    return result
