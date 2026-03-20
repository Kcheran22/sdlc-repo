import os

BASE_DIR = "projects"


def create_project_folder(project_name: str):
    """
    Create a folder for the project
    """
    folder_path = os.path.join(BASE_DIR, project_name)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path


def get_project_folder(project_name: str):
    """
    Get existing project folder
    """
    folder_path = os.path.join(BASE_DIR, project_name)

    if not os.path.exists(folder_path):
        raise Exception("Project folder not found")

    return folder_path


def save_file(file, folder_path):
    """
    Save uploaded file
    """
    file_path = os.path.join(folder_path, file.filename)

    with open(file_path, "wb") as f:
        f.write(file.file.read())

    return file_path