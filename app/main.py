from fastapi import FastAPI

from app.api.routes import router as api_router
from app.core.config import settings
from app.db.session import init_db

app = FastAPI(
    title="PawLuxe Hotel Video Backend",
    version="0.2.0",
    description="FastAPI backend for pet hotel tracking and encrypted video analytics.",
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router, prefix=settings.api_prefix)
