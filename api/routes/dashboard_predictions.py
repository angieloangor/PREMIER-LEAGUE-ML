from __future__ import annotations

from base64 import b64encode
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from api.config import Settings, get_settings
from api.dependencies.model_dependencies import get_prediction_service
from api.schemas.requests import TeamMatchPredictionRequest, XgPredictionRequest
from api.schemas.responses import (
    CsvBatchPredictionResponse,
    TeamMatchPredictionResponse,
    XgPredictionResponse,
)
from api.services.dashboard_prediction_service import predict_team_match, predict_xg
from api.services.feature_service import FeatureValidationError, csv_bytes_to_frame, require_columns
from api.services.prediction_service import PredictionService


router = APIRouter(tags=["dashboard-predictions"])

VALID_BATCH_TASKS = {"xg", "match_result", "match_goals", "match_full"}
BATCH_TASK_ALIASES = {"match": "match_full"}


@router.post("/predict/match", response_model=TeamMatchPredictionResponse)
def predict_match_for_dashboard(
    payload: TeamMatchPredictionRequest,
    settings: Settings = Depends(get_settings),
    prediction_service: PredictionService = Depends(get_prediction_service),
) -> TeamMatchPredictionResponse:
    return TeamMatchPredictionResponse(**predict_team_match(settings, prediction_service, payload))


@router.post("/predict/xg", response_model=XgPredictionResponse)
def predict_xg_for_dashboard(payload: XgPredictionRequest) -> XgPredictionResponse:
    return XgPredictionResponse(**predict_xg(payload))


def _raw_task(task: str | None) -> str:
    return str(task or "").strip().lower()


def _normalize_task(task: str | None) -> str:
    raw = _raw_task(task)
    return BATCH_TASK_ALIASES.get(raw, raw)


def _task_response_name(task: str | None) -> str:
    raw = _raw_task(task)
    return raw if raw == "match" else _normalize_task(task)


def _ensure_csv_upload(file: UploadFile) -> None:
    filename = (file.filename or "").lower()
    content_type = (file.content_type or "").lower()
    if not filename.endswith(".csv") and "csv" not in content_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe ser un CSV válido.",
        )


def _build_xg_row(row: pd.Series) -> dict[str, Any]:
    if pd.isna(row.get("x")) or pd.isna(row.get("y")):
        raise FeatureValidationError("El CSV xG debe incluir columnas 'x' y 'y' con valores válidos.")

    payload = {
        "x": row["x"],
        "y": row["y"],
        "shot_distance": None if pd.isna(row.get("shot_distance")) else row["shot_distance"],
        "shot_angle": None if pd.isna(row.get("shot_angle")) else row["shot_angle"],
        "is_big_chance": int(row["is_big_chance"]) if not pd.isna(row.get("is_big_chance")) else 0,
        "is_header": int(row["is_header"]) if not pd.isna(row.get("is_header")) else 0,
        "is_right_foot": int(row["is_right_foot"]) if not pd.isna(row.get("is_right_foot")) else 0,
        "is_left_foot": int(row["is_left_foot"]) if not pd.isna(row.get("is_left_foot")) else 0,
        "is_penalty": int(row["is_penalty"]) if not pd.isna(row.get("is_penalty")) else 0,
        "is_volley": int(row["is_volley"]) if not pd.isna(row.get("is_volley")) else 0,
        "first_touch": int(row["first_touch"]) if not pd.isna(row.get("first_touch")) else 0,
        "from_corner": int(row["from_corner"]) if not pd.isna(row.get("from_corner")) else 0,
        "is_counter": int(row["is_counter"]) if not pd.isna(row.get("is_counter")) else 0,
    }
    return payload


def _build_match_row(row: pd.Series) -> dict[str, str]:
    home = str(row.get("home_team", "")).strip()
    away = str(row.get("away_team", "")).strip()
    if not home or not away:
        raise FeatureValidationError("El CSV match debe incluir columnas 'home_team' y 'away_team' con valores válidos.")
    return {"home_team": home, "away_team": away}


def _require_batch_columns(frame: pd.DataFrame, required_columns: list[str], task_label: str) -> None:
    try:
        require_columns(frame, required_columns)
    except FeatureValidationError:
        missing = sorted(column for column in required_columns if column not in frame.columns)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"El CSV para {task_label} debe incluir columnas: "
                f"{', '.join(required_columns)}. Faltan: {', '.join(missing)}."
            ),
        )


