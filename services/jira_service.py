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
    GENERATE_AC_PROMPT,
    ASSIGN_OWNER_PROMPT,
)

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


# ── Node 1 ───────────────────────────────────────────────────────────────────
def parse_documents_node(state: PlannerState) -> dict:
    """Extract structured requirements from BRD + FRD."""
    logger.info("▶ parse_documents")
    try:
        result = _call_llm(
            PARSE_REQUIREMENTS_PROMPT.format(
                brd_content=state.get("brd", "") or state.get("brd_content", ""),
                frd_content=state.get("frd", "") or state.get("frd_content", ""),
            )
        )
        return {
            "requirements": result["requirements"],
            "current_step": "parse_documents",
            "step_outputs": [
                {
                    "step": "parse_documents",
                    "label": "Requirements Extracted",
                    "count": len(result["requirements"]),
                }
            ],
        }
    except Exception as exc:
        logger.error("parse_documents failed: %s", exc)
        return {"error": str(exc), "current_step": "parse_documents", "step_outputs": []}


# ── Node 2 ───────────────────────────────────────────────────────────────────
def group_into_epics_node(state: PlannerState) -> dict:
    """Group requirements into logical epics."""
    logger.info("▶ group_into_epics")
    try:
        result = _call_llm(
            GROUP_INTO_EPICS_PROMPT.format(
                requirements=json.dumps(state["requirements"], indent=2)
            )
        )
        return {
            "epics": result["epics"],
            "current_step": "group_into_epics",
            "step_outputs": [
                {
                    "step": "group_into_epics",
                    "label": "Epics Created",
                    "count": len(result["epics"]),
                }
            ],
        }
    except Exception as exc:
        logger.error("group_into_epics failed: %s", exc)
        return {"error": str(exc), "current_step": "group_into_epics", "step_outputs": []}


# ── Node 3 ───────────────────────────────────────────────────────────────────
def generate_stories_node(state: PlannerState) -> dict:
    """Generate user stories for every epic."""
    logger.info("▶ generate_stories")
    try:
        req_lookup = {r["id"]: r for r in (state["requirements"] or [])}
        all_stories_raw = []

        for epic in state["epics"]:
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
            all_stories_raw.extend(result.get("stories", []))

        # Wrap each story ready for AC enrichment
        stories_with_ac = [
            {"story": s, "acceptance_criteria": [], "definition_of_done": []}
            for s in all_stories_raw
        ]
        return {
            "stories_with_ac": stories_with_ac,
            "current_step": "generate_stories",
            "step_outputs": [
                {
                    "step": "generate_stories",
                    "label": "User Stories Generated",
                    "count": len(all_stories_raw),
                }
            ],
        }
    except Exception as exc:
        logger.error("generate_stories failed: %s", exc)
        return {"error": str(exc), "current_step": "generate_stories", "step_outputs": []}


# ── Node 4 ───────────────────────────────────────────────────────────────────
def generate_acceptance_criteria_node(state: PlannerState) -> dict:
    """Add acceptance criteria and definition of done to each story."""
    logger.info("▶ generate_acceptance_criteria")
    try:
        epic_lookup = {e["id"]: e for e in (state["epics"] or [])}
        updated = []

        for story_obj in state["stories_with_ac"]:
            story = story_obj["story"]
            epic = epic_lookup.get(story.get("epic_id"), {})
            result = _call_llm(
                GENERATE_AC_PROMPT.format(
                    story=json.dumps(story, indent=2),
                    epic=json.dumps(epic, indent=2),
                )
            )
            updated.append(
                {
                    **story_obj,
                    "acceptance_criteria": result.get("acceptance_criteria", []),
                    "definition_of_done": result.get("definition_of_done", []),
                }
            )

        return {
            "stories_with_ac": updated,
            "current_step": "generate_acceptance_criteria",
            "step_outputs": [
                {
                    "step": "generate_acceptance_criteria",
                    "label": "Acceptance Criteria Added",
                    "count": len(updated),
                }
            ],
        }
    except Exception as exc:
        logger.error("generate_acceptance_criteria failed: %s", exc)
        return {
            "error": str(exc),
            "current_step": "generate_acceptance_criteria",
            "step_outputs": [],
        }


# ── Node 5 ───────────────────────────────────────────────────────────────────
def assign_execution_owner_node(state: PlannerState) -> dict:
    """Map each story to Human / Agent / Hybrid execution owner."""
    logger.info("▶ assign_execution_owner")
    try:
        task_assignment = state.get("task_assignment") or {
            "development": "Hybrid",
            "testing": "Hybrid",
            "deployment": "Human",
        }
        result = _call_llm(
            ASSIGN_OWNER_PROMPT.format(
                task_assignment=json.dumps(task_assignment, indent=2),
                stories=json.dumps(
                    [s["story"] for s in state["stories_with_ac"]], indent=2
                ),
            )
        )
        assign_lookup = {a["story_id"]: a for a in result.get("assignments", [])}

        updated = []
        for story_obj in state["stories_with_ac"]:
            sid = story_obj["story"]["id"]
            assignment = assign_lookup.get(sid, {})
            updated.append(
                {
                    **story_obj,
                    "execution_owner": assignment.get("execution_owner", "Human"),
                    "executor_role": assignment.get("executor_role", "Developer"),
                    "assignment_rationale": assignment.get("rationale", ""),
                    "automation_percentage": assignment.get("automation_percentage", 0),
                }
            )

        return {
            "stories_with_ac": updated,
            "current_step": "assign_execution_owner",
            "step_outputs": [
                {
                    "step": "assign_execution_owner",
                    "label": "Execution Owners Assigned",
                    "count": len(updated),
                }
            ],
        }
    except Exception as exc:
        logger.error("assign_execution_owner failed: %s", exc)
        return {
            "error": str(exc),
            "current_step": "assign_execution_owner",
            "step_outputs": [],
        }


# ── Node 6 ───────────────────────────────────────────────────────────────────
def prepare_review_node(state: PlannerState) -> dict:
    """Assemble the final BA / PM review package."""
    logger.info("▶ prepare_review")
    try:
        # Build epic-centric view
        epic_map: dict = {e["id"]: {**e, "stories": []} for e in (state["epics"] or [])}
        for story_obj in state["stories_with_ac"]:
            eid = story_obj["story"].get("epic_id", "")
            if eid in epic_map:
                epic_map[eid]["stories"].append(story_obj)

        # Summary stats
        stories = state["stories_with_ac"] or []
        total_points = sum(s["story"].get("story_points", 0) for s in stories)
        owner_counts = {"Human": 0, "Agent": 0, "Hybrid": 0}
        for s in stories:
            key = s.get("execution_owner", "Human")
            owner_counts[key] = owner_counts.get(key, 0) + 1

        review_output = {
            "summary": {
                "total_requirements": len(state["requirements"] or []),
                "total_epics": len(state["epics"] or []),
                "total_stories": len(stories),
                "total_story_points": total_points,
                "execution_breakdown": owner_counts,
            },
            "epics": list(epic_map.values()),
        }

        return {
            "review_output": review_output,
            "current_step": "prepare_review",
            "step_outputs": [
                {
                    "step": "prepare_review",
                    "label": "Review Package Ready",
                    "count": len(stories),
                }
            ],
        }
    except Exception as exc:
        logger.error("prepare_review failed: %s", exc)
        return {"error": str(exc), "current_step": "prepare_review", "step_outputs": []}
