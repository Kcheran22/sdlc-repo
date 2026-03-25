from typing import List, Optional
from pydantic import BaseModel, Field


class PlannerState(BaseModel):
    # ── Inputs ──────────────────────────────────────────────────────────────
    project_id:    str = ""
    project_name:  str = ""
    text_input:    str = ""
    file_paths:    List[str] = Field(default_factory=list)
    transcripts:   List[str] = Field(default_factory=list)
    combined_text: str = ""
    cleaned_output: str = ""
    brd:           str = ""
    frd:           str = ""
    brd_content:   Optional[str] = ""
    frd_content:   Optional[str] = ""
    task_assignment: Optional[dict] = None

    # ── Intermediate outputs ─────────────────────────────────────────────────
    requirements:   Optional[List[dict]] = None
    epics:          Optional[List[dict]] = None
    stories_with_ac: Optional[List[dict]] = None

    # ── Final output ─────────────────────────────────────────────────────────
    review_output: Optional[dict] = None

    # ── Metadata ─────────────────────────────────────────────────────────────
    current_step:  str = "start"
    step_outputs:  List[dict] = Field(default_factory=list)
    error:         Optional[str] = None