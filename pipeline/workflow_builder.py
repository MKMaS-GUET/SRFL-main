import logging
from langgraph.graph import END, StateGraph
from typing import Dict, TypedDict, Callable

from pipeline.keyword_extraction import keyword_extraction
from pipeline.schema_filter import schema_filter
from pipeline.sql_generation import sql_generation
from pipeline.self_reflexion import self_reflexion
from pipeline.evaluation import evaluation

class GraphState(TypedDict):
    keys: Dict[str, any]

class WorkflowBuilder:
    def __init__(self):
        self.workflow = StateGraph(GraphState)
        logging.info("Initialized WorkflowBuilder")
    
    def add_nodes(self, nodes: list) -> None:
        for node in nodes:
            if node in globals() and callable(globals()[node]):
                self.workflow.add_node(node, globals()[node])
                logging.info(f"Added node: {node}")
            else:
                logging.error(f"Node function '{node}' not found in global scope")
    
    def add_edges(self, edges: list) -> None:
        for node_from, node_to in edges:
            self.workflow.add_edge(node_from, node_to)
            logging.info(f"Added edge from {node_from} to {node_to}")
    
    def build(self, pipeline_nodes: str) -> None:
        nodes = pipeline_nodes.split("+")
        logging.info(f"Building workflow with nodes: {nodes}")
        self.add_nodes(nodes)
        self.workflow.set_entry_point(nodes[0])
        self.add_edges([(nodes[i], nodes[i+1]) for i in range(len(nodes) - 1)])
        self.add_edges([(nodes[-1], END)])
        logging.info("Workflow built successfully")

def build_pipeline(pipeline_nodes: str) -> Callable:
    workflow_builder = WorkflowBuilder()
    workflow_builder.build(pipeline_nodes)
    compile = workflow_builder.workflow.compile()
    logging.info("Pipeline built and compiled successfully")
    return compile