from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

from src.dataops import build_data_artifacts
from src.pipeline import run_pipeline
from src.models.runner import MatchPredictorAutoML


def _load_yaml_config(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _csv_list(raw_value: str | None) -> list[str] | None:
    if not raw_value:
        return None
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _pair_list(raw_values: list[str] | None) -> list[tuple[str, str]] | None:
    if not raw_values:
        return None
    pairs: list[tuple[str, str]] = []
    for raw_value in raw_values:
        left, right = [piece.strip() for piece in raw_value.split(",", maxsplit=1)]
        pairs.append((left, right))
    return pairs


def _resolve_training_option(
    cli_value,
    config: dict[str, Any],
    section: str,
    key: str,
    default,
):
    if cli_value is not None:
        return cli_value
    return config.get(section, {}).get(key, default)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train the legacy workshop pipeline, the basic two-model match predictor, or the advanced two-step predictor."
    )
    parser.add_argument(
        "--workflow",
        choices=["legacy", "basic-match-predictor", "advanced-match-predictor", "match-predictor"],
        default="basic-match-predictor",
        help="Training workflow to run.",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to a YAML config file for the match predictor workflow.",
    )
    parser.add_argument("--session-name", help="Session name for the match predictor sweep.")
    parser.add_argument("--output-dir", help="Optional output directory for model runs.")
    parser.add_argument("--regressors", help="Comma-separated list of regressor model keys.")
    parser.add_argument("--classifiers", help="Comma-separated list of classifier model keys.")
    parser.add_argument("--feature-modes", help="Comma-separated list of feature modes.")
    parser.add_argument("--goal-feature-set", help="Goal feature preset or explicit list name.")
    parser.add_argument("--winner-feature-set", help="Winner feature preset or explicit list name.")
    parser.add_argument("--search-iterations", type=int, help="Hyperparameter search iterations.")
    parser.add_argument("--holdout-ratio", type=float, help="Holdout ratio for the match predictor.")
    parser.add_argument("--cv-splits", type=int, help="Number of time-series CV splits.")
    parser.add_argument(
        "--advance-modeling",
        action="store_true",
        default=None,
        help="Enable the advanced two-pass workflow with stage1 feature generators.",
    )
    parser.add_argument(
        "--basic-modeling",
        action="store_false",
        dest="advance_modeling",
        help="Force the standard pair-based workflow.",
    )
    parser.add_argument("--stage1-feature-set", help="Feature preset for the advanced stage1 generators.")
    parser.add_argument("--stage1-target-set", help="Target preset for the advanced stage1 generators.")
    parser.add_argument("--stage1-top-k", type=int, help="How many stage1 generators to keep for stage2.")
    parser.add_argument("--stage1-min-r2", type=float, help="Minimum test R2 required for a stage1 generator to advance.")
    parser.add_argument(
        "--include-all",
        action="store_true",
        default=None,
        help="In advanced mode, add extra runs that append the best generated metric from each target at once.",
    )
    parser.add_argument(
        "--single-metric-only",
        action="store_false",
        dest="include_all",
        help="Disable the extra advanced runs that combine all best generated metrics.",
    )
    parser.add_argument(
        "--include-stage1-prediction",
        action="store_true",
        default=None,
        help="Inject stage1 predicted goals into stage2 classification.",
    )
    parser.add_argument(
        "--disable-stage1-prediction",
        action="store_false",
        dest="include_stage1_prediction",
        help="Disable stage1 predicted goals as a stage2 feature.",
    )
    parser.add_argument(
        "--smote",
        action="store_true",
        default=None,
        help="Apply SMOTE inside the classification pipeline.",
    )
    parser.add_argument(
        "--no-smote",
        action="store_false",
        dest="smote",
        help="Disable SMOTE inside the classification pipeline.",
    )
    parser.add_argument(
        "--pair",
        action="append",
        help="Explicit pair in the form 'regressor,classifier'. Can be provided multiple times.",
    )
    return parser


def run_legacy_workflow() -> None:
    results = run_pipeline()
    payload = results["payload"]
    print("Legacy workshop pipeline completed.")
    print(f"- match_accuracy_cv: {payload['match_accuracy']:.2f}%")
    print(f"- benchmark_bet365_cv: {payload['project_summary']['benchmark_bet365']:.2f}%")
    print(f"- xg_auc_roc: {payload['xg_metrics']['auc_roc']:.4f}")
    print(f"- dashboard_json: {results['exported']['dashboard_json']}")


