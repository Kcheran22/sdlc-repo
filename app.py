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
    files: List[UploadFile] = File(default=[])
):
    try:
        # 🔹 Validate project
        if project_id not in PROJECTS:
            raise HTTPException(status_code=400, detail="Invalid project_id")

        project_name = PROJECTS[project_id]["project_name"]
        folder = get_project_folder(project_name)

        file_paths = []

        # 🔹 Save files
        for file in files:
            path = save_file(file, folder)
            file_paths.append(path)

        # 🔹 Prepare LangGraph state
        state = {
            "project_id": project_id,
            "project_name": project_name,
            "text_input": text_input or "",
            "file_paths": file_paths,
            "transcripts": [],
            "combined_text": "",
            "cleaned_output": ""
        }

        # 🔥 Run LangGraph pipeline
        result = graph.invoke(state)

        return {
            "project_id": project_id,
            "project_name": project_name,
            "cleaned_requirement": result["cleaned_output"]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===============================
# ✅ 3. HEALTH CHECK (Optional)
# ===============================
@app.get("/")
def health_check():
    return {"status": "Planner Agent API is running 🚀"}