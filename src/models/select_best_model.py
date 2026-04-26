from __future__ import annotations

import json
import shutil
from pathlib import Path


def _iter_run_summaries(runs_root, recursive: bool = False):
    runs_root = Path(runs_root)
    pattern = "**/run_summary.json" if recursive else "*/run_summary.json"
    for summary_path in runs_root.glob(pattern):
        with open(summary_path, "r", encoding="utf-8") as handle:
            yield summary_path, json.load(handle)


def rank_classifier_bundles(
    runs_root,
    top_k=5,
    weights=None,
):
    """
    Rankea los mejores bundles según métricas del classifier.
    """

    runs_root = Path(runs_root)
    if weights is None:
        weights = {
            "cv_accuracy": 0.25,
            "cv_f1_weighted": 0.25,
            "test_accuracy": 0.25,
            "test_f1_weighted": 0.25,
        }

    results = []
    for summary_path, summary in _iter_run_summaries(runs_root):
        classifier = summary.get("classifier", {})
        classifier_metrics = summary.get("classifier_metrics", {})
        if not classifier or not classifier_metrics:
            continue

        cv_metrics = classifier.get("cv_metrics", {})
        test_metrics = classifier_metrics.get("test", {})

        cv_accuracy = cv_metrics.get("mean_cv_accuracy", classifier.get("best_cv_score"))
        cv_f1 = cv_metrics.get("mean_cv_f1_weighted")
        test_accuracy = test_metrics.get("accuracy")
        test_f1 = test_metrics.get("f1_weighted")

        if None in [cv_accuracy, cv_f1, test_accuracy, test_f1]:
            continue

        score = (
            weights["cv_accuracy"] * cv_accuracy
            + weights["cv_f1_weighted"] * cv_f1
            + weights["test_accuracy"] * test_accuracy
            + weights["test_f1_weighted"] * test_f1
        )

        results.append(
            {
                "run_name": summary.get("run_name", summary_path.parent.name),
                "classifier_name": classifier.get("name"),
                "feature_mode": summary.get("feature_mode"),
                "score": score,
                "cv_accuracy": cv_accuracy,
                "cv_f1_weighted": cv_f1,
                "test_accuracy": test_accuracy,
                "test_f1_weighted": test_f1,
                "bundle_dir": str(summary_path.parent),
                "classifier_artifact_path": classifier.get("artifact_path"),
                "run_type": summary.get("run_type", "match_predictor"),
            }
        )

    results = sorted(
        results,
        key=lambda item: (
            item["score"],
            item["test_accuracy"],
            item["test_f1_weighted"],
            item["cv_accuracy"],
            item["cv_f1_weighted"],
        ),
        reverse=True,
    )

    top_results = results[:top_k]
    for index, item in enumerate(top_results, start=1):
        item["rank"] = index
    return top_results


def rank_regressor_bundles(
    runs_root,
    top_k=5,
    metric_name=None,
    min_test_r2=None,
    weights=None,
):
    """
    Rankea los mejores bundles de regresión según R2.

    Pensado para la etapa 1 del modo avanzado, donde el modelo genera
    features aproximadas del partido a partir de variables históricas ex ante.
    """

    runs_root = Path(runs_root)
    if weights is None:
        weights = {
            "cv_r2": 0.5,
            "test_r2": 0.5,
        }

    results = []
    for summary_path, summary in _iter_run_summaries(runs_root):
        regressor = summary.get("regressor", {})
        regression_metrics = summary.get("regression_metrics", {})
        if not regressor or not regression_metrics:
            continue
        if metric_name is not None and summary.get("target_metric") != metric_name:
            continue

        cv_metrics = regressor.get("cv_metrics", {})
        test_metrics = regression_metrics.get("test", {})

        cv_r2 = cv_metrics.get("mean_cv_r2", regressor.get("best_cv_score"))
        test_r2 = test_metrics.get("r2")
        test_rmse = test_metrics.get("rmse")
        test_mae = test_metrics.get("mae")

        if None in [cv_r2, test_r2]:
            continue

        score = (weights["cv_r2"] * cv_r2) + (weights["test_r2"] * test_r2)

        if min_test_r2 is not None and test_r2 < min_test_r2:
            continue

        results.append(
            {
                "run_name": summary.get("run_name", summary_path.parent.name),
                "regressor_name": regressor.get("name"),
                "feature_mode": summary.get("feature_mode"),
                "score": score,
                "cv_r2": cv_r2,
                "test_r2": test_r2,
                "test_rmse": test_rmse,
                "test_mae": test_mae,
                "bundle_dir": str(summary_path.parent),
                "regressor_artifact_path": regressor.get("artifact_path"),
                "target_columns": regressor.get("target_columns", []),
                "target_metric": summary.get("target_metric"),
                "run_type": summary.get("run_type", "regression"),
            }
        )

    results = sorted(
        results,
        key=lambda item: (
            item["score"],
            item["test_r2"],
            item["cv_r2"],
            -(item["test_rmse"] or 0.0),
        ),
        reverse=True,
    )

    top_results = results[:top_k]
    for index, item in enumerate(top_results, start=1):
        item["rank"] = index
    return top_results


