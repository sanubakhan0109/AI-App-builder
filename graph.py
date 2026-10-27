import os
import time
import logging
import shutil
from typing import TypedDict
from pathlib import Path
import re

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END

from prompts import (
    PLANNER_PROMPT,
    ARCHITECT_PROMPT,
    WORKER_PROMPT,
)

logger = logging.getLogger("app_builder.graph")

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


# ============================================================
# LLM CONFIGURATION
# ============================================================

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    logger.warning("GOOGLE_API_KEY is not set in backend environment. Graph calls will fail until it is configured.")

model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

llm = ChatGoogleGenerativeAI(
    model=model_name,
    api_key=api_key or "MISSING_KEY",
    timeout=45,
    max_retries=1,
)


# ============================================================
# PLANNER SCHEMAS
# ============================================================

class FilePlan(BaseModel):
    path: str = Field(
        description="Path of the file to be created, e.g. index.html, styles.css, script.js."
    )

    purpose: str = Field(
        description="Purpose of the file."
    )


class Plan(BaseModel):
    name: str = Field(
        description="Name of the application."
    )

    description: str = Field(
        description="Description of the application."
    )

    techstack: list[str] = Field(
        description="Technology stack used by the application."
    )

    features: list[str] = Field(
        description="Features required by the application."
    )

    files: list[FilePlan] = Field(
        description="Files required to build the application."
    )


# ============================================================
# ARCHITECT SCHEMAS
# ============================================================

class ArchitectureFile(BaseModel):
    path: str = Field(
        description="Path of the file."
    )

    responsibility: str = Field(
        description="Main responsibility of this file."
    )

    components: list[str] = Field(
        description="Major components that need to be implemented."
    )

    implementation_steps: list[str] = Field(
        description="Detailed implementation steps for this file."
    )

    dependencies: list[str] = Field(
        description="Other project files this file interacts with."
    )


class Architecture(BaseModel):
    overview: str = Field(
        description="Overall architecture of the application."
    )

    files: list[ArchitectureFile] = Field(
        description="Detailed architecture for every project file."
    )


# ============================================================
# WORKER SCHEMAS
# ============================================================

class GeneratedFile(BaseModel):
    path: str = Field(
        description="Path where this file should be created."
    )

    content: str = Field(
        description="Complete source code or content of the file."
    )


class GeneratedProject(BaseModel):
    files: list[GeneratedFile] = Field(
        description="All files generated for the project."
    )


# ============================================================
# STRUCTURED LLMs
# ============================================================

planner_llm = llm.with_structured_output(Plan)

architect_llm = llm.with_structured_output(Architecture)

worker_llm = llm.with_structured_output(GeneratedProject)


# ============================================================
# LANGGRAPH STATE
# ============================================================

class AgentState(TypedDict):
    user_prompt: str
    plan: Plan | None
    architecture: Architecture | None
    generated_project: GeneratedProject | None


# ============================================================
# PLANNER NODE
# ============================================================

def planner_node(state: AgentState):
    user_prompt = state.get("user_prompt", "")
    preview = (user_prompt[:70] + "...") if len(user_prompt) > 70 else user_prompt
    logger.info("[Planner] Starting planning for prompt: %r", preview)
    start_time = time.perf_counter()

    try:
        prompt = PLANNER_PROMPT.format(
            user_prompt=user_prompt
        )
        result = planner_llm.invoke(prompt)
        elapsed = time.perf_counter() - start_time
        file_count = len(result.files) if result and hasattr(result, "files") else 0
        file_list = ", ".join(f.path for f in result.files) if file_count else "none"
        logger.info(
            "[Planner] Completed in %.2fs | App: %r | %d files planned: %s",
            elapsed,
            getattr(result, "name", "App"),
            file_count,
            file_list,
        )
        return {
            "plan": result
        }
    except Exception as exc:
        elapsed = time.perf_counter() - start_time
        logger.error(
            "[Planner] Failed after %.2fs (%s: %s)",
            elapsed,
            type(exc).__name__,
            str(exc),
        )
        raise


# ============================================================
# ARCHITECT NODE
# ============================================================

def architect_node(state: AgentState):
    plan = state.get("plan")
    if not plan:
        logger.error("[Architect] Cannot proceed: plan is missing from graph state.")
        raise ValueError("Planner output is missing from graph state.")

    logger.info("[Architect] Starting architecture blueprint for: %r", getattr(plan, "name", "App"))
    start_time = time.perf_counter()

    try:
        prompt = ARCHITECT_PROMPT.format(
            plan=plan.model_dump_json(indent=2)
        )
        result = architect_llm.invoke(prompt)
        elapsed = time.perf_counter() - start_time
        file_count = len(result.files) if result and hasattr(result, "files") else 0
        file_list = ", ".join(f.path for f in result.files) if file_count else "none"
        logger.info(
            "[Architect] Completed in %.2fs | %d files architected: %s",
            elapsed,
            file_count,
            file_list,
        )
        return {
            "architecture": result
        }
    except Exception as exc:
        elapsed = time.perf_counter() - start_time
        logger.error(
            "[Architect] Failed after %.2fs (%s: %s)",
            elapsed,
            type(exc).__name__,
            str(exc),
        )
        raise


