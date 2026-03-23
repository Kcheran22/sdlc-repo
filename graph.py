from langgraph.graph import StateGraph, START, END
from state import PlannerState

from services.transcription_service import transcribe_audio
from services.llm_service import clean_requirements
from services.databricks_service import save_to_databricks
from services.document_service import generate_brd, generate_frd
from services.jira_service import parse_documents_node, group_into_epics_node, generate_stories_node, generate_acceptance_criteria_node, assign_execution_owner_node, prepare_review_node
import json
import logging
import os
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage
 
 

logger = logging.getLogger(__name__)


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL", "gpt-4o"),
        temperature=0.3,
    )


def _call_llm(prompt: str) -> dict:
    """Invoke the LLM and parse JSON output robustly."""
    llm = _get_llm()
    raw = llm.invoke([HumanMessage(content=prompt)]).content.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


# 🔹 Node 1
def collect_inputs(state: PlannerState):
    return state


# 🔹 Node 2
def process_audio(state: PlannerState):
    transcripts = []

    for path in state["file_paths"]:
        if path.endswith(".mp3") or path.endswith(".wav"):
            text = transcribe_audio(path)
            transcripts.append(text)

    state["transcripts"] = transcripts
    return state


# 🔹 Node 3
def merge_inputs(state: PlannerState):
    combined = state.get("text_input", "") + "\n"

    for t in state.get("transcripts", []):
        combined += t + "\n"

    state["combined_text"] = combined
    return state


# 🔹 Node 4
def clean_with_llm(state: PlannerState):
    cleaned = clean_requirements(state["combined_text"])
    state["cleaned_output"] = cleaned
    return state


# 🔹 Node 5
def store_in_databricks(state: PlannerState):
    save_to_databricks(
        state["project_id"],
        state["project_name"],
        state["cleaned_output"],
        state["brd"],
        state["frd"]    
    )
    return state

def generate_brd_node(state):
    brd = generate_brd(state["cleaned_output"])
    state["brd"] = brd
    return state


def generate_frd_node(state):
    frd = generate_frd(state["cleaned_output"])
    state["frd"] = frd
    return state



# 🔥 Build Graph
builder = StateGraph(PlannerState)

builder.add_node("collect", collect_inputs)
builder.add_node("audio", process_audio)
builder.add_node("merge", merge_inputs)
builder.add_node("llm", clean_with_llm)
builder.add_node("store", store_in_databricks)
builder.add_node("brd_node", generate_brd_node)
builder.add_node("frd_node", generate_frd_node)
builder.add_node("parse_documents", parse_documents_node)
builder.add_node("group_into_epics", group_into_epics_node)
builder.add_node("generate_stories", generate_stories_node)
builder.add_node("generate_acceptance_criteria", generate_acceptance_criteria_node)
builder.add_node("assign_execution_owner", assign_execution_owner_node)
builder.add_node("prepare_review", prepare_review_node)

def route_start(state: PlannerState) -> str:
    # If we are given initial text or file paths, run the full pipeline
    if state.get("text_input") or state.get("file_paths"):
        return "collect"
    # If we are given BRD/FRD directly, skip straight to epic generation
    return "parse_documents"

def _has_error(state: PlannerState) -> str:
    return "error" if state.get("error") else "ok"

builder.add_conditional_edges(START, route_start, {"collect": "collect", "parse_documents": "parse_documents"})
builder.add_edge("collect", "audio")
builder.add_edge("audio", "merge")
builder.add_edge("merge", "llm")
builder.add_edge("llm", "brd_node")
builder.add_edge("brd_node", "frd_node")
builder.add_edge("frd_node", "store")
builder.add_edge("store", "parse_documents")

for src, dst in [
    ("parse_documents", "group_into_epics"),
    ("group_into_epics", "generate_stories"),
    ("generate_stories", "generate_acceptance_criteria"),
    ("generate_acceptance_criteria", "assign_execution_owner"),
    ("assign_execution_owner", "prepare_review"),
]:
    builder.add_conditional_edges(src, _has_error, {"ok": dst, "error": END})

builder.add_edge("prepare_review", END)

graph = builder.compile()