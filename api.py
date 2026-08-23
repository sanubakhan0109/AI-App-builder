from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from graph import graph, create_project_files


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="AI App Builder API"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://ai-app-builder-frontend-ovkp.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# PREVIEW DIRECTORY
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

PREVIEW_DIR = BASE_DIR / "generated_projects" / "generated-app"

PREVIEW_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# PREVIEW
# ============================================================

app.mount(
    "/preview",
    StaticFiles(
        directory=str(PREVIEW_DIR),
        html=True
    ),
    name="preview"
)


# ============================================================
# REQUEST
# ============================================================

class GenerateRequest(BaseModel):
    prompt: str


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "message": "AI App Builder API is running"
    }


# ============================================================
# GENERATE
# ============================================================

@app.post("/generate")
def generate_app(request: GenerateRequest):

    result = graph.invoke(
        {
            "user_prompt": request.prompt,
            "plan": None,
            "architecture": None,
            "generated_project": None,
        }
    )

    project = result["generated_project"]

    # IMPORTANT:
    # Actually create the files on disk
    create_project_files(project)

    return {
        "files": [
            {
                "path": file.path,
                "content": file.content,
            }
            for file in project.files
        ]
    }