from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import issues
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

app.include_router(issues.router, prefix="/api/v1", tags=["Issues"])


@app.get("/health")
def health() -> dict:
    return {
        "status": "operational",
        "ai_routing": "claude" if settings.ANTHROPIC_API_KEY else "fallback (no API key)",
        "model": settings.CLAUDE_MODEL,
    }


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/admin")


@app.get("/admin")
def admin_page() -> FileResponse:
    return FileResponse("frontend/admin.html")


@app.get("/report")
def report_page() -> FileResponse:
    return FileResponse("frontend/report.html")


# Serve any other static assets if added later.
app.mount("/static", StaticFiles(directory="frontend"), name="static")
