from typing import TypedDict

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_mistralai import ChatMistralAI
from langgraph.graph import StateGraph, START, END
from pathlib import Path
import re

from prompts import (
    PLANNER_PROMPT,
    ARCHITECT_PROMPT,
    WORKER_PROMPT,
)


load_dotenv()


# ============================================================
# LLM
# ============================================================

llm = ChatMistralAI(
    model="mistral-large-latest",
    temperature=0,
)


# ============================================================
# PLANNER SCHEMAS
# ============================================================

class FilePlan(BaseModel):
    path: str = Field(
        description="Path of the file to be created."
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

    prompt = PLANNER_PROMPT.format(
        user_prompt=state["user_prompt"]
    )

    result = planner_llm.invoke(prompt)

    return {
        "plan": result
    }


# ============================================================
# ARCHITECT NODE
# ============================================================

def architect_node(state: AgentState):

    plan = state["plan"]

    prompt = ARCHITECT_PROMPT.format(
        plan=plan.model_dump_json(indent=2)
    )

    result = architect_llm.invoke(prompt)

    return {
        "architecture": result
    }


# ============================================================
# WORKER NODE
# ============================================================

def worker_node(state: AgentState):

    plan = state["plan"]
    architecture = state["architecture"]

    prompt = WORKER_PROMPT.format(
        user_prompt=state["user_prompt"],
        plan=plan.model_dump_json(indent=2),
        architecture=architecture.model_dump_json(indent=2),
    )

    result = worker_llm.invoke(prompt)

    return {
        "generated_project": result
    }



def create_project_files(project: GeneratedProject):

    project_dir = Path("generated_projects") / "generated-app"

    project_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    for file in project.files:

        file_path = project_dir / file.path

        file_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        file_path.write_text(
            file.content,
            encoding="utf-8"
        )

        print(f"Created: {file_path}")

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