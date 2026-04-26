from __future__ import annotations

from fastapi import Request

from api.services.metadata_service import MetadataService
from api.services.model_loader import ModelRegistryService
from api.services.prediction_service import PredictionService


def get_registry(request: Request) -> ModelRegistryService:
    return request.app.state.model_registry


def get_prediction_service(request: Request) -> PredictionService:
    return request.app.state.prediction_service


def get_metadata_service(request: Request) -> MetadataService:
    return request.app.state.metadata_service
