from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from api.config import Settings
from api.services.feature_service import numeric_frame
from api.services.match_feature_builder_service import MatchFeatureBuilderService
from api.services.model_loader import ModelBundle, ModelRegistryService

RESULT_LABELS = {0: "H", 1: "D", 2: "A", "H": "H", "D": "D", "A": "A"}
PROBABILITY_KEYS = {0: "home_win", 1: "draw", 2: "away_win", "H": "home_win", "D": "draw", "A": "away_win"}


class PredictionService:
    def __init__(self, registry: ModelRegistryService, settings: Settings) -> None:
        self.registry = registry
        self.feature_builder = MatchFeatureBuilderService(settings)

    def predict_goals(self, model_id: str | None, frame: pd.DataFrame) -> dict[str, Any]:
        bundle = self.registry.get_bundle(model_id)
        frame = self.prepare_frame(bundle.model_id, frame)
        stage1_predictions = self._predict_stage1(bundle, frame)
        rows = self._rows_from_stage1_predictions(bundle, stage1_predictions)
        return {"bundle": bundle, "rows": rows}

    def predict_winner(self, model_id: str | None, frame: pd.DataFrame) -> dict[str, Any]:
        bundle = self.registry.get_bundle(model_id)
        frame = self.prepare_frame(bundle.model_id, frame)
        stage1_predictions = self._predict_stage1(bundle, frame) if bundle.uses_stage1_prediction else None
        classifier_frame = self._build_classifier_frame(bundle, frame, stage1_predictions=stage1_predictions)
        predicted_codes = bundle.classifier.predict(classifier_frame)
        probabilities = self._predict_probabilities(bundle.classifier, classifier_frame, predicted_codes)
        rows = self._rows_from_predictions(
            bundle=bundle,
            predicted_goals=self._goal_prediction_vector(bundle, stage1_predictions),
            predicted_codes=predicted_codes,
            probabilities=probabilities,
            stage1_predictions=stage1_predictions,
        )
        return {"bundle": bundle, "rows": rows}

    def predict_full(self, model_id: str | None, frame: pd.DataFrame) -> dict[str, Any]:
        bundle = self.registry.get_bundle(model_id)
        frame = self.prepare_frame(bundle.model_id, frame)
        stage1_predictions = self._predict_stage1(bundle, frame)
        predicted_goals = self._goal_prediction_vector(bundle, stage1_predictions)
        classifier_frame = self._build_classifier_frame(bundle, frame, stage1_predictions=stage1_predictions)
        predicted_codes = bundle.classifier.predict(classifier_frame)
        probabilities = self._predict_probabilities(bundle.classifier, classifier_frame, predicted_codes)
        rows = self._rows_from_predictions(
            bundle=bundle,
            predicted_goals=predicted_goals,
            predicted_codes=predicted_codes,
            probabilities=probabilities,
            stage1_predictions=stage1_predictions,
        )
        return {"bundle": bundle, "rows": rows}

    def prepare_frame(self, model_id: str | None, frame: pd.DataFrame) -> pd.DataFrame:
        bundle = self.registry.get_bundle(model_id)
        required_features = set(bundle.regressor_features + bundle.classifier_base_features)
        if required_features.issubset(frame.columns):
            return frame.copy()
        return self.feature_builder.build_feature_frame(frame)

    def _build_classifier_frame(
        self,
        bundle: ModelBundle,
        frame: pd.DataFrame,
        stage1_predictions: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        classifier_frame = numeric_frame(frame, bundle.classifier_base_features)
        if bundle.uses_stage1_prediction:
            local_stage1_predictions = stage1_predictions
            if local_stage1_predictions is None:
                local_stage1_predictions = self._predict_stage1(bundle, frame)
            classifier_frame = classifier_frame.copy()
            for column in bundle.stage1_generated_features:
                classifier_frame[column] = local_stage1_predictions[column].to_numpy()
        return classifier_frame.loc[:, bundle.classifier_features]

    def _predict_stage1(self, bundle: ModelBundle, frame: pd.DataFrame) -> pd.DataFrame:
        stage1_frame = numeric_frame(frame, bundle.regressor_features)
        raw_predictions = np.asarray(bundle.regressor.predict(stage1_frame))
        if raw_predictions.ndim == 1:
            raw_predictions = raw_predictions.reshape(-1, 1)
        columns = self._stage1_output_columns(bundle, raw_predictions.shape[1])
        return pd.DataFrame(raw_predictions, columns=columns, index=frame.index)

    def _stage1_output_columns(self, bundle: ModelBundle, width: int) -> list[str]:
        if bundle.stage1_generated_features:
            return bundle.stage1_generated_features
        if width == 1:
            if bundle.stage1_prediction_is_total_goals:
                return ["stage1_pred_total_goals"]
            if bundle.stage1_target_metric:
                return [f"approx_{bundle.stage1_target_metric}"]
            return ["stage1_output"]
        return [f"stage1_output_{index}" for index in range(width)]

    def _goal_prediction_vector(
        self,
        bundle: ModelBundle,
        stage1_predictions: pd.DataFrame | None,
    ) -> np.ndarray | None:
        if stage1_predictions is None or not bundle.stage1_prediction_is_total_goals or stage1_predictions.shape[1] != 1:
            return None
        return np.asarray(stage1_predictions.iloc[:, 0], dtype=float)

    def _rows_from_stage1_predictions(
        self,
        bundle: ModelBundle,
        stage1_predictions: pd.DataFrame,
    ) -> list[dict[str, Any]]:
        predicted_goals = self._goal_prediction_vector(bundle, stage1_predictions)
        rows: list[dict[str, Any]] = []
        for index in range(len(stage1_predictions)):
            stage1_row = self._stage1_prediction_row(stage1_predictions, index)
            rows.append(
                {
                    "row_index": index,
                    "predicted_total_goals": None if predicted_goals is None else float(predicted_goals[index]),
                    "predicted_result_code": None,
                    "predicted_result_label": None,
                    "probabilities": None,
                    "stage1_predictions": stage1_row,
                    "metadata": self._row_metadata(bundle),
                }
            )
        return rows

    def _predict_probabilities(self, classifier, X: pd.DataFrame, predicted_codes) -> list[dict[str, float] | None]:
        if hasattr(classifier, "predict_proba"):
            raw_probabilities = classifier.predict_proba(X)
            classes = self._classifier_classes(classifier)
            return [self._map_probabilities(classes, row) for row in raw_probabilities]

        if hasattr(classifier, "decision_function"):
            scores = np.asarray(classifier.decision_function(X))
            if scores.ndim == 1:
                scores = np.column_stack([-scores, scores])
            shifted = scores - scores.max(axis=1, keepdims=True)
            exp_scores = np.exp(shifted)
            probabilities = exp_scores / exp_scores.sum(axis=1, keepdims=True)
            classes = self._classifier_classes(classifier)
            return [self._map_probabilities(classes, row) for row in probabilities]

        return [self._fallback_probabilities(code) for code in predicted_codes]

    def _classifier_classes(self, classifier):
        if hasattr(classifier, "classes_"):
            return list(classifier.classes_)
        if hasattr(classifier, "named_steps") and "model" in classifier.named_steps:
            return list(classifier.named_steps["model"].classes_)
        raise AttributeError("Classifier does not expose classes_.")

    def _map_probabilities(self, classes, row: np.ndarray) -> dict[str, float]:
        mapped = {"home_win": 0.0, "draw": 0.0, "away_win": 0.0}
        for class_value, probability in zip(classes, row):
            key = PROBABILITY_KEYS.get(class_value)
            if key:
                mapped[key] = float(probability)
        return mapped

    def _fallback_probabilities(self, predicted_code) -> dict[str, float]:
        mapped = {"home_win": 0.0, "draw": 0.0, "away_win": 0.0}
        key = PROBABILITY_KEYS.get(predicted_code)
        if key:
            mapped[key] = 1.0
        return mapped

    def _rows_from_predictions(
        self,
        bundle: ModelBundle,
        predicted_goals: np.ndarray | None,
        predicted_codes,
        probabilities: list[dict[str, float] | None],
        stage1_predictions: pd.DataFrame | None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for index, predicted_code in enumerate(predicted_codes):
            label = RESULT_LABELS.get(predicted_code, str(predicted_code))
            stage1_row = self._stage1_prediction_row(stage1_predictions, index)
            row: dict[str, Any] = {
                "row_index": index,
                "predicted_total_goals": None if predicted_goals is None else float(predicted_goals[index]),
                "predicted_result_code": int(predicted_code) if isinstance(predicted_code, (np.integer, int)) else str(predicted_code),
                "predicted_result_label": label,
                "probabilities": probabilities[index] if probabilities else None,
                "stage1_predictions": stage1_row,
                "metadata": self._row_metadata(bundle),
            }
            rows.append(row)
        return rows

    def _stage1_prediction_row(self, stage1_predictions: pd.DataFrame | None, index: int) -> dict[str, float] | None:
        if stage1_predictions is None:
            return None
        row = stage1_predictions.iloc[index]
        return {column: float(row[column]) for column in stage1_predictions.columns}

    def _row_metadata(self, bundle: ModelBundle) -> dict[str, Any] | None:
        if not bundle.stage1_target_metric:
            return None
        return {"stage1_target_metric": bundle.stage1_target_metric}
