"""FastAPI backend for RCABench Evaluation Dashboard."""

import logging
import os
import sys
import threading
from pathlib import Path

# Add parent directory to path for imports when running directly
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))

from api.deps import init_demo_mode
from api.routes import analysis, filters, matrix, metrics, samples
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

# Initialize demo mode if ANALYSIS_CACHE_FILE is set
init_demo_mode()

app = FastAPI(
    title="RCABench Evaluation Dashboard API",
    description="API for viewing and analyzing RCABench evaluation results",
    version="1.0.0",
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(filters.router, prefix="/api/v1", tags=["filters"])
app.include_router(metrics.router, prefix="/api/v1", tags=["metrics"])
app.include_router(samples.router, prefix="/api/v1", tags=["samples"])
app.include_router(analysis.router, prefix="/api/v1", tags=["analysis"])
app.include_router(matrix.router, prefix="/api/v1", tags=["matrix"])


@app.on_event("startup")
def precompute_analysis():
    """Load cache from file, or precompute in background if no cache file."""
    loaded = analysis._load_cache()
    if loaded > 0:
        logger.info(f"[Startup] Loaded {loaded} cached entries from file, ready instantly")
    else:
        def _run():
            from sota_rca.utils.sqlmodel_utils import SQLModelUtils
            try:
                with SQLModelUtils.create_session() as session:
                    analysis._precompute_all(session)
            except Exception as e:
                logger.warning(f"[Startup] Precompute failed: {e}")
        threading.Thread(target=_run, daemon=True).start()
        logger.info("[Startup] No cache file, precomputing in background")


@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "cache_entries": len(analysis._cache)}


# Serve static files in production (with no-cache for HTML to prevent stale pages)
FRONTEND_BUILD_DIR = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_BUILD_DIR.exists():
    from starlette.responses import FileResponse, Response

    @app.middleware("http")
    async def no_cache_html(request, call_next):
        response: Response = await call_next(request)
        if request.url.path == "/" or request.url.path.endswith(".html"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response

    from starlette.responses import FileResponse

    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_BUILD_DIR / "assets")), name="assets")

    # SPA fallback: serve index.html for any non-API route (client-side routing)
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        # Try serving a static file first
        file_path = FRONTEND_BUILD_DIR / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        # Otherwise serve index.html for client-side routing
        return FileResponse(str(FRONTEND_BUILD_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("DASHBOARD_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
