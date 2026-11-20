"""BrandShield AI - FastAPI entry point.

Run from the backend folder:
    uvicorn app.main:app --reload
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.auth_routes import router as auth_router
from app.api.routes import router, ws_router
from app.auth import AuthMiddleware
from app.config import settings
from app.core import App

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    core = App(settings)
    app.state.core = core
    await core.start()
    yield
    await core.stop()


app = FastAPI(
    title="BrandShield AI",
    description="Real-Time Brand Risk & Sentiment Intelligence System",
    version="1.0.0",
    lifespan=lifespan,
)
# Starlette runs the middleware added last first: CORS wraps the login check,
# so 401 responses still carry CORS headers.
app.add_middleware(AuthMiddleware, settings=settings)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)
app.include_router(auth_router)
app.include_router(router)
app.include_router(ws_router)

# Serve the production build of the React dashboard when it exists
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404, "Not found")
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file() and FRONTEND_DIST in candidate.resolve().parents:
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
