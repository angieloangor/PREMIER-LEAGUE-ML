from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from api.config import Settings
from api.schemas.requests import TeamMatchPredictionRequest, XgPredictionRequest
from api.services.prediction_service import PredictionService


RESULT_ORDER = ("H", "D", "A")


def _team_key(team: str) -> str:
    return " ".join(str(team or "").strip().lower().replace(".", "").split())


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return number


def _clip_probability(value: float) -> float:
    return max(0.001, min(0.999, value))


def _predicted_result(home: float, draw: float, away: float) -> str:
    values = {"H": home, "D": draw, "A": away}
    return max(values, key=values.get)


@lru_cache(maxsize=1)
def _dashboard_predictions(project_root: str) -> list[dict[str, Any]]:
    root = Path(project_root)
    candidates = [
        root / "dashboard" / "dashboard_data.json",
        root / "outputs" / "dashboard_data.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return list(payload.get("predictions") or [])
        except Exception:
            continue
    return []


@lru_cache(maxsize=1)
def _matches_raw(project_root: str) -> pd.DataFrame:
    path = Path(project_root) / "data" / "matches.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


@lru_cache(maxsize=1)
def _matches_features(project_root: str) -> pd.DataFrame:
    path = Path(project_root) / "data" / "processed" / "matches_features.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


@lru_cache(maxsize=1)
def _eda_summary(project_root: str) -> dict[str, Any]:
    path = Path(project_root) / "data" / "processed" / "eda_summary.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _find_team_row(frame: pd.DataFrame, home_team: str, away_team: str) -> pd.DataFrame:
    if frame.empty or "home_team" not in frame.columns or "away_team" not in frame.columns:
        return pd.DataFrame()
    home_key = _team_key(home_team)
    away_key = _team_key(away_team)
    mask = frame["home_team"].map(_team_key).eq(home_key) & frame["away_team"].map(_team_key).eq(away_key)
    matched = frame.loc[mask].copy()
    if matched.empty:
        return matched
    if "kickoff" in matched.columns:
        matched = matched.sort_values("kickoff")
    elif "date" in matched.columns:
        matched["_sort_date"] = pd.to_datetime(matched["date"], dayfirst=True, errors="coerce")
        matched = matched.sort_values(["_sort_date", "time"] if "time" in matched.columns else ["_sort_date"]).drop(columns="_sort_date")
    return matched.tail(1)


def _model_match_prediction(
    settings: Settings,
    prediction_service: PredictionService,
    payload: TeamMatchPredictionRequest,
) -> dict[str, Any] | None:
    registry = prediction_service.registry
    if not registry.list_models():
        return None

    bundle = registry.get_bundle(payload.model_id)
    raw_matches = _matches_raw(str(settings.project_root))
    row = _find_team_row(raw_matches, payload.home_team, payload.away_team)
    if row.empty:
        return None

    feature_frame = prediction_service.prepare_frame(bundle.model_id, row)
    result = prediction_service.predict_full(payload.model_id, feature_frame)
    prediction = result["rows"][0]
    probabilities = prediction.get("probabilities") or {}
    home = _clip_probability(_safe_float(probabilities.get("home_win"), 0.0))
    draw = _clip_probability(_safe_float(probabilities.get("draw"), 0.0))
    away = _clip_probability(_safe_float(probabilities.get("away_win"), 0.0))
    total = home + draw + away
    home, draw, away = home / total, draw / total, away / total
    expected_goals = _safe_float(prediction.get("predicted_total_goals"), 2.7)

    return {
        "home_win_probability": home,
        "draw_probability": draw,
        "away_win_probability": away,
        "expected_goals": max(0.0, expected_goals),
        "predicted_result": str(prediction.get("predicted_result_label") or _predicted_result(home, draw, away)),
        "source": "api_model",
        "model": bundle.model_id,
        "fallback_reason": None,
    }


def _static_dashboard_match_prediction(settings: Settings, home_team: str, away_team: str, reason: str) -> dict[str, Any] | None:
    home_key = _team_key(home_team)
    away_key = _team_key(away_team)
    for row in _dashboard_predictions(str(settings.project_root)):
        if _team_key(row.get("home")) != home_key or _team_key(row.get("away")) != away_key:
            continue
        home = _clip_probability(_safe_float(row.get("prob_home")) / 100)
        draw = _clip_probability(_safe_float(row.get("prob_draw")) / 100)
        away = _clip_probability(_safe_float(row.get("prob_away")) / 100)
        total = home + draw + away
        home, draw, away = home / total, draw / total, away / total
        return {
            "home_win_probability": home,
            "draw_probability": draw,
            "away_win_probability": away,
            "expected_goals": max(0.0, _safe_float(row.get("est_goals"), 2.7)),
            "predicted_result": _predicted_result(home, draw, away),
            "source": "static_dashboard_fallback",
            "model": None,
            "fallback_reason": reason,
        }
    return None


def _market_match_prediction(settings: Settings, home_team: str, away_team: str, reason: str) -> dict[str, Any] | None:
    matches = _matches_features(str(settings.project_root))
    row = _find_team_row(matches, home_team, away_team)
    if row.empty:
        return None

    selected = row.iloc[0]
    if {"b365_home_prob_norm", "b365_draw_prob_norm", "b365_away_prob_norm"}.issubset(row.columns):
        home = _safe_float(selected.get("b365_home_prob_norm"), 0.42)
        draw = _safe_float(selected.get("b365_draw_prob_norm"), 0.26)
        away = _safe_float(selected.get("b365_away_prob_norm"), 0.32)
    elif {"b365h", "b365d", "b365a"}.issubset(row.columns):
        inv_home = 1 / max(_safe_float(selected.get("b365h"), 2.4), 0.001)
        inv_draw = 1 / max(_safe_float(selected.get("b365d"), 3.4), 0.001)
        inv_away = 1 / max(_safe_float(selected.get("b365a"), 3.0), 0.001)
        total_inv = inv_home + inv_draw + inv_away
        home, draw, away = inv_home / total_inv, inv_draw / total_inv, inv_away / total_inv
    else:
        return None

    total = home + draw + away
    home, draw, away = home / total, draw / total, away / total
    return {
        "home_win_probability": home,
        "draw_probability": draw,
        "away_win_probability": away,
        "expected_goals": max(0.0, _safe_float(selected.get("total_goals"), 2.7)),
        "predicted_result": _predicted_result(home, draw, away),
        "source": "market_odds_fallback",
        "model": None,
        "fallback_reason": reason,
    }


def _league_average_prediction(settings: Settings, reason: str) -> dict[str, Any]:
    summary = _eda_summary(str(settings.project_root))
    home = _safe_float(summary.get("home_win_rate"), 0.42)
    draw = _safe_float(summary.get("draw_rate"), 0.26)
    away = _safe_float(summary.get("away_win_rate"), 0.32)
    total = home + draw + away
    home, draw, away = home / total, draw / total, away / total
    return {
        "home_win_probability": home,
        "draw_probability": draw,
        "away_win_probability": away,
        "expected_goals": 2.7,
        "predicted_result": _predicted_result(home, draw, away),
        "source": "league_average_fallback",
        "model": None,
        "fallback_reason": reason,
    }


def predict_team_match(
    settings: Settings,
    prediction_service: PredictionService,
    payload: TeamMatchPredictionRequest,
) -> dict[str, Any]:
    fallback_reason = "API model unavailable; using dashboard/static fallback."
    try:
        prediction = _model_match_prediction(settings, prediction_service, payload)
        if prediction:
            return prediction
        fallback_reason = "No model-ready feature row found for the selected fixture."
    except Exception as exc:
        fallback_reason = f"API model prediction failed: {exc}"

    for fallback in (
        _static_dashboard_match_prediction(settings, payload.home_team, payload.away_team, fallback_reason),
        _market_match_prediction(settings, payload.home_team, payload.away_team, fallback_reason),
    ):
        if fallback:
            return fallback
    return _league_average_prediction(settings, fallback_reason)


def predict_xg(payload: XgPredictionRequest) -> dict[str, Any]:
    x = _safe_float(payload.x, 88.0)
    y = _safe_float(payload.y, 50.0)
    distance = payload.shot_distance
    if distance is None:
        distance = math.sqrt(((100 - x) ** 2) + ((50 - y) ** 2))
    distance = _safe_float(distance, 12.0)

    angle = payload.shot_angle
    if angle is None:
        angle = math.atan2(abs(50 - y), max(100 - x, 0.001))
    angle = _safe_float(angle, 0.2)

    centrality = 1 - min(angle / (math.pi / 2), 1)
    logit = (
        -2.70
        - (0.055 * distance)
        + (1.10 * centrality)
        + (1.35 * int(payload.is_big_chance))
        + (2.25 * int(payload.is_penalty))
        - (0.25 * int(payload.is_header))
        + (0.15 * int(payload.first_touch))
        + (0.12 * int(payload.is_volley))
        + (0.10 * int(payload.is_counter))
        + (0.04 * int(payload.from_corner))
    )
    xg = 1 / (1 + math.exp(-logit))
    return {
        "xg": _clip_probability(xg),
        "source": "heuristic_fallback",
        "fallback_reason": "No trained xG API artifact is registered; using documented logistic fallback.",
    }
