from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

logger = logging.getLogger(__name__)

RESULT_BY_PROBABILITY = {
    "home_win": "H",
    "draw": "D",
    "away_win": "A",
}

PROBABILITY_ALIASES = {
    "home_win": "home_win",
    "home_win_probability": "home_win",
    "prob_home": "home_win",
    "draw": "draw",
    "draw_probability": "draw",
    "prob_draw": "draw",
    "away_win": "away_win",
    "away_win_probability": "away_win",
    "prob_away": "away_win",
}


class EnsemblePredictionError(RuntimeError):
    """Raised when no ensemble member can produce a usable prediction."""


def _coerce_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _nested_float(payload: dict[str, Any], *keys: str) -> float | None:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return _coerce_float(current)


def extract_model_score(summary: dict[str, Any]) -> float | None:
    """Return the selection score used by the advanced classifier notebooks.

    Prefer an explicit score if one exists. Otherwise, mirror the weighted
    ranking in src.models.select_best_model and fall back to the strongest
    available classifier metric.
    """

    for key in ("score", "selection_score", "ensemble_score"):
        value = _coerce_float(summary.get(key))
        if value is not None:
            return value

    classifier = summary.get("classifier") or {}
    classifier_metrics = summary.get("classifier_metrics") or {}
    cv_metrics = classifier.get("cv_metrics") or {}
    test_metrics = classifier_metrics.get("test") or classifier_metrics

    cv_accuracy = _coerce_float(cv_metrics.get("mean_cv_accuracy") or classifier.get("best_cv_score"))
    cv_f1 = _coerce_float(cv_metrics.get("mean_cv_f1_weighted"))
    test_accuracy = _coerce_float(test_metrics.get("accuracy") or test_metrics.get("test_accuracy"))
    test_f1 = _coerce_float(test_metrics.get("f1_weighted") or test_metrics.get("test_f1_weighted"))

    ranked_values = (cv_accuracy, cv_f1, test_accuracy, test_f1)
    if all(value is not None for value in ranked_values):
        return sum(value for value in ranked_values if value is not None) / 4.0

    for value in (test_accuracy, test_f1, cv_accuracy, cv_f1):
        if value is not None:
            return value
    return None


@dataclass(frozen=True)
class EnsembleCandidate:
    model_id: str
    name: str
    bundle_dir: Path
    summary: dict[str, Any]
    score: float | None


@dataclass
class EnsembleMember:
    candidate: EnsembleCandidate
    bundle: Any
    weight: float = 0.0

    @property
    def model_id(self) -> str:
        return self.candidate.model_id

    @property
    def name(self) -> str:
        return self.candidate.name

    @property
    def score(self) -> float | None:
        return self.candidate.score


