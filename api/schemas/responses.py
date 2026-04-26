from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: str


class ReadyResponse(BaseModel):
    status: str
    loaded_models: int
    default_model: str | None
    timestamp: str


class ModelPerformance(BaseModel):
    stage1_cv_r2: float | None = None
    stage1_cv_rmse: float | None = None
    stage1_test_r2: float | None = None
    stage1_test_rmse: float | None = None
    stage1_test_mae: float | None = None
    stage2_cv_accuracy: float | None = None
    stage2_cv_f1_weighted: float | None = None
    stage2_test_accuracy: float | None = None
    stage2_test_f1_weighted: float | None = None


class ModelStages(BaseModel):
    stage_1_regressor: str
    stage_1_target_metric: str | None = None
    stage_2_classifier: str


class ModelSummary(BaseModel):
    id: str
    name: str
    default: bool = False
    feature_mode: str | None = None
    stages: ModelStages
    performance: ModelPerformance


class ModelListResponse(BaseModel):
    default_model: str | None = None
    loaded_models: int
    models: list[ModelSummary]


class ModelVariables(BaseModel):
    feature_mode: str | None = None
    stage1_input_features: list[str]
    stage2_base_features: list[str]
    stage2_generated_features: list[str]
    stage2_features: list[str]


class ModelVariablesDescriptor(BaseModel):
    id: str
    name: str
    stages: ModelStages
    default: bool = False
    variables: ModelVariables


class ModelVariablesListResponse(BaseModel):
    default_model: str | None = None
    loaded_models: int
    models: list[ModelVariablesDescriptor]


class PredictionProbabilities(BaseModel):
    home_win: float | None = None
    draw: float | None = None
    away_win: float | None = None


class PredictionRow(BaseModel):
    row_index: int
    predicted_total_goals: float | None = None
    predicted_result_code: int | str | None = None
    predicted_result_label: str | None = None
    probabilities: PredictionProbabilities | None = None
    stage1_predictions: dict[str, float] | None = None
    metadata: dict[str, Any] | None = None


class PredictionResponse(BaseModel):
    model: ModelSummary
    rows: int
    predictions: list[PredictionRow]


class TeamMatchPredictionResponse(BaseModel):
    home_win_probability: float
    draw_probability: float
    away_win_probability: float
    expected_goals: float
    predicted_result: str
    source: str
    model: str | None = None
    fallback_reason: str | None = None


class XgPredictionResponse(BaseModel):
    xg: float
    source: str
    fallback_reason: str | None = None


class CsvBatchPredictionResponse(BaseModel):
    task: str
    mode: str
    rows_processed: int
    summary: dict[str, Any]
    columns: list[str]
    preview: list[dict[str, Any]]
    csv_base64: str
