from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import add_request_logging, setup_logging
from app.routers import observations

setup_logging()
settings = get_settings()

app = FastAPI(
    title="StreamSaathi API",
    version="1.0.0",
    description="AI second opinion for citizen stream assessment. AI suggests, human decides.",
)

add_request_logging(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
    expose_headers=["X-Request-Id"],
)
register_error_handlers(app)
app.include_router(observations.router)


@app.get("/", include_in_schema=False)
def root():
    return {"name": "StreamSaathi API", "docs": "/docs", "health": "/api/v1/health"}