def run_match_predictor_workflow(args: argparse.Namespace) -> None:
    workflow = args.workflow
    if workflow == "match-predictor":
        workflow = "basic-match-predictor"

    default_config = {
        "basic-match-predictor": "config/experiments/match_predictor_basic.yaml",
        "advanced-match-predictor": "config/experiments/match_predictor_advanced.yaml",
    }
    config = _load_yaml_config(args.config or default_config.get(workflow))

    regressors = _csv_list(args.regressors) or config.get("models", {}).get("regressors", ["linear_regression"])
    classifiers = _csv_list(args.classifiers) or config.get("models", {}).get("classifiers", ["ridge_classifier"])
    explicit_pairs = _pair_list(args.pair) or [
        tuple(pair) for pair in config.get("models", {}).get("explicit_pairs", [])
    ] or None

    training_config = config.get("training", {})
    holdout_ratio = _resolve_training_option(args.holdout_ratio, config, "training", "holdout_ratio", 0.2)
    cv_splits = _resolve_training_option(args.cv_splits, config, "training", "cv_splits", 5)
    search_iterations = _resolve_training_option(args.search_iterations, config, "training", "search_iterations", 8)
    default_advance_modeling = workflow == "advanced-match-predictor"
    advance_modeling = _resolve_training_option(
        args.advance_modeling,
        config,
        "training",
        "advance_modeling",
        default_advance_modeling,
    )
    include_stage1_prediction = _resolve_training_option(
        args.include_stage1_prediction,
        config,
        "training",
        "include_stage1_prediction",
        True,
    )
    smote = _resolve_training_option(args.smote, config, "training", "smote", True)
    stage1_feature_set = args.stage1_feature_set or training_config.get("stage1_feature_set", "history_only")
    stage1_target_set = args.stage1_target_set or training_config.get("stage1_target_set", "candidate_indices")
    stage1_top_k = _resolve_training_option(args.stage1_top_k, config, "training", "stage1_top_k", 3)
    stage1_min_r2 = _resolve_training_option(args.stage1_min_r2, config, "training", "stage1_min_r2", 0.15)
    include_all = _resolve_training_option(args.include_all, config, "training", "include_all", False)
    goal_feature_set = args.goal_feature_set or training_config.get("goal_feature_set", "goals_default")
    winner_feature_set = args.winner_feature_set or training_config.get("winner_feature_set", "winner_default")
    feature_modes = _csv_list(args.feature_modes) or training_config.get("feature_modes", ["normal"])

    data_artifacts = build_data_artifacts()
    match_features = data_artifacts["match_features"]
    output_dir = Path(args.output_dir) if args.output_dir else None

    runner = MatchPredictorAutoML(
        match_features=match_features,
        output_dir=output_dir,
        holdout_ratio=holdout_ratio,
        cv_splits=cv_splits,
    )
    report = runner.run(
        regressors=regressors,
        classifiers=classifiers,
        goal_feature_set=goal_feature_set,
        winner_feature_set=winner_feature_set,
        explicit_pairs=explicit_pairs,
        feature_modes=feature_modes,
        search_iterations=search_iterations,
        include_stage1_prediction=include_stage1_prediction,
        smote=smote,
        advance_modeling=advance_modeling,
        stage1_feature_set=stage1_feature_set,
        stage1_target_set=stage1_target_set,
        stage1_top_k=stage1_top_k,
        stage1_min_r2=stage1_min_r2,
        include_all=include_all,
        session_name=args.session_name,
    )
    print("Match predictor training completed.")
    print(f"- session: {report['session']}")
    if advance_modeling:
        print(f"- stage1_runs: {len(report['stage1_runs'])}")
        print(f"- stage2_runs: {len(report['stage2_runs'])}")
        print(f"- selected_generators: {len(report['selected_generators'])}")
        print(f"- include_all: {report['include_all']}")
        print(f"- stage1_min_r2: {report['stage1_min_r2']}")
    else:
        print(f"- runs: {len(report['runs'])}")
    print(f"- smote: {report['smote']}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.workflow == "legacy":
        run_legacy_workflow()
        return
    run_match_predictor_workflow(args)


if __name__ == "__main__":
    main()
