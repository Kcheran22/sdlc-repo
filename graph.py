from langgraph.graph import StateGraph, START, END
from state import PlannerState

from services.transcription_service import transcribe_audio
from services.llm_service import clean_requirements
from services.databricks_service import save_to_databricks
from services.document_service import generate_brd, generate_frd


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
builder.add_node("brd", generate_brd_node)
builder.add_node("frd", generate_frd_node)

builder.add_edge(START, "collect")
builder.add_edge("collect", "audio")
builder.add_edge("audio", "merge")
builder.add_edge("merge", "llm")
builder.add_edge("llm", "brd")
builder.add_edge("brd", "frd")
builder.add_edge("frd", "store")

graph = builder.compile()