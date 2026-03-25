# ============================================================
# nodes.py  —  All pipeline node functions
#
# Nodes are pure functions: receive PlannerState, mutate it,
# and return it. Grouped into two sections:
#
#   1. Upload Pipeline Nodes   (text/file → BRD/FRD → Databricks)
#   2. Epic & Story Nodes      (BRD/FRD → epics → stories → review)
# ============================================================

import json
import logging
import os

from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage

from state import PlannerState
from prompts import (
    PARSE_REQUIREMENTS_PROMPT,
    GROUP_INTO_EPICS_PROMPT,
    GENERATE_STORIES_PROMPT,
    ASSIGN_OWNER_PROMPT,
)
from services.transcription_service import transcribe_audio
from services.llm_service import clean_requirements
from services.databricks_service import save_to_databricks
from services.document_service import generate_brd, generate_frd

logger = logging.getLogger(__name__)


# ── LLM helper ───────────────────────────────────────────────────────────────

def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4o"), temperature=0.3)


def _call_llm(prompt: str) -> dict:
    """Invoke the LLM and robustly parse JSON output."""
    llm = _get_llm()
    raw = llm.invoke([HumanMessage(content=prompt)]).content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


# ════════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Upload Pipeline Nodes
# Flow: collect → audio → merge → clean → brd → frd → store
# ════════════════════════════════════════════════════════════════════════════════

def collect_inputs(state: PlannerState) -> PlannerState:
    """Pass-through — state already contains text_input and file_paths."""
    logger.info("▶ collect_inputs")
    return state


def process_audio(state: PlannerState) -> PlannerState:
    """Transcribe any audio files found in file_paths."""
    logger.info("▶ process_audio")
    transcripts = []
    for path in state.file_paths:
        if path.endswith(".mp3") or path.endswith(".wav"):
            transcripts.append(transcribe_audio(path))
    state.transcripts = transcripts
    return state


def merge_inputs(state: PlannerState) -> PlannerState:
    """Merge text_input and transcripts into a single combined_text."""
    logger.info("▶ merge_inputs")
    combined = state.text_input + "\n"
    for t in state.transcripts:
        combined += t + "\n"
    state.combined_text = combined
    return state


def clean_with_llm(state: PlannerState) -> PlannerState:
    """Use LLM to clean and structure the combined raw text."""
    logger.info("▶ clean_with_llm")
    state.cleaned_output = clean_requirements(state.combined_text)
    return state


def generate_brd_node(state: PlannerState) -> PlannerState:
    """Generate a Business Requirement Document from cleaned_output."""
    logger.info("▶ generate_brd")
    state.brd = generate_brd(state.cleaned_output)
    return state


def generate_frd_node(state: PlannerState) -> PlannerState:
    """Generate a Functional Requirement Document from cleaned_output."""
    logger.info("▶ generate_frd")
    state.frd = generate_frd(state.cleaned_output)
    return state


def store_in_databricks_node(state: PlannerState) -> PlannerState:
    """Persist project data (cleaned req, BRD, FRD) to Databricks."""
    logger.info("▶ store_in_databricks")
    save_to_databricks(
        state.project_id,
        state.project_name,
        state.cleaned_output,
        state.brd,
        state.frd,
    )
    return state


# ════════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Epic & Story Pipeline Nodes
# Flow: parse_documents → group_into_epics → generate_stories
#        → assign_execution_owner → prepare_review
# ════════════════════════════════════════════════════════════════════════════════

def parse_documents_node(state: PlannerState) -> PlannerState:
    """Extract structured requirements from BRD + FRD."""
    logger.info("▶ parse_documents")
    try:
        brd = state.brd or state.brd_content or ""
        frd = state.frd or state.frd_content or ""
        result = _call_llm(
            PARSE_REQUIREMENTS_PROMPT.format(brd_content=brd, frd_content=frd)
        )
        state.requirements = result["requirements"]
        state.current_step = "parse_documents"
        state.step_outputs.append({
            "step":  "parse_documents",
            "label": "Requirements Extracted",
            "count": len(state.requirements),
        })
    except Exception as exc:
        logger.error("parse_documents failed: %s", exc)
        state.error = str(exc)
    return state


