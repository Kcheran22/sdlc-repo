# ============================================================
# graph.py  —  PlannerPipeline
#
# Imports all nodes from nodes.py and orchestrates them into
# two pipelines:
#   run_upload()          → Upload + BRD/FRD generation + Databricks store
#   run_epic_generation() → Epic & story generation from BRD/FRD
#   run()                 → Both pipelines end-to-end
# ============================================================

import logging

from state import PlannerState
from nodes import (
    # Upload pipeline nodes
    collect_inputs,
    process_audio,
    merge_inputs,
    clean_with_llm,
    generate_brd_node,
    generate_frd_node,
    store_in_databricks_node,
    # Epic & story pipeline nodes
    parse_documents_node,
    group_into_epics_node,
    generate_stories_node,
    assign_execution_owner_node,
    prepare_review_node,
)

logger = logging.getLogger(__name__)


class PlannerPipeline:
    """
    Sequential Pydantic-based pipeline.
    Each node receives a PlannerState, mutates it, and returns it.
    If any node sets state.error, the pipeline short-circuits.

    Methods
    -------
    run_upload(state)
        collect → audio → merge → clean → brd → frd → databricks
        Used by: POST /upload-to-project/

    run_epic_generation(state)
        parse_documents → group_into_epics → generate_stories
            → assign_execution_owner → prepare_review
        Used by: POST /api/generate-epics-stories
                 POST /api/generate-epics-stories-from-files
                 POST /api/generate-from-existing

    run(state)
        run_upload → run_epic_generation  (full end-to-end)
    """

    _upload_steps = [
        collect_inputs,
        process_audio,
        merge_inputs,
        clean_with_llm,
        generate_brd_node,
        generate_frd_node,
        store_in_databricks_node,
    ]

    _epic_steps = [
        parse_documents_node,
        group_into_epics_node,
        generate_stories_node,
        assign_execution_owner_node,
        prepare_review_node,
    ]

    def _run_steps(self, state: PlannerState, steps: list) -> PlannerState:
        for step in steps:
            state = step(state)
            if state.error:
                logger.error("Pipeline stopped at %s: %s", step.__name__, state.error)
                break
        return state

    def run_upload(self, state: PlannerState) -> PlannerState:
        """Upload pipeline only — does NOT run epic/story generation."""
        return self._run_steps(state, self._upload_steps)

    def run_epic_generation(self, state: PlannerState) -> PlannerState:
        """Epic & story generation only — requires brd/frd already in state."""
        return self._run_steps(state, self._epic_steps)

    def run(self, state: PlannerState) -> PlannerState:
        """Full end-to-end pipeline: upload first, then epic generation."""
        state = self.run_upload(state)
        if not state.error:
            state = self.run_epic_generation(state)
        return state


# Module-level singleton imported by app.py
pipeline = PlannerPipeline()