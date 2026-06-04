import logging
import threading
import random
import time
import queue
from concurrent.futures import ThreadPoolExecutor
from langchain_core.exceptions import OutputParserException
from langchain.output_parsers import OutputFixingParser
from llm.configs import ENGINE_CONFIGS
from run_manager.logger import Logger
from typing import Dict, List, Any

def get_llm_chain(engine: str, temperature: float=0, base_uri: str=None) -> Any:
    if engine not in ENGINE_CONFIGS:
        raise ValueError(f"Engine {engine} not supported")
    config = ENGINE_CONFIGS[engine]
    constructor = config["constructor"]
    params = config["params"]
    if temperature:
        params["temperature"] = temperature
    if base_uri and "openai_api_base" in params:
        params["openai_api_base"] = f"{base_uri}/v1"
    model = constructor(**params)
    if "preprocess" in config:
        llm_chain = config["preprocess"] | model
    else:
        llm_chain = model
    return llm_chain

def async_llm_chain_call(engine, prompt, parser, request_list: List[Dict[str, Any]], step: str, sampling_count: int) -> List[List[Any]]:
    result_queue = queue.Queue()
    log_file_lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=len(request_list)*sampling_count) as executor:
        for request_id, request_kwargs in enumerate(request_list):
            for _ in range(sampling_count):
                executor.submit(threading_llm_call, request_id, engine, prompt, parser, request_kwargs, step, result_queue, log_file_lock)
                time.sleep(0.2)
    
    results = []
    while not result_queue.empty():
        results.append(result_queue.get())
    results = sorted(results, key=lambda x: x[0])
    sorted_results = [result[1] for result in results]
    grouped_results = [sorted_results[i * sampling_count: (i + 1) * sampling_count] for i in range(len(request_list))]
    return grouped_results

def threading_llm_call(request_id: int, engine, prompt, parser, request_kwargs: Dict[str, Any], step: str, result_queue: queue.Queue, log_file_lock: threading.Lock) -> None:
    try:
        result = call_llm_chain(engine, prompt, parser, request_kwargs, step, log_file_lock)
        result_queue.put((request_id, result))
    except Exception as e:
        logging.error(f"Exception in thread with request: {request_kwargs}\n{e}")
        result_queue.put((request_id, None)) 

def call_llm_chain(engine: Any, prompt: Any, parser: Any, request_kwargs: Dict[str, Any], step: str, log_file_lock: threading.Lock, max_attempts: int=2, backoff_base: int=2, jitter_max: int=60) -> Any:
    logger = Logger()
    for attempt in range(max_attempts):
        try:
            chain = prompt | engine | parser
            prompt_text = prompt.invoke(request_kwargs).messages[0].content
            output = chain.invoke(request_kwargs)
            with log_file_lock:
                logger.log_conversation(prompt_text, "Human", step)
                logger.log_conversation(output, "AI", step)
            return output
        except OutputParserException as e:
            new_parser = OutputFixingParser.from_llm(parser=parser, llm=engine)
            chain = prompt | engine | new_parser
            if attempt == max_attempts - 1:
                logger.log(f"call_chain: {e}", "error")
                raise e
        except Exception as e:
            if attempt < max_attempts - 1:
                logger.log(f"Failed to invoke the chain {attempt + 1} times.\n{type(e)}\n{e}", "warning")
                sleep_time = (backoff_base ** attempt) + random.uniform(0, jitter_max)
                time.sleep(sleep_time)
            else:
                logger.log(f"Failed to invoke the chain {attempt + 1} times.\n{type(e)} <{e}>\n", "error")
                raise e