from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.config import get_settings
from api.services.model_loader import ModelBundle, ModelRegistryService
from api.services.prediction_service import PredictionService
from src.models.ensemble_predictor import EnsemblePredictor

LABELS = ["H", "D", "A"]


def _load_match_frame(project_root: Path) -> pd.DataFrame:
    candidates = [
        project_root / "data" / "processed" / "match_features.csv",
        project_root / "data" / "processed" / "matches_features.csv",
    ]
    for path in candidates:
        if path.exists():
            frame = pd.read_csv(path)
            if "ftr" in frame.columns:
                return frame.loc[frame["ftr"].isin(LABELS)].copy()
    raise FileNotFoundError("No processed match features file with an 'ftr' column was found.")


def _required_features(bundles: list[ModelBundle]) -> list[str]:
    required: set[str] = set()
    for bundle in bundles:
        required.update(bundle.regressor_features)
        required.update(bundle.classifier_base_features)
    return sorted(required)


def _ready_frame(frame: pd.DataFrame, bundles: list[ModelBundle]) -> pd.DataFrame:
    required = [column for column in _required_features(bundles) if column in frame.columns]
    if not required:
        return frame.copy()
    return frame.dropna(subset=required).copy()


def _labels_from_prediction_rows(rows: list[dict[str, Any]]) -> list[str]:
    labels = []
    for row in rows:
        label = str(row.get("predicted_result_label") or row.get("predicted_result") or "").upper()
        labels.append(label if label in LABELS else "H")
    return labels


def _bet365_labels(frame: pd.DataFrame) -> list[str]:
    labels = []
    for _, row in frame.iterrows():
        if {"b365_home_prob_norm", "b365_draw_prob_norm", "b365_away_prob_norm"}.issubset(frame.columns):
            scores = {
                "H": float(row.get("b365_home_prob_norm") or 0.0),
                "D": float(row.get("b365_draw_prob_norm") or 0.0),
                "A": float(row.get("b365_away_prob_norm") or 0.0),
            }
        else:
            scores = {
                "H": _inverse_odd(row.get("b365h")),
                "D": _inverse_odd(row.get("b365d")),
                "A": _inverse_odd(row.get("b365a")),
            }
        labels.append(max(scores, key=scores.get))
    return labels


def _inverse_odd(value: Any) -> float:
    try:
        odd = float(value)
    except (TypeError, ValueError):
        return 0.0
    return 1.0 / odd if odd > 0 else 0.0


def _metrics(y_true: list[str], y_pred: list[str]) -> dict[str, Any]:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=LABELS, average="macro", zero_division=0)),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=LABELS).tolist(),
        "labels": LABELS,
    }


def _evaluate_current_model(service: PredictionService, frame: pd.DataFrame) -> dict[str, Any]:
    bundle = service.registry.get_bundle(None)
    eval_frame = _ready_frame(frame, [bundle])
    result = service.predict_full(bundle.model_id, eval_frame)
    return {
        "rows": len(eval_frame),
        "model_id": bundle.model_id,
        **_metrics(eval_frame["ftr"].tolist(), _labels_from_prediction_rows(result["rows"])),
    }


def _evaluate_ensemble(
    service: PredictionService,
    settings,
    frame: pd.DataFrame,
    top_k: int | None,
) -> dict[str, Any]:
    service.ensemble = EnsemblePredictor(
        settings.runs_root,
        top_k=top_k,
        min_score=settings.ensemble_min_score,
    ).load(service._load_ensemble_candidate)
    bundles = [member.bundle for member in service.ensemble.members]
    eval_frame = _ready_frame(frame, bundles)
    result = service.predict_full_ensemble(eval_frame)
    return {
        "rows": len(eval_frame),
        "top_k": top_k or "all",
        "ensemble_size": result.get("ensemble_size", 0),
        "best_model_score": result.get("best_model_score"),
        **_metrics(eval_frame["ftr"].tolist(), _labels_from_prediction_rows(result["rows"])),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate current model, ensemble variants, and Bet365 benchmark.")
    parser.add_argument(
        "--top-k",
        default="5,10,20,all",
        help="Comma-separated ensemble sizes to evaluate. Use 'all' for all eligible models.",
    )
    parser.add_argument(
        "--output",
        default="data/processed/ensemble_summary.json",
        help="Output JSON path.",
    )
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    args = build_parser().parse_args()
    settings = get_settings()
    frame = _load_match_frame(settings.project_root)

    registry = ModelRegistryService(settings)
    registry.load()
    service = PredictionService(registry, settings)

    summary: dict[str, Any] = {
        "rows_available": len(frame),
        "current_model": None,
        "ensembles": {},
        "bet365": _metrics(frame["ftr"].tolist(), _bet365_labels(frame)),
        "errors": [],
    }

    try:
        summary["current_model"] = _evaluate_current_model(service, frame)
    except Exception as exc:
        summary["errors"].append({"target": "current_model", "error": str(exc)})

    for raw_top_k in [item.strip().lower() for item in args.top_k.split(",") if item.strip()]:
        top_k = None if raw_top_k == "all" else int(raw_top_k)
        label = f"top_{top_k}" if top_k else "all"
        try:
            summary["ensembles"][label] = _evaluate_ensemble(service, settings, frame, top_k)
        except Exception as exc:
            summary["errors"].append({"target": f"ensemble_{label}", "error": str(exc)})

    output_path = settings.project_root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
