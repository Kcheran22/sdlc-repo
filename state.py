from typing import TypedDict, List

class PlannerState(TypedDict):
    project_id: str
    project_name: str
    text_input: str
    file_paths: List[str]
    transcripts: List[str]
    combined_text: str
    cleaned_output: str