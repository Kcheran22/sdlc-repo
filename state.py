from typing import TypedDict, List, Optional, Annotated
import operator

class PlannerState(TypedDict):
    project_id: str
    project_name: str
    text_input: str
    file_paths: List[str]
    transcripts: List[str]
    combined_text: str
    cleaned_output: str
    brd: str
    frd: str
    brd_content: Optional[str]
    frd_content: Optional[str]
    task_assignment: Optional[dict]       # dev/test/deploy: Human | Agent | Hybrid

    # ── Intermediate pipeline outputs ───────────────────────────
    requirements: Optional[List[dict]]    # extracted from BRD + FRD
    epics: Optional[List[dict]]           # grouped requirement clusters
    stories_with_ac: Optional[List[dict]] # stories enriched with AC + assignments

    # ── Final output ────────────────────────────────────────────
    review_output: Optional[dict]         # structured for BA / PM review

    # ── Metadata ────────────────────────────────────────────────
    current_step: str
    step_outputs: Annotated[list, operator.add]  # accumulates per-node outputs
    error: Optional[str]

 


 