class EnsemblePredictor:
    def __init__(
        self,
        runs_root: str | Path,
        *,
        top_k: int | None = 10,
        min_score: float | None = 0.49,
    ) -> None:
        self.runs_root = Path(runs_root)
        self.top_k = top_k
        self.min_score = min_score
        self.total_models_found = 0
        self.candidates: list[EnsembleCandidate] = []
        self.selected_candidates: list[EnsembleCandidate] = []
        self.members: list[EnsembleMember] = []
        self.skipped: list[dict[str, Any]] = []
        self.prediction_failures: list[dict[str, Any]] = []

    @property
    def is_ready(self) -> bool:
        return bool(self.members)

    def discover(self) -> list[EnsembleCandidate]:
        self.total_models_found = 0
        self.candidates = []
        self.selected_candidates = []

        if not self.runs_root.exists():
            logger.warning("Ensemble runs root does not exist: %s", self.runs_root)
            return []

        for summary_path in sorted(self.runs_root.glob("*/run_summary.json")):
            self.total_models_found += 1
            bundle_dir = summary_path.parent
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                if not _has_classifier_artifact(bundle_dir):
                    self._skip(bundle_dir, "missing_classifier_artifact")
                    continue
                score = extract_model_score(summary)
                if self.min_score is not None and score is not None and score < self.min_score:
                    self._skip(bundle_dir, "below_min_score", score=score)
                    continue
                model_id = str(summary.get("run_name") or bundle_dir.name)
                self.candidates.append(
                    EnsembleCandidate(
                        model_id=model_id,
                        name=bundle_dir.name,
                        bundle_dir=bundle_dir,
                        summary=summary,
                        score=score,
                    )
                )
            except Exception as exc:
                self._skip(bundle_dir, str(exc))

        self.candidates.sort(
            key=lambda candidate: (
                candidate.score is not None,
                candidate.score if candidate.score is not None else -1.0,
                candidate.name,
            ),
            reverse=True,
        )
        if self.top_k is None or self.top_k <= 0:
            self.selected_candidates = list(self.candidates)
        else:
            self.selected_candidates = self.candidates[: self.top_k]
        return list(self.selected_candidates)

    def load(self, bundle_loader: Callable[[EnsembleCandidate], Any]) -> "EnsemblePredictor":
        self.members = []
        for candidate in self.discover():
            try:
                bundle = bundle_loader(candidate)
                self.members.append(EnsembleMember(candidate=candidate, bundle=bundle))
            except Exception as exc:
                self._skip(candidate.bundle_dir, str(exc), score=candidate.score)
                logger.warning("Skipping ensemble model %s: %s", candidate.bundle_dir, exc)

        self._assign_weights(self.members)
        logger.info(
            "Ensemble loaded %s/%s selected models from %s",
            len(self.members),
            len(self.selected_candidates),
            self.runs_root,
        )
        return self

    def predict(
        self,
        frame: Any,
        predict_member: Callable[[Any, Any], Sequence[dict[str, Any]]],
    ) -> dict[str, Any]:
        if not self.members:
            raise EnsemblePredictionError("No ensemble members are loaded.")

        successful: list[tuple[EnsembleMember, list[dict[str, Any]]]] = []
        self.prediction_failures = []

        for member in self.members:
            try:
                rows = list(predict_member(member.bundle, frame))
                if not rows:
                    raise EnsemblePredictionError("Model returned no rows.")
                successful.append((member, rows))
            except Exception as exc:
                failure = {"id": member.model_id, "name": member.name, "reason": str(exc)}
                self.prediction_failures.append(failure)
                logger.warning("Ensemble member failed during prediction: %s", failure)

        if not successful:
            raise EnsemblePredictionError("All ensemble members failed during prediction.")

        row_count = len(successful[0][1])
        if any(len(rows) != row_count for _, rows in successful):
            raise EnsemblePredictionError("Ensemble members returned inconsistent row counts.")

        weights = _renormalize_successful_weights([member for member, _ in successful])
        model_weights = [
            _member_weight_payload(member, weight)
            for (member, _), weight in zip(successful, weights)
        ]
        rows = [
            self._combine_row(row_index, successful, weights, model_weights)
            for row_index in range(row_count)
        ]
        scores = [member.score for member, _ in successful if member.score is not None]
        return {
            "mode": "ensemble",
            "rows": rows,
            "ensemble_size": len(successful),
            "model_weights": model_weights,
            "best_model_score": max(scores) if scores else None,
            "prediction_failures": list(self.prediction_failures),
        }

    def info(self) -> dict[str, Any]:
        scores = [member.score for member in self.members if member.score is not None]
        return {
            "total_models_found": self.total_models_found,
            "total_models_loaded": len(self.members),
            "total_models_used": len(self.members),
            "models_ignored": len(self.skipped),
            "min_score": min(scores) if scores else None,
            "max_score": max(scores) if scores else None,
            "avg_score": (sum(scores) / len(scores)) if scores else None,
            "top_models": [
                _member_weight_payload(member, member.weight)
                for member in sorted(self.members, key=lambda item: item.weight, reverse=True)
            ],
        }

    def _combine_row(
        self,
        row_index: int,
        successful: list[tuple[EnsembleMember, list[dict[str, Any]]]],
        weights: list[float],
        model_weights: list[dict[str, Any]],
    ) -> dict[str, Any]:
        combined = {"home_win": 0.0, "draw": 0.0, "away_win": 0.0}
        goal_sum = 0.0
        goal_weight = 0.0

        for (_, rows), weight in zip(successful, weights):
            row = rows[row_index]
            probabilities = _extract_probabilities(row)
            for key, value in probabilities.items():
                combined[key] += weight * value

            goals = _coerce_float(row.get("predicted_total_goals") or row.get("expected_goals"))
            if goals is not None:
                goal_sum += weight * goals
                goal_weight += weight

        combined = _normalize_probabilities(combined)
        probability_key = max(combined, key=combined.get)
        predicted_label = RESULT_BY_PROBABILITY[probability_key]
        return {
            "row_index": row_index,
            "predicted_total_goals": (goal_sum / goal_weight) if goal_weight else None,
            "predicted_result_code": predicted_label,
            "predicted_result_label": predicted_label,
            "probabilities": combined,
            "stage1_predictions": None,
            "metadata": {
                "mode": "ensemble",
                "ensemble_size": len(successful),
                "model_weights": model_weights,
            },
        }

    def _assign_weights(self, members: Iterable[EnsembleMember]) -> None:
        members = list(members)
        scores = [member.score for member in members]
        finite_scores = [score for score in scores if score is not None and score > 0]
        if finite_scores and len(finite_scores) == len(members):
            total = sum(finite_scores)
            if total > 0:
                for member in members:
                    member.weight = float(member.score or 0.0) / total
                return

        equal_weight = 1.0 / len(members) if members else 0.0
        for member in members:
            member.weight = equal_weight

    def _skip(self, bundle_dir: Path, reason: str, *, score: float | None = None) -> None:
        self.skipped.append(
            {
                "path": str(bundle_dir),
                "reason": reason,
                "score": score,
            }
        )


