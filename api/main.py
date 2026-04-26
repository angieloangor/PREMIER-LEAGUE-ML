from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import get_settings
from api.middleware.errors import register_exception_handlers
from api.middleware.logging import RequestLoggingMiddleware
from api.routes.health import router as health_router
from api.routes.models import router as models_router
from api.routes.dashboard_predictions import router as dashboard_predictions_router
from api.routes.predictions import router as predictions_router
from api.services.metadata_service import MetadataService
from api.services.model_loader import ModelRegistryService
from api.services.prediction_service import PredictionService
from scripts.download_models import download_models_if_needed


def _configure_logging() -> None:
    settings = get_settings()
    settings.api_logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = settings.api_logs_dir / "api.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    _configure_logging()

    logging.info("Checking model bundles...")
    download_models_if_needed()
    logging.info("Model bundles ready")

    registry = ModelRegistryService(settings)
    registry.load()

    app.state.settings = settings
    app.state.model_registry = registry
    app.state.prediction_service = PredictionService(registry, settings)
    app.state.metadata_service = MetadataService(registry)
    yield


settings = get_settings()
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="Professional FastAPI backend for serving match predictor model bundles.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:8001",
        "http://127.0.0.1:8001",
        "null",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)
register_exception_handlers(app)

app.include_router(health_router)
app.include_router(models_router)
app.include_router(dashboard_predictions_router)
app.include_router(predictions_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "service": settings.api_title, "docs": "/docs"}
