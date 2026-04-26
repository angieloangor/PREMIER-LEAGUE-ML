from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from api.config import Settings, get_settings
from api.dependencies.model_dependencies import get_registry
from api.schemas.responses import HealthResponse, ReadyResponse
from api.services.model_loader import ModelRegistryService


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.api_title,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/ready", response_model=ReadyResponse)
def ready(
    registry: ModelRegistryService = Depends(get_registry),
) -> ReadyResponse:
    return ReadyResponse(
        status="ready" if registry.list_models() else "loading",
        loaded_models=len(registry.list_models()),
        default_model=registry.default_model_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
