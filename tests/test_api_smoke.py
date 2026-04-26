from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

from api.main import app


def test_api_ready_and_models_endpoints():
    with TestClient(app) as client:
        ready = client.get("/ready")
        assert ready.status_code == 200
        ready_payload = ready.json()
        assert ready_payload["status"] == "ready"
        assert ready_payload["loaded_models"] >= 1

        models = client.get("/api/v1/models")
        assert models.status_code == 200
        payload = models.json()
        assert payload["loaded_models"] >= 1
        assert payload["default_model"]
        assert payload["models"][0]["id"]
        assert payload["models"][0]["name"]
        assert "|" in payload["models"][0]["name"]
        assert payload["models"][0]["feature_mode"]
        assert payload["models"][0]["stages"]["stage_1_regressor"]
        assert payload["models"][0]["stages"]["stage_2_classifier"]
        assert "performance" in payload["models"][0]
        assert "variables" not in payload["models"][0]

        model_info = client.get("/api/v1/model-info")
        assert model_info.status_code == 200
        model_info_payload = model_info.json()
        assert model_info_payload["loaded_models"] >= 1
        assert len(model_info_payload["models"]) == model_info_payload["loaded_models"]

        model_variables = client.get("/api/v1/models_variables")
        assert model_variables.status_code == 200
        variables_payload = model_variables.json()
        assert variables_payload["loaded_models"] >= 1
        assert variables_payload["models"][0]["variables"]["stage1_input_features"]
        assert variables_payload["models"][0]["variables"]["stage2_features"]


def test_api_predict_full_with_real_match_features_row():
    frame = pd.read_csv("data/processed/match_features.csv").tail(1)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/matches/predict-full",
            json={"records": frame.to_dict(orient="records")},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["rows"] == 1
    assert payload["model"]["id"]
    assert payload["model"]["name"]
    assert payload["model"]["feature_mode"]
    assert payload["model"]["stages"]["stage_1_regressor"]
    assert payload["predictions"][0]["predicted_result_label"] in {"H", "D", "A"}
    assert "stage1_predictions" in payload["predictions"][0]