# ============================================================
# WORKER NODE
# ============================================================

def worker_node(state: AgentState):
    plan = state.get("plan")
    architecture = state.get("architecture")
    user_prompt = state.get("user_prompt", "")

    if not architecture:
        logger.error("[Worker] Cannot proceed: architecture is missing from graph state.")
        raise ValueError("Architect output is missing from graph state.")

    file_count = len(architecture.files) if hasattr(architecture, "files") else 0
    file_list = ", ".join(f.path for f in architecture.files) if file_count else "none"
    logger.info(
        "[Worker] Starting code generation for %d files: %s",
        file_count,
        file_list,
    )
    start_time = time.perf_counter()

    try:
        prompt = WORKER_PROMPT.format(
            user_prompt=user_prompt,
            plan=plan.model_dump_json(indent=2) if plan else "{}",
            architecture=architecture.model_dump_json(indent=2),
        )
        result = worker_llm.invoke(prompt)
        elapsed = time.perf_counter() - start_time
        gen_count = len(result.files) if result and hasattr(result, "files") else 0
        gen_list = ", ".join(f.path for f in result.files) if gen_count else "none"
        logger.info(
            "[Worker] Completed in %.2fs | Generated %d files: %s",
            elapsed,
            gen_count,
            gen_list,
        )
        return {
            "generated_project": result
        }
    except Exception as exc:
        elapsed = time.perf_counter() - start_time
        logger.error(
            "[Worker] Failed after %.2fs (%s: %s)",
            elapsed,
            type(exc).__name__,
            str(exc),
        )
        raise



def create_project_files(project: GeneratedProject, target_dir: Path | None = None) -> Path:
    if target_dir is None:
        project_dir = BASE_DIR / "generated_projects" / "generated-app"
    else:
        project_dir = Path(target_dir)

    # Clean existing directory to remove obsolete files from previous generations
    if project_dir.exists():
        for item in project_dir.iterdir():
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            except Exception as cleanup_err:
                logger.warning("Could not delete old file %s: %s", item, cleanup_err)

    project_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    for file in project.files:
        norm_path = file.path.lstrip("/\\")
        file_path = project_dir / norm_path

        file_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        file_path.write_text(
            file.content,
            encoding="utf-8"
        )

        logger.info("[Files] Created: %s (%d bytes)", file_path, len(file.content))

    return project_dir

# ============================================================
# BUILD GRAPH
# ============================================================

builder = StateGraph(AgentState)


builder.add_node("planner", planner_node)

builder.add_node("architect", architect_node)

builder.add_node("worker", worker_node)


builder.add_edge(START, "planner")

builder.add_edge("planner", "architect")

builder.add_edge("architect", "worker")

builder.add_edge("worker", END)


graph = builder.compile()


# ============================================================
# TEST GRAPH
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    user_prompt = input(
        "\nWhat application do you want to create?\n> "
    )

    print("\n🚀 Starting AI application builder...\n")

    result = graph.invoke(
        {
            "user_prompt": user_prompt,
            "plan": None,
            "architecture": None,
            "generated_project": None,
        }
    )

    # --------------------------------------------------------
    # PLAN
    # --------------------------------------------------------

    plan = result["plan"]

    print("=" * 60)
    print("📋 PLANNER")
    print("=" * 60)

    print(f"\nName:\n{plan.name}")

    print(f"\nDescription:\n{plan.description}")

    print("\nTech Stack:")

    for tech in plan.techstack:
        print(f"  - {tech}")

    print("\nFeatures:")

    for feature in plan.features:
        print(f"  - {feature}")

    print("\nFiles:")

    for file in plan.files:
        print(f"  - {file.path}")
        print(f"    {file.purpose}")


    # --------------------------------------------------------
    # ARCHITECTURE
    # --------------------------------------------------------

    architecture = result["architecture"]

    print("\n")
    print("=" * 60)
    print("🏗️ ARCHITECT")
    print("=" * 60)

    print(f"\nOverview:\n{architecture.overview}")

    for file in architecture.files:

        print("\n" + "-" * 50)

        print(f"Path: {file.path}")

        print(f"\nResponsibility:")
        print(file.responsibility)

        print("\nComponents:")

        for component in file.components:
            print(f"  - {component}")

        print("\nImplementation Steps:")

        for step in file.implementation_steps:
            print(f"  - {step}")

        print("\nDependencies:")

        for dependency in file.dependencies:
            print(f"  - {dependency}")


    # --------------------------------------------------------
    # WORKER
    # --------------------------------------------------------

  
    generated_project = result["generated_project"]

    print("\n")
    print("=" * 60)
    print("👷 WORKER")
    print("=" * 60)

    for file in generated_project.files:

        print(f"\nGenerated: {file.path}")

    # --------------------------------------------------------
    # CREATE ACTUAL FILES
    # --------------------------------------------------------

    print("\n")
    print("=" * 60)
    print("📁 CREATING PROJECT FILES")
    print("=" * 60)

    project_dir = create_project_files(generated_project)

    print(f"\n✅ Project created at: {project_dir}")