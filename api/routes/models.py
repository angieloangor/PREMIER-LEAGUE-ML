from __future__ import annotations

from fastapi import APIRouter, Depends

from api.dependencies.model_dependencies import get_metadata_service, get_prediction_service
from api.schemas.responses import (
    EnsembleInfoResponse,
    ModelListResponse,
    ModelSummary,
    ModelVariablesDescriptor,
    ModelVariablesListResponse,
)
from api.services.metadata_service import MetadataService
from api.services.prediction_service import PredictionService


router = APIRouter(prefix="/api/v1", tags=["models"])


@router.get("/models", response_model=ModelListResponse)
def list_models(metadata_service: MetadataService = Depends(get_metadata_service)) -> ModelListResponse:
    models = [ModelSummary(**item) for item in metadata_service.list_models()]
    return ModelListResponse(
        default_model=metadata_service.registry.default_model_id,
        loaded_models=len(models),
        models=models,
    )


@router.get("/model-info", response_model=ModelListResponse)
def get_model_info(metadata_service: MetadataService = Depends(get_metadata_service)) -> ModelListResponse:
    models = [ModelSummary(**item) for item in metadata_service.list_models()]
    return ModelListResponse(
        default_model=metadata_service.registry.default_model_id,
        loaded_models=len(models),
        models=models,
    )


@router.get("/ensemble-info", response_model=EnsembleInfoResponse)
def get_ensemble_info(prediction_service: PredictionService = Depends(get_prediction_service)) -> EnsembleInfoResponse:
    return EnsembleInfoResponse(**prediction_service.ensemble_info())


@router.get("/models/{model_id}", response_model=ModelSummary)
def get_model(model_id: str, metadata_service: MetadataService = Depends(get_metadata_service)) -> ModelSummary:
    return ModelSummary(**metadata_service.get_model(model_id))


@router.get("/models_variables", response_model=ModelVariablesListResponse)
def list_model_variables(metadata_service: MetadataService = Depends(get_metadata_service)) -> ModelVariablesListResponse:
    models = [ModelVariablesDescriptor(**item) for item in metadata_service.list_model_variables()]
    return ModelVariablesListResponse(
        default_model=metadata_service.registry.default_model_id,
        loaded_models=len(models),
        models=models,
    )


@router.get("/models_variables/{model_id}", response_model=ModelVariablesDescriptor)
def get_model_variables(model_id: str, metadata_service: MetadataService = Depends(get_metadata_service)) -> ModelVariablesDescriptor:
    return ModelVariablesDescriptor(**metadata_service.get_model_variables(model_id))
