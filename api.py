import asyncio
import logging
import os
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from graph import graph, create_project_files

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app_builder.api")

# Backend deadline for one generation (planner -> architect -> worker).
# Must stay below the frontend deadline (170s in frontend/codebuddy/src/config.js).
GENERATION_TIMEOUT_SECONDS = int(os.getenv("GENERATION_TIMEOUT_SECONDS", "150"))


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="AI App Builder API"
)


# ============================================================
# CORS
# ============================================================

DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://ai-app-builder-frontend-ovkp.onrender.com",
]


def _build_allowed_origins() -> list[str]:
    """Default origins plus any comma-separated origins in ALLOWED_ORIGINS."""
    origins = list(DEFAULT_ALLOWED_ORIGINS)
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(","):
        # Origins never end with "/"; a trailing slash would never match.
        cleaned = origin.strip().rstrip("/")
        if cleaned and cleaned not in origins:
            origins.append(cleaned)
    return origins


ALLOWED_ORIGINS = _build_allowed_origins()
logger.info("[API] CORS allowed origins: %s", ALLOWED_ORIGINS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
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


async def _cancel_on_client_disconnect(
    request: Request,
    generation_task: asyncio.Task,
) -> None:
    try:
        while not generation_task.done():
            try:
                message = await asyncio.wait_for(request.receive(), timeout=0.5)
            except (TimeoutError, asyncio.TimeoutError):
                continue

            if message.get("type") == "http.disconnect":
                logger.info("[API] Client disconnected; cancelling generation task")
                generation_task.cancel()
                return
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.debug("[API] Disconnect listener exited (%s)", type(exc).__name__)


def _consume_cancelled_generation(task: asyncio.Task) -> None:
    if task.cancelled():
        return

    error = task.exception()
    if error is not None:
        logger.error(
            "[API] Generation task failed during cancellation (%s: %s)",
            type(error).__name__,
            str(error),
        )


def _generation_error(error: Exception) -> tuple[int, str]:
    code = getattr(error, "code", None)
    code_text = str(code).upper()
    provider_status = str(getattr(error, "status", "")).upper()
    error_text = str(error).lower()

    if (
        code == 429
        or code_text == "429"
        or provider_status in {"RESOURCE_EXHAUSTED", "QUOTA_EXCEEDED"}
        or "quota" in error_text
        or "resource_exhausted" in error_text
    ):
        return 429, "Gemini API quota exceeded. Check your API limits and try again."

    if (
        code in {401, 403}
        or code_text in {"401", "403"}
        or provider_status in {"UNAUTHENTICATED", "PERMISSION_DENIED"}
        or "api key" in error_text
        or "api_key" in error_text
        or "unauthenticated" in error_text
    ):
        return 401, "Gemini rejected the API key or project access. Check GOOGLE_API_KEY and Gemini API access."

    if (
        code == 504
        or code_text == "504"
        or provider_status in {"DEADLINE_EXCEEDED"}
        or "deadline" in error_text
        or "deadline_exceeded" in error_text
        or "timed out" in error_text
        or "timeout" in error_text
    ):
        return 504, "Generation took too long. Gemini request timed out. Please try again."

    if "api key required" in error_text or "google_api_key" in error_text:
        return 500, "GOOGLE_API_KEY is not configured in the backend environment. Set it in the Render service's Environment settings."

    if (
        code == 404
        or code_text == "404"
        or provider_status == "NOT_FOUND"
        or ("model" in error_text and "not found" in error_text)
    ):
        return 502, (
            f"Gemini model '{os.getenv('GEMINI_MODEL', 'gemini-3.5-flash-lite')}' was not found or is not "
            "available for this API key. Set GEMINI_MODEL to a model your key can use."
        )

    # Surface the real provider reason instead of a bare exception class name.
    # The API key is redacted in case a library echoes it in the message.
    detail = str(error).strip().replace("\n", " ")
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        detail = detail.replace(api_key, "[redacted]")
    if len(detail) > 300:
        detail = detail[:300] + "..."
    return 502, f"App generation failed ({type(error).__name__}): {detail or 'no error message from provider'}"


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
async def generate_app(payload: GenerateRequest, request: Request):
    clean_prompt = payload.prompt.strip()
    if not clean_prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    start_time = time.perf_counter()
    preview = (clean_prompt[:70] + "...") if len(clean_prompt) > 70 else clean_prompt
    logger.info("[API] Incoming generation request: %r", preview)

    generation_task = asyncio.create_task(
        graph.ainvoke(
            {
                "user_prompt": clean_prompt,
                "plan": None,
                "architecture": None,
                "generated_project": None,
            }
        )
    )
    disconnect_task = asyncio.create_task(
        _cancel_on_client_disconnect(request, generation_task)
    )

    try:
        async with asyncio.timeout(GENERATION_TIMEOUT_SECONDS):
            result = await generation_task
    except (TimeoutError, asyncio.TimeoutError) as error:
        generation_task.cancel()
        generation_task.add_done_callback(_consume_cancelled_generation)
        elapsed = time.perf_counter() - start_time
        logger.warning(
            "[API] App generation exceeded backend deadline of %ds (elapsed: %.2fs)",
            GENERATION_TIMEOUT_SECONDS,
            elapsed,
        )
        raise HTTPException(
            status_code=504,
            detail="Generation took too long. Please try again.",
        ) from error
    except asyncio.CancelledError:
        generation_task.cancel()
        generation_task.add_done_callback(_consume_cancelled_generation)
        elapsed = time.perf_counter() - start_time
        logger.info("[API] App generation was cancelled after %.2fs", elapsed)
        raise
    except Exception as error:
        elapsed = time.perf_counter() - start_time
        status_code, message = _generation_error(error)
        logger.error(
            "[API] App generation failed after %.2fs (%s: %s, provider status=%s)",
            elapsed,
            type(error).__name__,
            str(error),
            getattr(error, "status", "unknown"),
        )
        raise HTTPException(status_code=status_code, detail=message) from error
    finally:
        disconnect_task.cancel()
        await asyncio.gather(disconnect_task, return_exceptions=True)

    project = result.get("generated_project")
    if not project or not getattr(project, "files", None):
        logger.error("[API] Graph completed but generated_project has no files")
        raise HTTPException(
            status_code=502,
            detail="Generation finished, but no project files were generated.",
        )

    # Actually write the files to disk for static preview
    project_dir = create_project_files(project, PREVIEW_DIR)
    total_elapsed = time.perf_counter() - start_time

    logger.info(
        "[API] Generation completed successfully in %.2fs. Written %d files to %s",
        total_elapsed,
        len(project.files),
        project_dir,
    )

    return {
        "files": [
            {
                "path": file.path,
                "content": file.content,
            }
            for file in project.files
        ],
        "preview_url": "/preview/index.html",
    }