def delete_bad_classifier_runs(
    runs_root,
    min_test_accuracy=0.40,
    dry_run=True,
    recursive=False,
    verbose=True,
):
    """
    Elimina carpetas de corridas cuyo classifier tenga test accuracy
    menor que min_test_accuracy.
    """

    runs_root = Path(runs_root)
    if not runs_root.exists():
        raise FileNotFoundError(f"No existe la carpeta: {runs_root.resolve()}")

    deleted = []
    kept = []
    skipped = []

    summaries = list(_iter_run_summaries(runs_root, recursive=recursive))
    if verbose:
        print(f"runs_root: {runs_root.resolve()}")
        print(f"run_summary.json encontrados: {len(summaries)}")
        print(f"Umbral mínimo test_accuracy: {min_test_accuracy}")
        print(f"dry_run: {dry_run}")

    for summary_path, summary in summaries:
        run_dir = summary_path.parent
        try:
            classifier_metrics = summary.get("classifier_metrics", {})
            test_metrics = classifier_metrics.get("test", {})
            test_accuracy = test_metrics.get("accuracy") or test_metrics.get("test_accuracy")
            run_name = summary.get("run_name", run_dir.name)

            if test_accuracy is None:
                skipped.append({"run_name": run_name, "run_dir": str(run_dir), "reason": "missing_test_accuracy"})
                if verbose:
                    print(f"[SKIP] {run_name}: no tiene test_accuracy")
                continue

            test_accuracy = float(test_accuracy)
            if test_accuracy < min_test_accuracy:
                deleted.append({"run_name": run_name, "run_dir": str(run_dir), "test_accuracy": test_accuracy})
                if verbose:
                    action = "WOULD DELETE" if dry_run else "DELETE"
                    print(f"[{action}] {run_name} | test_accuracy={test_accuracy:.4f}")
                if not dry_run:
                    shutil.rmtree(run_dir)
            else:
                kept.append({"run_name": run_name, "run_dir": str(run_dir), "test_accuracy": test_accuracy})
                if verbose:
                    print(f"[KEEP] {run_name} | test_accuracy={test_accuracy:.4f}")
        except Exception as exc:
            skipped.append({"run_dir": str(run_dir), "reason": str(exc)})
            if verbose:
                print(f"[ERROR] {run_dir}: {exc}")

    summary_result = {
        "evaluated": len(summaries),
        "deleted_or_to_delete": len(deleted),
        "kept": len(kept),
        "skipped": len(skipped),
        "dry_run": dry_run,
        "deleted": deleted,
        "kept": kept,
        "skipped": skipped,
    }

    if verbose:
        print("\nResumen:")
        print(f"Evaluadas: {summary_result['evaluated']}")
        print(f"A eliminar: {summary_result['deleted_or_to_delete']}")
        print(f"Conservadas: {summary_result['kept']}")
        print(f"Saltadas: {summary_result['skipped']}")

    return summary_result
