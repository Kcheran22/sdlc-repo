import io
import json
import logging
import os
import uuid
from typing import Optional, List

import pdfplumber
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from utils.file_utils import (
    create_project_folder,
    get_project_folder,
    save_file
)

from graph import graph

# 🔥 Initialize FastAPI
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
app = FastAPI(title="Planner Agent API")
from fastapi.openapi.utils import get_openapi


def _extract_text(file_bytes: bytes, filename: str) -> str:
    if not filename:
        return ""
    
    filename_lower = filename.lower()
    
    if filename_lower.endswith(".pdf"):
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
            
    elif filename_lower.endswith(".docx"):
        import docx
        doc = docx.Document(io.BytesIO(file_bytes))
        return "\n".join(paragraph.text for paragraph in doc.paragraphs)
        
    return file_bytes.decode("utf-8", errors="replace")


def _run_agent(brd: str, frd: str, task_assignment: Optional[dict]) -> dict:
    initial_state = {
        "project_id": "temp-project",
        "project_name": "Epic Generation",
        "text_input": "",
        "file_paths": [],
        "transcripts": [],
        "combined_text": "",
        "cleaned_output": "",
        "brd": brd,
        "frd": frd,
        "brd_content": brd,
        "frd_content": frd,
        "task_assignment": task_assignment,
        "requirements": None,
        "epics": None,
        "stories_with_ac": None,
        "review_output": None,
        "current_step": "start",
        "step_outputs": [],
        "error": None,
    }
    result = graph.invoke(initial_state)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version="1.0.0",
        description="Fixed file upload schema",
        routes=app.routes,
    )

    try:
        # 🔥 FIX THE ACTUAL COMPONENT SCHEMA
        body_schema = schema["components"]["schemas"]["Body_upload_to_project_upload_to_project__post"]

        body_schema["properties"]["files"] = {
            "type": "array",
            "items": {
                "type": "string",
                "format": "binary"   # ✅ THIS FIXES SWAGGER
            }
        }

    except Exception as e:
        print("Schema fix error:", e)

    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi

 
# 🔹 Temporary in-memory store (replace with DB later)
PROJECTS = {}


# ===============================
# ✅ 1. CREATE PROJECT
# ===============================
@app.post("/create-project/")
def create_project(project_name: str):
    try:
        project_id = str(uuid.uuid4())

        folder_path = create_project_folder(project_name)

        PROJECTS[project_id] = {
            "project_name": project_name,
            "folder_path": folder_path
        }

        return {
            "project_id": project_id,
            "project_name": project_name,
            "message": "Project created successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===============================
# ✅ 2. UPLOAD + PROCESS
# ===============================
@app.post("/upload-to-project/")
async def upload_to_project(
    project_id: str = Form(...),
    text_input: Optional[str] = Form(None),
    files: List[UploadFile] = File(None)   # 🔥 MULTIPLE FILE SUPPORT
):
    try:
        # 🔹 Validate project
        if project_id not in PROJECTS:
            raise HTTPException(status_code=400, detail="Invalid project_id")

        project_name = PROJECTS[project_id]["project_name"]
        folder = get_project_folder(project_name)

        file_paths = []
        all_text = text_input or ""

        # 🔥 Process uploaded files
        if files:
            for file in files:
                path = save_file(file, folder)
                file_paths.append(path)

                # 🎙️ Audio → Transcription
                if file.content_type and file.content_type.startswith("audio"):
                    from services.transcription_service import transcribe_audio
                    transcript = transcribe_audio(path)
                    all_text += "\n" + transcript

                # 📄 Text files → Read content
                elif file.content_type and file.content_type.startswith("text"):
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        all_text += "\n" + f.read()

                # 📦 Other files (PDF, DOC, etc.)
                else:
                    all_text += f"\n[FILE: {file.filename}]"

        # 🔹 Prepare LangGraph state
        state = {
            "project_id": project_id,
            "project_name": project_name,
            "text_input": all_text,
            "file_paths": file_paths,
            "transcripts": [],
            "combined_text": "",
            "cleaned_output": "",
            "brd": "",
            "frd": ""
        }

        # 🔥 Run LangGraph pipeline
        result = graph.invoke(state)

        return {
            "project_id": project_id,
            "project_name": project_name,
            "cleaned_requirement": result.get("cleaned_output"),
            "brd": result.get("brd"),
            "frd": result.get("frd")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

 


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "SDLC Planner — Epic & Story Generator"}


class TextGenerateRequest(BaseModel):
    brd_content: Optional[str] = ""
    frd_content: Optional[str] = ""
    task_assignment: Optional[dict] = None


@app.post("/api/generate")
async def generate_from_text(body: TextGenerateRequest):
    """
    Generate epics & stories from raw BRD/FRD text.

    Pass `task_assignment` to hint the ownership model, e.g.:
    ```json
    { "development": "Agent", "testing": "Human", "deployment": "Human" }
    ```
    """
    result = _run_agent(body.brd_content, body.frd_content, body.task_assignment)
    return {
        "success": True,
        "data": result["review_output"],
        "step_outputs": result.get("step_outputs", []),
    }


@app.post("/api/generate-from-files")
async def generate_from_files(
    brd_file: Optional[UploadFile] = File(None, description="BRD document (.pdf or .txt)"),
    frd_file: Optional[UploadFile] = File(None, description="FRD document (.pdf or .txt)"),
    task_assignment: Optional[str] = Form(
        None, description='JSON string, e.g. {"development":"Agent"}'
    ),
):
    """Generate epics & stories from uploaded BRD / FRD files (PDF or TXT)."""
    brd_text = ""
    if brd_file and brd_file.filename:
        brd_bytes = await brd_file.read()
        brd_text = _extract_text(brd_bytes, brd_file.filename)
        
    frd_text = ""
    if frd_file and frd_file.filename:
        frd_bytes = await frd_file.read()
        frd_text = _extract_text(frd_bytes, frd_file.filename)

    task_assign_dict = json.loads(task_assignment) if task_assignment else None

    result = _run_agent(brd_text, frd_text, task_assign_dict)
    return {
        "success": True,
        "data": result["review_output"],
        "step_outputs": result.get("step_outputs", []),
    }



# ===============================
# ✅ 3. HEALTH CHECK
# ===============================
@app.get("/")
def health_check():
    return {"status": "Planner Agent API is running 🚀"}