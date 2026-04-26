from __future__ import annotations

import json

import pandas as pd

from src.models.runner import MatchPredictorAutoML


def test_match_automl_smoke_run_creates_report(tmp_path):
    frame = pd.read_csv("data/processed/match_features.csv").head(160).copy()
    automl = MatchPredictorAutoML(
        match_features=frame,
        output_dir=tmp_path,
        holdout_ratio=0.2,
        cv_splits=2,
    )

    report = automl.run(
        regressors=["linear_regression"],
        classifiers=["ridge_classifier"],
        goal_feature_set="goals_compact",
        winner_feature_set="winner_default",
        explicit_pairs=[("linear_regression", "ridge_classifier")],
        feature_modes=["normal"],
        search_iterations=1,
        include_stage1_prediction=True,
        smote=False,
        session_name="smoke",
    )

    assert report["session"] == "smoke"
    assert len(report["runs"]) == 1

    run_dir = tmp_path / "smoke" / "linear_regression+ridge_classifier+normal"
    summary = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["regressor"]["name"] == "linear_regression"
    assert summary["classifier"]["name"] == "ridge_classifier"
    assert (run_dir / "regressor.joblib").exists()
    assert (run_dir / "classifier.joblib").exists()


def test_match_automl_advanced_smoke_run_creates_reports(tmp_path):
    frame = pd.read_csv("data/processed/match_features.csv").head(160).copy()
    automl = MatchPredictorAutoML(
        match_features=frame,
        output_dir=tmp_path,
        holdout_ratio=0.2,
        cv_splits=2,
    )

    report = automl.run(
        regressors=["linear_regression"],
        classifiers=["ridge_classifier"],
        winner_feature_set="winner_default",
        feature_modes=["normal"],
        search_iterations=1,
        smote=False,
        advance_modeling=True,
        stage1_feature_set="history_only",
        stage1_target_set="candidate_indices",
        stage1_top_k=1,
        stage1_min_r2=-999.0,
        session_name="advanced_smoke",
    )

    assert report["session"] == "advanced_smoke"
    assert len(report["stage1_runs"]) == 5
    assert len(report["stage2_runs"]) == 5
    assert len(report["selected_generators"]) == 5

    stage1_root = tmp_path / "advanced_smoke" / "stage1_feature_generators"
    stage2_dir = tmp_path / "advanced_smoke" / "stage2_classifier_runs"
    assert any(path.name == "regressor.joblib" for path in stage1_root.rglob("regressor.joblib"))
    assert any(path.name.endswith("run_summary.json") for path in stage2_dir.rglob("run_summary.json"))


def test_match_automl_advanced_include_all_adds_combined_run(tmp_path):
    frame = pd.read_csv("data/processed/match_features.csv").head(160).copy()
    automl = MatchPredictorAutoML(
        match_features=frame,
        output_dir=tmp_path,
        holdout_ratio=0.2,
        cv_splits=2,
    )

    report = automl.run(
        regressors=["linear_regression"],
        classifiers=["ridge_classifier"],
        winner_feature_set="winner_default",
        feature_modes=["normal"],
        search_iterations=1,
        smote=False,
        advance_modeling=True,
        stage1_feature_set="history_only",
        stage1_target_set="candidate_indices",
        stage1_top_k=1,
        stage1_min_r2=-999.0,
        include_all=True,
        session_name="advanced_include_all_smoke",
    )

    assert report["include_all"] is True
    assert len(report["best_generators_by_metric"]) == 5
    assert len(report["stage2_runs"]) == 6

    combined_runs = [item for item in report["stage2_runs"] if item["plan_type"] == "include_all"]
    assert len(combined_runs) == 1
    assert len(combined_runs[0]["generator_models"]) == 5
    assert combined_runs[0]["run_name"] == "include_all__ridge_classifier+normal"
