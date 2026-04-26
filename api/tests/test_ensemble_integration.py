from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from api.main import app
from src.models.ensemble_predictor import EnsembleCandidate, EnsemblePredictor


def _candidate(name: str, score: float) -> EnsembleCandidate:
    return EnsembleCandidate(
        model_id=name,
        name=name,
        bundle_dir=Path(name),
        summary={"run_name": name},
        score=score,
    )


def test_ensemble_load_skips_bad_model_without_breaking():
    predictor = EnsemblePredictor("unused", top_k=5, min_score=0.49)
    candidates = [_candidate("good_model", 0.55), _candidate("bad_model", 0.56)]
    predictor.discover = lambda: candidates  # type: ignore[method-assign]
    predictor.total_models_found = 2

    def loader(candidate: EnsembleCandidate):
        if candidate.model_id == "bad_model":
            raise RuntimeError("corrupt artifact")
        return object()

    predictor.load(loader)

    assert predictor.total_models_found == 2
    assert len(predictor.members) == 1
    assert predictor.members[0].model_id == "good_model"
    assert predictor.skipped


def test_ensemble_weights_sum_to_one():
    predictor = EnsemblePredictor("unused", top_k=2, min_score=0.49)
    candidates = [_candidate("model_a", 0.50), _candidate("model_b", 0.60)]
    predictor.discover = lambda: candidates  # type: ignore[method-assign]

    predictor.load(lambda candidate: object())
    total_weight = sum(member.weight for member in predictor.members)

    assert len(predictor.members) == 2
    assert abs(total_weight - 1.0) < 1e-9


def test_ensemble_info_endpoint_responds():
    with TestClient(app) as client:
        response = client.get("/api/v1/ensemble-info")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_models_found"] >= body["total_models_loaded"]
    assert body["total_models_used"] == body["total_models_loaded"]
    assert "top_models" in body


def test_predict_match_unknown_teams_uses_valid_mode():
    with TestClient(app) as client:
        response = client.post(
            "/predict/match",
            json={"home_team": "Unknown FC", "away_team": "Missing United"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] in {"ensemble", "model", "fallback"}
    assert body["mode"] == "fallback"
    assert body["ensemble_size"] in {0, None}


def test_predict_full_returns_valid_mode():
    frame = pd.read_csv("data/processed/match_features.csv").tail(1)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/matches/predict-full",
            json={"records": frame.to_dict(orient="records")},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] in {"ensemble", "model", "fallback"}
    assert body["rows"] == 1
    assert body["predictions"][0]["predicted_result_label"] in {"H", "D", "A"}
