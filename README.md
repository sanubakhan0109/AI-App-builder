# AI App Builder

AI App Builder is an agentic AI application that turns a natural-language idea into a working web application.

The user describes what they want to build, and the system plans the application, designs its architecture, generates the code, creates the project files, and provides a preview of the generated application.

## How It Works

The system uses three AI agents connected through LangGraph:

User Prompt → Planner → Architect → Worker → Generated Files → Preview

### Planner

The Planner understands the user's request and creates a structured development plan.

It determines:

- Application name
- Application description
- Technology stack
- Required features
- Required files
- Purpose of each file

For example, a request such as:

"Create a todo app"

can produce a plan containing:

- index.html
- styles.css
- script.js
- README.md

### Architect

The Architect receives the Planner's output and creates a detailed implementation blueprint.

It defines:

- Responsibility of each file
- Components required in each file
- Implementation steps
- Dependencies between files

The Architect does not generate the actual source code. It provides the Worker with a clear implementation plan.

### Worker

The Worker receives the original request, the Planner's plan, and the Architect's architecture.

It generates the complete source code for every required file.

The generated files are then written to the generated project directory.

## Tech Stack

### AI and Agentic AI

- Python
- Mistral
- LangChain
- LangGraph
- Pydantic

### Backend

- FastAPI
- Uvicorn

### Frontend

- React
- Vite
- Tailwind CSS

### Development Tools

- uv
- python-dotenv

## Project Structure

```text
Lovable/
│
├── frontend/
│   └── codebuddy/
│       ├── src/
│       │   ├── App.jsx
│       │   ├── App.css
│       │   └── main.jsx
│       ├── package.json
│       └── vite.config.js
│
├── generated_projects/
│   └── generated-app/
│       ├── index.html
│       ├── styles.css
│       ├── script.js
│       └── README.md
│
├── graph.py
├── prompts.py
├── api.py
├── requirements.txt
├── pyproject.toml
├── uv.lock
└── .env