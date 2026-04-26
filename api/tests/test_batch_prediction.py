from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app


def _post_batch(csv_content: str, task: str):
    with TestClient(app) as client:
        return client.post(
            "/predict/batch",
            files={"file": ("sample.csv", csv_content, "text/csv")},
            data={"task": task},
        )


def test_predict_batch_xg_valid_csv():
    csv_content = """x,y,is_big_chance,is_header,is_penalty
88,50,1,0,0
75,40,0,1,0
"""
    response = _post_batch(csv_content, "xg")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["task"] == "xg"
    assert body["rows_processed"] == 2
    assert body["mode"] in {"model", "fallback"}
    assert "xg_prediction" in body["preview"][0]
    assert "shot_quality_label" in body["preview"][0]
    assert body["preview"][0]["shot_quality_label"] in {"baja", "media", "alta"}
    assert "avg_xg" in body["summary"]
    assert "max_xg" in body["summary"]
    assert "high_quality_shots" in body["summary"]
    assert body["csv_base64"]


def test_predict_batch_match_result_valid_csv():
    csv_content = """home_team,away_team
Arsenal,Chelsea
Liverpool,Everton
"""
    response = _post_batch(csv_content, "match_result")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["task"] == "match_result"
    assert body["rows_processed"] == 2
    preview = body["preview"][0]
    assert "home_win_probability" in preview
    assert "draw_probability" in preview
    assert "away_win_probability" in preview
    assert "predicted_result" in preview
    assert "expected_goals" not in preview
    assert {"home_predictions", "draw_predictions", "away_predictions"} <= set(body["summary"])
    assert body["csv_base64"]


def test_predict_batch_match_goals_valid_csv():
    csv_content = """home_team,away_team
Arsenal,Chelsea
Liverpool,Everton
"""
    response = _post_batch(csv_content, "match_goals")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["task"] == "match_goals"
    assert body["rows_processed"] == 2
    preview = body["preview"][0]
    assert "expected_goals" in preview
    assert "predicted_result" not in preview
    assert "home_win_probability" not in preview
    assert "avg_expected_goals" in body["summary"]
    assert body["csv_base64"]


def test_predict_batch_match_full_valid_csv():
    csv_content = """home_team,away_team
Arsenal,Chelsea
Liverpool,Everton
"""
    response = _post_batch(csv_content, "match_full")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["task"] == "match_full"
    preview = body["preview"][0]
    assert "home_win_probability" in preview
    assert "draw_probability" in preview
    assert "away_win_probability" in preview
    assert "predicted_result" in preview
    assert "expected_goals" in preview
    assert {"home_predictions", "draw_predictions", "away_predictions", "avg_expected_goals"} <= set(body["summary"])
    assert body["csv_base64"]


def test_predict_batch_match_alias_still_works():
    csv_content = """home_team,away_team
Arsenal,Chelsea
"""
    response = _post_batch(csv_content, "match")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["task"] == "match"
    preview = body["preview"][0]
    assert "home_win_probability" in preview
    assert "draw_probability" in preview
    assert "away_win_probability" in preview
    assert "predicted_result" in preview
    assert "expected_goals" in preview


def test_predict_batch_invalid_task_rejected():
    csv_content = """x,y
88,50
"""
    response = _post_batch(csv_content, "unknown")

    assert response.status_code == 400
    assert "task" in response.json()["detail"]


def test_predict_batch_missing_required_columns():
    csv_content = """a,b
1,2
"""
    response = _post_batch(csv_content, "xg")

    assert response.status_code == 400
    assert "x" in response.json()["detail"]
    assert "y" in response.json()["detail"]


def test_predict_batch_non_csv_file_rejected():
    with TestClient(app) as client:
        response = client.post(
            "/predict/batch",
            files={"file": ("sample.txt", "hello world", "text/plain")},
            data={"task": "xg"},
        )
    assert response.status_code == 400
    assert "CSV" in response.json()["detail"]
