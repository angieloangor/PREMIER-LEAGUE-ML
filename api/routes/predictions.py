from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile

from api.dependencies.model_dependencies import get_prediction_service
from api.schemas.requests import MatchPredictionRequest
from api.schemas.responses import PredictionResponse, PredictionRow
from api.services.feature_service import csv_bytes_to_frame, rows_to_frame
from api.services.metadata_service import MetadataService
from api.services.prediction_service import PredictionService
from api.dependencies.model_dependencies import get_metadata_service


router = APIRouter(prefix="/api/v1/matches", tags=["predictions"])


@router.post("/predict-goals", response_model=PredictionResponse)
def predict_goals(
    payload: MatchPredictionRequest,
    prediction_service: PredictionService = Depends(get_prediction_service),
    metadata_service: MetadataService = Depends(get_metadata_service),
) -> PredictionResponse:
    frame = rows_to_frame(payload.records)
    result = prediction_service.predict_goals(payload.model_id, frame)
    bundle = result["bundle"]
    rows = [PredictionRow(**row) for row in result["rows"]]
    return PredictionResponse(
        model=metadata_service.get_model(bundle.model_id),
        rows=len(rows),
        predictions=rows,
    )


@router.post("/predict-winner", response_model=PredictionResponse)
def predict_winner(
    payload: MatchPredictionRequest,
    prediction_service: PredictionService = Depends(get_prediction_service),
    metadata_service: MetadataService = Depends(get_metadata_service),
) -> PredictionResponse:
    frame = rows_to_frame(payload.records)
    result = prediction_service.predict_winner(payload.model_id, frame)
    bundle = result["bundle"]
    return PredictionResponse(
        model=metadata_service.get_model(bundle.model_id),
        rows=len(result["rows"]),
        predictions=[PredictionRow(**row) for row in result["rows"]],
    )


@router.post("/predict-full", response_model=PredictionResponse)
def predict_full(
    payload: MatchPredictionRequest,
    prediction_service: PredictionService = Depends(get_prediction_service),
    metadata_service: MetadataService = Depends(get_metadata_service),
) -> PredictionResponse:
    frame = rows_to_frame(payload.records)
    result = prediction_service.predict_full(payload.model_id, frame)
    bundle = result["bundle"]
    return PredictionResponse(
        model=metadata_service.get_model(bundle.model_id),
        rows=len(result["rows"]),
        predictions=[PredictionRow(**row) for row in result["rows"]],
    )


@router.post("/predict-full-csv", response_model=PredictionResponse)
async def predict_full_csv(
    file: UploadFile = File(...),
    model_id: str | None = Form(default=None),
    prediction_service: PredictionService = Depends(get_prediction_service),
    metadata_service: MetadataService = Depends(get_metadata_service),
) -> PredictionResponse:
    frame = csv_bytes_to_frame(await file.read())
    result = prediction_service.predict_full(model_id, frame)
    bundle = result["bundle"]
    return PredictionResponse(
        model=metadata_service.get_model(bundle.model_id),
        rows=len(result["rows"]),
        predictions=[PredictionRow(**row) for row in result["rows"]],
    )