def _row_input_values(row: pd.Series, columns: list[str]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for column in columns:
        value = row.get(column)
        if pd.isna(value):
            values[column] = None
        elif hasattr(value, "item"):
            values[column] = value.item()
        else:
            values[column] = value
    return values


def _shot_quality_label(xg: float) -> str:
    if xg >= 0.35:
        return "alta"
    if xg >= 0.15:
        return "media"
    return "baja"


def _format_csv_response(rows: list[dict[str, Any]]) -> tuple[list[str], str]:
    frame = pd.DataFrame(rows)
    csv_bytes = frame.to_csv(index=False).encode("utf-8")
    encoded = b64encode(csv_bytes).decode("utf-8")
    return list(frame.columns), encoded


def _summary_for_xg(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    values = [float(row["xg_prediction"]) for row in predictions]
    count = len(values)
    return {
        "avg_xg": sum(values) / count if count else 0.0,
        "max_xg": max(values) if count else 0.0,
        "high_quality_shots": sum(1 for row in predictions if row.get("shot_quality_label") == "alta"),
    }


def _summary_for_match_result(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    home_count = sum(1 for row in predictions if row.get("predicted_result") == "H")
    draw_count = sum(1 for row in predictions if row.get("predicted_result") == "D")
    away_count = sum(1 for row in predictions if row.get("predicted_result") == "A")
    return {
        "home_predictions": home_count,
        "draw_predictions": draw_count,
        "away_predictions": away_count,
    }


def _summary_for_match_goals(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    expected = [float(row.get("expected_goals", 0.0)) for row in predictions]
    total = len(expected)
    return {
        "avg_expected_goals": sum(expected) / total if total else 0.0,
    }


def _summary_for_match_full(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        **_summary_for_match_result(predictions),
        **_summary_for_match_goals(predictions),
    }


def _match_output_for_task(result: dict[str, Any], task_name: str) -> dict[str, Any]:
    output: dict[str, Any] = {}
    if task_name in {"match_result", "match_full"}:
        output.update({
            "home_win_probability": float(result["home_win_probability"]),
            "draw_probability": float(result["draw_probability"]),
            "away_win_probability": float(result["away_win_probability"]),
            "predicted_result": str(result.get("predicted_result")),
        })
    if task_name in {"match_goals", "match_full"}:
        output["expected_goals"] = float(result["expected_goals"])
    output["source"] = result.get("source")
    output["mode"] = result.get("mode", "fallback")
    output["ensemble_size"] = result.get("ensemble_size")
    output["best_model_score"] = result.get("best_model_score")
    return output


@router.post("/predict/batch", response_model=CsvBatchPredictionResponse)
async def predict_batch_csv(
    file: UploadFile = File(...),
    task: str = Form(...),
    settings: Settings = Depends(get_settings),
    prediction_service: PredictionService = Depends(get_prediction_service),
) -> CsvBatchPredictionResponse:
    _ensure_csv_upload(file)

    try:
        frame = csv_bytes_to_frame(await file.read())
    except FeatureValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"No se pudo leer el CSV: {exc}")

    if frame.empty:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo CSV está vacío.")

    task_name = _normalize_task(task)
    response_task = _task_response_name(task)
    if task_name not in VALID_BATCH_TASKS:
        valid = ", ".join(sorted(VALID_BATCH_TASKS | set(BATCH_TASK_ALIASES)))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"El campo 'task' debe ser uno de: {valid}.")

    if task_name == "xg":
        _require_batch_columns(frame, ["x", "y"], "xG por tiro")
        predictions: list[dict[str, Any]] = []
        for _, row in frame.iterrows():
            try:
                payload = _build_xg_row(row)
                result = predict_xg(XgPredictionRequest(**payload))
                xg_value = float(result["xg"])
                predictions.append({
                    **_row_input_values(row, list(frame.columns)),
                    "xg_prediction": xg_value,
                    "shot_quality_label": _shot_quality_label(xg_value),
                    "source": result.get("source"),
                })
            except FeatureValidationError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
            except Exception as exc:
                predictions.append({
                    **{col: None for col in frame.columns},
                    "xg_prediction": 0.0,
                    "shot_quality_label": "baja",
                    "source": "fallback",
                })

        columns, csv_base64 = _format_csv_response(predictions)
        summary = _summary_for_xg(predictions)
        mode = "fallback"
        return CsvBatchPredictionResponse(
            task=response_task,
            mode=mode,
            rows_processed=len(predictions),
            summary=summary,
            columns=columns,
            preview=predictions[:20],
            csv_base64=csv_base64,
        )

    _require_batch_columns(frame, ["home_team", "away_team"], "prediccion de partido")
    predictions = []
    observed_modes: set[str] = set()
    for _, row in frame.iterrows():
        try:
            payload = _build_match_row(row)
            result = predict_team_match(settings, prediction_service, TeamMatchPredictionRequest(**payload))
            observed_modes.add(str(result.get("mode") or "fallback"))
            predictions.append({
                **_row_input_values(row, list(frame.columns)),
                **_match_output_for_task(result, task_name),
            })
        except FeatureValidationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        except Exception as exc:
            fallback_result = {
                "home_win_probability": 0.0,
                "draw_probability": 0.0,
                "away_win_probability": 0.0,
                "expected_goals": 0.0,
                "predicted_result": "H",
                "source": "fallback",
                "mode": "fallback",
                "ensemble_size": 0,
                "best_model_score": None,
            }
            observed_modes.add("fallback")
            predictions.append({
                **{col: None for col in frame.columns},
                **_match_output_for_task(fallback_result, task_name),
            })

    columns, csv_base64 = _format_csv_response(predictions)
    if task_name == "match_result":
        summary = _summary_for_match_result(predictions)
    elif task_name == "match_goals":
        summary = _summary_for_match_goals(predictions)
    else:
        summary = _summary_for_match_full(predictions)
    mode = "ensemble" if "ensemble" in observed_modes else "model" if "model" in observed_modes else "fallback"
    return CsvBatchPredictionResponse(
        task=response_task,
        mode=mode,
        rows_processed=len(predictions),
        summary=summary,
        columns=columns,
        preview=predictions[:20],
        csv_base64=csv_base64,
    )