def _has_classifier_artifact(bundle_dir: Path) -> bool:
    return any((bundle_dir / f"classifier{extension}").exists() for extension in (".joblib", ".pt"))


def _member_weight_payload(member: EnsembleMember, weight: float) -> dict[str, Any]:
    return {
        "id": member.model_id,
        "name": member.name,
        "score": member.score,
        "weight": weight,
    }


def _renormalize_successful_weights(members: list[EnsembleMember]) -> list[float]:
    raw_weights = [member.weight for member in members]
    total = sum(weight for weight in raw_weights if math.isfinite(weight) and weight > 0)
    if total > 0:
        return [max(0.0, weight) / total for weight in raw_weights]
    return [1.0 / len(members) for _ in members]


def _extract_probabilities(row: dict[str, Any]) -> dict[str, float]:
    raw_probabilities: dict[str, Any] = {}
    probabilities = row.get("probabilities")
    if isinstance(probabilities, dict):
        raw_probabilities.update(probabilities)
    for key, value in row.items():
        if key in PROBABILITY_ALIASES:
            raw_probabilities[key] = value

    mapped = {"home_win": 0.0, "draw": 0.0, "away_win": 0.0}
    for key, value in raw_probabilities.items():
        alias = PROBABILITY_ALIASES.get(key)
        if not alias:
            continue
        mapped[alias] = max(0.0, _coerce_float(value) or 0.0)

    if sum(mapped.values()) <= 0:
        label = str(row.get("predicted_result_label") or row.get("predicted_result") or "").upper()
        label_to_key = {"H": "home_win", "D": "draw", "A": "away_win"}
        if label in label_to_key:
            mapped[label_to_key[label]] = 1.0

    return _normalize_probabilities(mapped)


def _normalize_probabilities(probabilities: dict[str, float]) -> dict[str, float]:
    total = sum(value for value in probabilities.values() if math.isfinite(value) and value >= 0)
    if total <= 0:
        raise EnsemblePredictionError("Model probabilities are empty or invalid.")
    return {
        "home_win": max(0.0, probabilities.get("home_win", 0.0)) / total,
        "draw": max(0.0, probabilities.get("draw", 0.0)) / total,
        "away_win": max(0.0, probabilities.get("away_win", 0.0)) / total,
    }
