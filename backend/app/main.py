from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .database import Base, engine, ensure_schema_extras
from .routers import router

@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schema_extras()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Sikkim Organic Provenance",
    description="Hash-chained food supply traceability API (PBL)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# Serve the built React frontend (and its /trace/<id> SPA routes) from the same
# server when frontend/dist exists. This keeps local dev unchanged.
DIST_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if DIST_DIR.is_dir():

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        dist_root = DIST_DIR.resolve()
        candidate = (DIST_DIR / full_path).resolve() if full_path else None
        if candidate and candidate.is_file() and dist_root in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(DIST_DIR / "index.html")

