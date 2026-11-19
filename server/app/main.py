"""FindBack API entry point:  uvicorn app.main:app   (run from the server/ directory)."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import router as v1_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.db.session import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="FindBack API", version="1.0.0", lifespan=lifespan,
                  description="Lost & found reporting with AI-assisted (image/text/location) matching.")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                       allow_methods=["*"], allow_headers=["*"])
    register_exception_handlers(app)
    app.include_router(v1_router)

    @app.get("/api/v1/health", tags=["system"])
    def health():
        return {"status": "ok"}

    return app


app = create_app()
