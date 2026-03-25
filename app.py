# ============================================================
# app.py  —  FastAPI entry point for the SDLC Planner Agent
# ============================================================

# ── Standard library ─────────────────────────────────────────────────────────
import io
import json
import logging
import uuid
from typing import List, Optional

# ── Third-party ──────────────────────────────────────────────────────────────
import pdfplumber
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel

# ── Internal ─────────────────────────────────────────────────────────────────
from pipeline import pipeline
from state import PlannerState
from services.databricks_service import fetch_brd_frd_by_project_id
from utils.file_utils import create_project_folder, get_project_folder, save_file

# ── Bootstrap ────────────────────────────────────────────────────────────────
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="SDLC Planner Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory project store (replace with DB in production) ──────────────────
PROJECTS: dict = {}


# ── Swagger / OpenAPI fix for multi-file upload ───────────────────────────────
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    try:
        body = schema["components"]["schemas"]["Body_upload_to_project_upload_to_project__post"]
        body["properties"]["files"] = {
            "type": "array",
            "items": {"type": "string", "format": "binary"},
        }
    except KeyError:
        pass
    app.openapi_schema = schema
    return schema

app.openapi = custom_openapi


# ── Helper utilities ──────────────────────────────────────────────────────────

def _extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract plain text from PDF, DOCX, or raw text bytes."""
    if not filename:
        return ""
    name = filename.lower()
    if name.endswith(".pdf"):
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    if name.endswith(".docx"):
        import docx
        doc = docx.Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs)
    return file_bytes.decode("utf-8", errors="replace")


def _run_epic_agent(brd: str, frd: str, task_assignment: Optional[dict]) -> PlannerState:
    """Build a PlannerState from BRD/FRD text and run the epic generation pipeline."""
    state = PlannerState(
        brd=brd,
        frd=frd,
        brd_content=brd,
        frd_content=frd,
        task_assignment=task_assignment,
    )
    result = pipeline.run_epic_generation(state)
    if result.error:
        raise HTTPException(status_code=500, detail=result.error)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 1 — Health check
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def health_check():
    return {"status": "SDLC Planner API is running 🚀"}


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 2 — Create project
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/create-project/", tags=["Project"])
def create_project(project_name: str):
    """Create a new project and return its project_id."""
    try:
        project_id   = str(uuid.uuid4())
        folder_path  = create_project_folder(project_name)
        PROJECTS[project_id] = {"project_name": project_name, "folder_path": folder_path}
        return {
            "project_id":   project_id,
            "project_name": project_name,
            "message":      "Project created successfully",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 3 — Upload files → clean → generate BRD/FRD → store in Databricks
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/upload-to-project/", tags=["Project"])
async def upload_to_project(
    project_id: str = Form(...),
    text_input: Optional[str] = Form(None),
    files: List[UploadFile] = File(None),
):
    """
    Upload raw text or files (audio/text/PDF/DOCX) to a project.
    Runs: collect → transcribe → merge → clean → BRD → FRD → Databricks store.
    Does NOT run epic/story generation.
    """
    try:
        if project_id not in PROJECTS:
            raise HTTPException(status_code=400, detail="Invalid project_id")

        project_name = PROJECTS[project_id]["project_name"]
        folder       = get_project_folder(project_name)
        file_paths   = []
        all_text     = text_input or ""

        if files:
            for file in files:
                path = save_file(file, folder)
                file_paths.append(path)

                if file.content_type and file.content_type.startswith("audio"):
                    from services.transcription_service import transcribe_audio
                    all_text += "\n" + transcribe_audio(path)
                elif file.content_type and file.content_type.startswith("text"):
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        all_text += "\n" + f.read()
                else:
                    all_text += f"\n[FILE: {file.filename}]"

        state  = PlannerState(
            project_id=project_id,
            project_name=project_name,
            text_input=all_text,
            file_paths=file_paths,
        )
        result = pipeline.run_upload(state)

        return {
            "project_id":          project_id,
            "project_name":        project_name,
            "cleaned_requirement": result.cleaned_output,
            "brd":                 result.brd,
            "frd":                 result.frd,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 4 — Generate epics & stories from raw BRD/FRD text
# ─────────────────────────────────────────────────────────────────────────────
class EpicGenerateRequest(BaseModel):
    brd_content:     Optional[str] = ""
    frd_content:     Optional[str] = ""
    task_assignment: Optional[dict] = None


@app.post("/api/generate-epics-stories", tags=["Epic & Story Generation"])
async def generate_from_text(body: EpicGenerateRequest):
    """
    Generate epics & stories from raw BRD/FRD text.

    Pass `task_assignment` to hint ownership, e.g.:
    `{ "development": "Agent", "testing": "Human", "deployment": "Human" }`
    """
    result = _run_epic_agent(body.brd_content, body.frd_content, body.task_assignment)
    return {
        "success":      True,
        "data":         result.review_output,
        "step_outputs": result.step_outputs,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 5 — Generate epics & stories from uploaded BRD/FRD files
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/api/generate-epics-stories-from-files", tags=["Epic & Story Generation"])
async def generate_from_files(
    brd_file:        Optional[UploadFile] = File(None, description="BRD document (.pdf / .docx / .txt)"),
    frd_file:        Optional[UploadFile] = File(None, description="FRD document (.pdf / .docx / .txt)"),
    task_assignment: Optional[str]        = Form(None, description='JSON e.g. {"development":"Agent"}'),
):
    """Generate epics & stories from uploaded BRD / FRD files."""
    brd_text = ""
    if brd_file and brd_file.filename:
        brd_text = _extract_text(await brd_file.read(), brd_file.filename)

    frd_text = ""
    if frd_file and frd_file.filename:
        frd_text = _extract_text(await frd_file.read(), frd_file.filename)

    task_assign_dict = json.loads(task_assignment) if task_assignment else None
    result           = _run_epic_agent(brd_text, frd_text, task_assign_dict)

    return {
        "success":      True,
        "data":         result.review_output,
        "step_outputs": result.step_outputs,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 6 — Generate epics & stories from an existing Databricks project
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/api/generate-from-existing", tags=["Epic & Story Generation"])
async def generate_from_existing(
    project_id:      str,
    task_assignment: Optional[dict] = None,
):
    """
    Fetch BRD and FRD from the Databricks `projects` table by project_id,
    then run the Epic & Story Generation pipeline.
    """
    try:
        project_data = fetch_brd_frd_by_project_id(project_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    brd = project_data.get("brd", "")
    frd = project_data.get("frd", "")

    if not brd and not frd:
        raise HTTPException(
            status_code=422,
            detail=f"Project '{project_id}' found but BRD and FRD are both empty. "
                   "Run /upload-to-project/ first to generate them.",
        )

    result = _run_epic_agent(brd, frd, task_assignment)

    return {
        "success":      True,
        "project_id":   project_data["project_id"],
        "project_name": project_data["project_name"],
        "data":         result.review_output,
        "step_outputs": result.step_outputs,
    }