def group_into_epics_node(state: PlannerState) -> PlannerState:
    """Group requirements into logical epics."""
    logger.info("▶ group_into_epics")
    try:
        result = _call_llm(
            GROUP_INTO_EPICS_PROMPT.format(
                requirements=json.dumps(state.requirements, indent=2)
            )
        )
        state.epics = result["epics"]
        state.current_step = "group_into_epics"
        state.step_outputs.append({
            "step":  "group_into_epics",
            "label": "Epics Created",
            "count": len(state.epics),
        })
    except Exception as exc:
        logger.error("group_into_epics failed: %s", exc)
        state.error = str(exc)
    return state


def generate_stories_node(state: PlannerState) -> PlannerState:
    """Generate user stories for every epic."""
    logger.info("▶ generate_stories")
    try:
        req_lookup  = {r["id"]: r for r in (state.requirements or [])}
        all_stories = []

        for epic in state.epics:
            related_reqs = [
                req_lookup[rid]
                for rid in epic.get("source_requirements", [])
                if rid in req_lookup
            ]
            result = _call_llm(
                GENERATE_STORIES_PROMPT.format(
                    epic=json.dumps(epic, indent=2),
                    epic_id=epic["id"],
                    requirements=json.dumps(related_reqs, indent=2),
                )
            )
            all_stories.extend(result.get("stories", []))

        state.stories_with_ac = all_stories
        state.current_step    = "generate_stories"
        state.step_outputs.append({
            "step":  "generate_stories",
            "label": "User Stories Generated",
            "count": len(all_stories),
        })
    except Exception as exc:
        logger.error("generate_stories failed: %s", exc)
        state.error = str(exc)
    return state


def assign_execution_owner_node(state: PlannerState) -> PlannerState:
    """Map each story to Human / Agent / Hybrid execution owner."""
    logger.info("▶ assign_execution_owner")
    try:
        task_assignment = state.task_assignment or {
            "development": "Hybrid",
            "testing":     "Hybrid",
            "deployment":  "Human",
        }
        stories = state.stories_with_ac or []
        result  = _call_llm(
            ASSIGN_OWNER_PROMPT.format(
                task_assignment=json.dumps(task_assignment, indent=2),
                stories=json.dumps(stories, indent=2),
            )
        )
        assign_lookup = {a["story_id"]: a for a in result.get("assignments", [])}

        updated = []
        for story in stories:
            assignment = assign_lookup.get(story["id"], {})
            updated.append({
                **story,
                "execution_owner":       assignment.get("execution_owner", "Human"),
                "executor_role":         assignment.get("executor_role", "Developer"),
                "assignment_rationale":  assignment.get("rationale", ""),
                "automation_percentage": assignment.get("automation_percentage", 0),
            })

        state.stories_with_ac = updated
        state.current_step    = "assign_execution_owner"
        state.step_outputs.append({
            "step":  "assign_execution_owner",
            "label": "Execution Owners Assigned",
            "count": len(updated),
        })
    except Exception as exc:
        logger.error("assign_execution_owner failed: %s", exc)
        state.error = str(exc)
    return state


def prepare_review_node(state: PlannerState) -> PlannerState:
    """Assemble the final BA / PM review package."""
    logger.info("▶ prepare_review")
    try:
        stories   = state.stories_with_ac or []
        epic_map  = {e["id"]: {**e, "stories": []} for e in (state.epics or [])}

        for story in stories:
            eid = story.get("epic_id", "")
            if eid in epic_map:
                epic_map[eid]["stories"].append(story)

        total_points = sum(s.get("story_points", 0) for s in stories)
        owner_counts = {"Human": 0, "Agent": 0, "Hybrid": 0}
        for s in stories:
            key = s.get("execution_owner", "Human")
            owner_counts[key] = owner_counts.get(key, 0) + 1

        state.review_output = {
            "summary": {
                "total_requirements":  len(state.requirements or []),
                "total_epics":         len(state.epics or []),
                "total_stories":       len(stories),
                "total_story_points":  total_points,
                "execution_breakdown": owner_counts,
            },
            "epics": list(epic_map.values()),
        }
        state.current_step = "prepare_review"
        state.step_outputs.append({
            "step":  "prepare_review",
            "label": "Review Package Ready",
            "count": len(stories),
        })
    except Exception as exc:
        logger.error("prepare_review failed: %s", exc)
        state.error = str(exc)
    return state
