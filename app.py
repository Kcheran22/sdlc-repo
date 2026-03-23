from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from typing import List, Optional
import uuid

from utils.file_utils import (
    create_project_folder,
    get_project_folder,
    save_file
)

from graph import graph

# 🔥 Initialize FastAPI
app = FastAPI(title="Planner Agent API")
from fastapi.openapi.utils import get_openapi

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


# ===============================
# ✅ 3. HEALTH CHECK
# ===============================
@app.get("/")
def health_check():
    return {"status": "Planner Agent API is running 🚀"}