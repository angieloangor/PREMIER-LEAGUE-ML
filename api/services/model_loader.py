from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any

import joblib

from api.config import Settings
from src.models.select_best_model import rank_classifier_bundles

logger = logging.getLogger(__name__)


def _optional_torch_load(path: Path):
    try:
        import torch
    except ImportError as exc:  # pragma: no cover - depends on local environment
        raise RuntimeError("Torch artifact found but PyTorch is not installed.") from exc

    try:
        return torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:  # pragma: no cover - compatibility with older torch versions
        return torch.load(path, map_location="cpu")


def _iter_estimator_components(estimator, seen: set[int] | None = None):
    if seen is None:
        seen = set()
    object_id = id(estimator)
    if object_id in seen:
        return
    seen.add(object_id)
    yield estimator

    for _, step in getattr(estimator, "steps", []) or []:
        yield from _iter_estimator_components(step, seen)

    for transformer in getattr(estimator, "transformers", []) or []:
        if len(transformer) >= 2 and not isinstance(transformer[1], str):
            yield from _iter_estimator_components(transformer[1], seen)

    for child in getattr(estimator, "estimators", []) or []:
        if child is not None and not isinstance(child, str):
            yield from _iter_estimator_components(child, seen)

    for attribute in ("estimator", "base_estimator", "final_estimator"):
        child = getattr(estimator, attribute, None)
        if child is not None and not isinstance(child, str):
            yield from _iter_estimator_components(child, seen)


def _patch_loaded_estimator_compatibility(estimator):
    try:
        from sklearn.impute import SimpleImputer
    except Exception:
        return estimator

    for component in _iter_estimator_components(estimator):
        if isinstance(component, SimpleImputer) and not hasattr(component, "_fill_dtype"):
            fill_dtype = getattr(component, "_fit_dtype", None)
            if fill_dtype is None and hasattr(component, "statistics_"):
                fill_dtype = getattr(component.statistics_, "dtype", None)
            component._fill_dtype = fill_dtype or float
        if not hasattr(component, "classes_"):
            label_binarizer = getattr(component, "_label_binarizer", None)
            if label_binarizer is not None and hasattr(label_binarizer, "classes_"):
                component.classes_ = label_binarizer.classes_
    return estimator


def _extract_metric(summary: dict[str, Any], *path: str) -> float | None:
    current: Any = summary
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    if current is None:
        return None
    return float(current)


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


@dataclass
class ModelBundle:
    model_id: str
    display_name: str
    bundle_path: Path
    stage1_bundle_path: Path
    summary: dict[str, Any]
    regressor: Any
    classifier: Any
    stage1_model_name: str
    stage1_run_name: str
    stage1_target_metric: str | None
    stage1_generated_features: list[str]
    regressor_features: list[str]
    classifier_features: list[str]
    classifier_base_features: list[str]
    is_default: bool = False

    @property
    def metrics_preview(self) -> dict[str, float | None]:
        return {
            "stage2_cv_accuracy": _extract_metric(self.summary, "classifier", "cv_metrics", "mean_cv_accuracy"),
            "stage2_cv_f1_weighted": _extract_metric(self.summary, "classifier", "cv_metrics", "mean_cv_f1_weighted"),
            "stage2_test_accuracy": _extract_metric(self.summary, "classifier_metrics", "test", "accuracy")
            or _extract_metric(self.summary, "classifier_metrics", "accuracy"),
            "stage2_test_f1_weighted": _extract_metric(self.summary, "classifier_metrics", "test", "f1_weighted")
            or _extract_metric(self.summary, "classifier_metrics", "f1_weighted"),
            "stage1_cv_r2": _extract_metric(self.summary, "regressor", "cv_metrics", "mean_cv_r2")
            or _coerce_float((self.summary.get("generator_model") or {}).get("cv_r2")),
            "stage1_cv_rmse": _extract_metric(self.summary, "regressor", "cv_metrics", "mean_cv_rmse"),
            "stage1_test_r2": _extract_metric(self.summary, "regression_metrics", "test", "r2")
            or _coerce_float((self.summary.get("generator_model") or {}).get("test_r2")),
            "stage1_test_rmse": _extract_metric(self.summary, "regression_metrics", "test", "rmse")
            or _extract_metric(self.summary, "regression_metrics", "rmse"),
            "stage1_test_mae": _extract_metric(self.summary, "regression_metrics", "test", "mae")
            or _extract_metric(self.summary, "regression_metrics", "mae"),
        }

    @property
    def uses_stage1_prediction(self) -> bool:
        return bool(self.stage1_generated_features)

    @property
    def stage1_prediction_is_total_goals(self) -> bool:
        target_metric = (self.stage1_target_metric or "").lower()
        if not self.stage1_generated_features:
            return target_metric == "total_goals"
        if len(self.stage1_generated_features) != 1:
            return False
        feature_name = self.stage1_generated_features[0].lower()
        return feature_name == "stage1_pred_total_goals" or "total_goals" in feature_name or target_metric == "total_goals"


class ModelRegistryService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.bundles: dict[str, ModelBundle] = {}
        self.default_model_id: str | None = None

    def load(self) -> None:
        self.bundles = {}
        self.default_model_id = None
        ranked_entries = rank_classifier_bundles(
            runs_root=self.settings.runs_root,
            top_k=self.settings.top_k_models,
        )
        selected_dirs = [Path(entry["bundle_dir"]) for entry in ranked_entries]

        if not selected_dirs:
            logger.warning(
                "No ranked bundles found in %s. Falling back to artifact discovery under %s.",
                self.settings.runs_root,
                self.settings.outputs_dir,
            )
            candidate_dirs = self._discover_bundle_dirs()
            selected_dirs = self._rank_bundle_dirs(candidate_dirs)[: self.settings.top_k_models]

        for bundle_dir in selected_dirs:
            try:
                bundle = self._load_bundle(bundle_dir, is_default=self.default_model_id is None)
            except Exception as exc:
                logger.warning("Skipping model bundle %s: %s", bundle_dir, exc)
                continue
            self.bundles[bundle.model_id] = bundle
            if bundle.is_default:
                self.default_model_id = bundle.model_id

        logger.info(
            "Loaded %s model bundles from %s. Default=%s",
            len(self.bundles),
            self.settings.runs_root,
            self.default_model_id,
        )

    def list_models(self) -> list[ModelBundle]:
        return list(self.bundles.values())

    def get_bundle(self, model_id: str | None = None) -> ModelBundle:
        lookup_id = model_id or self.default_model_id
        if not lookup_id or lookup_id not in self.bundles:
            available = ", ".join(sorted(self.bundles))
            raise KeyError(f"Unknown model id '{lookup_id}'. Available models: {available}")
        return self.bundles[lookup_id]

    def load_bundle_from_dir(self, bundle_dir: Path, *, is_default: bool = False) -> ModelBundle:
        return self._load_bundle(bundle_dir, is_default=is_default)

    def _discover_bundle_dirs(self) -> list[Path]:
        discovered: list[Path] = []
        for summary_path in self.settings.outputs_dir.rglob("run_summary.json"):
            bundle_dir = summary_path.parent
            if self._has_model_artifacts(bundle_dir):
                discovered.append(bundle_dir)
        return discovered

    def _rank_bundle_dirs(self, bundle_dirs: list[Path]) -> list[Path]:
        def score(bundle_dir: Path) -> tuple[float, float, float]:
            summary = json.loads((bundle_dir / "run_summary.json").read_text(encoding="utf-8"))
            test_accuracy = (
                _extract_metric(summary, "classifier_metrics", "test", "accuracy")
                or _extract_metric(summary, "classifier_metrics", "accuracy")
                or -1.0
            )
            cv_accuracy = _extract_metric(summary, "classifier", "cv_metrics", "mean_cv_accuracy") or -1.0
            test_f1 = (
                _extract_metric(summary, "classifier_metrics", "test", "f1_weighted")
                or _extract_metric(summary, "classifier_metrics", "f1_weighted")
                or -1.0
            )
            return (test_accuracy, cv_accuracy, test_f1)

        return sorted(bundle_dirs, key=score, reverse=True)

    def _load_bundle(self, bundle_dir: Path, is_default: bool) -> ModelBundle:
        summary = json.loads((bundle_dir / "run_summary.json").read_text(encoding="utf-8"))
        classifier_path = self._find_artifact(bundle_dir, "classifier")
        classifier_summary = summary.get("classifier") or {}
        classifier_features = list(classifier_summary.get("feature_columns", []))

        if summary.get("generator_model"):
            generator_summary = summary["generator_model"]
            stage1_bundle_path = self._resolve_stage1_bundle_dir(bundle_dir, summary)
            regressor_path = self._find_artifact(stage1_bundle_path, "regressor")
            regressor_features = list(generator_summary.get("feature_columns", []))
            stage1_generated_features = list(generator_summary.get("generated_feature_columns", []))
            stage1_model_name = generator_summary.get("name") or stage1_bundle_path.name
            stage1_run_name = generator_summary.get("run_name") or stage1_bundle_path.name
            stage1_target_metric = generator_summary.get("target_metric") or summary.get("target_metric")
        else:
            regressor_summary = summary.get("regressor") or {}
            stage1_bundle_path = bundle_dir
            regressor_path = self._find_artifact(bundle_dir, "regressor")
            regressor_features = list(regressor_summary.get("feature_columns", []))
            stage1_generated_features = [column for column in classifier_features if column == "stage1_pred_total_goals"]
            stage1_model_name = regressor_summary.get("name") or "regressor"
            stage1_run_name = summary.get("run_name") or bundle_dir.name
            target_columns = regressor_summary.get("target_columns") or []
            stage1_target_metric = target_columns[0] if target_columns else None

        regressor = self._load_estimator(regressor_path)
        classifier = self._load_estimator(classifier_path)

        model_id = summary.get("run_name") or bundle_dir.name
        generated_feature_set = set(stage1_generated_features)
        classifier_base_features = [column for column in classifier_features if column not in generated_feature_set]
        return ModelBundle(
            model_id=model_id,
            display_name=bundle_dir.name,
            bundle_path=bundle_dir,
            stage1_bundle_path=stage1_bundle_path,
            summary=summary,
            regressor=regressor,
            classifier=classifier,
            stage1_model_name=stage1_model_name,
            stage1_run_name=stage1_run_name,
            stage1_target_metric=stage1_target_metric,
            stage1_generated_features=stage1_generated_features,
            regressor_features=regressor_features,
            classifier_features=classifier_features,
            classifier_base_features=classifier_base_features,
            is_default=is_default,
        )

    def _resolve_stage1_bundle_dir(self, bundle_dir: Path, summary: dict[str, Any]) -> Path:
        generator_summary = summary.get("generator_model") or {}
        target_metric = generator_summary.get("target_metric") or summary.get("target_metric")
        run_name = generator_summary.get("run_name")
        stage1_root = bundle_dir.parent.parent / "stage1_feature_generators"

        candidates: list[Path] = []
        if target_metric and run_name:
            candidates.append(stage1_root / str(target_metric) / str(run_name))

        hinted_artifact_path = self._resolve_portable_artifact_hint(generator_summary.get("artifact_path"))
        if hinted_artifact_path is not None:
            candidates.append(hinted_artifact_path.parent)

        if run_name:
            candidates.extend(stage1_root.glob(f"**/{run_name}"))

        seen: set[Path] = set()
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            if self._artifact_exists(candidate, "regressor"):
                return candidate

        raise FileNotFoundError(
            f"Could not resolve stage1 bundle for {bundle_dir.name}. "
            f"target_metric={target_metric!r}, run_name={run_name!r}"
        )

    def _resolve_portable_artifact_hint(self, raw_path: str | None) -> Path | None:
        if not raw_path:
            return None

        direct_path = Path(raw_path)
        if direct_path.exists():
            return direct_path

        parts_candidates = [direct_path.parts, PureWindowsPath(raw_path).parts]
        for parts in parts_candidates:
            normalized = [part.lower().rstrip("\\/") for part in parts]
            if "outputs" not in normalized:
                continue
            outputs_index = normalized.index("outputs")
            candidate = self.settings.project_root.joinpath(*parts[outputs_index:])
            if candidate.exists():
                return candidate
        return None

    def _find_artifact(self, bundle_dir: Path, stem: str) -> Path:
        for extension in (".joblib", ".pt"):
            candidate = bundle_dir / f"{stem}{extension}"
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"Could not find artifact '{stem}' in {bundle_dir}")

    def _load_estimator(self, artifact_path: Path):
        if artifact_path.suffix == ".joblib":
            return _patch_loaded_estimator_compatibility(joblib.load(artifact_path))
        if artifact_path.suffix == ".pt":
            return _patch_loaded_estimator_compatibility(_optional_torch_load(artifact_path))
        raise ValueError(f"Unsupported artifact extension: {artifact_path.suffix}")

    def _has_model_artifacts(self, bundle_dir: Path) -> bool:
        summary_path = bundle_dir / "run_summary.json"
        if not summary_path.exists():
            return False
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False
        return bool(summary.get("classifier")) and self._artifact_exists(bundle_dir, "classifier")

    def _artifact_exists(self, bundle_dir: Path, stem: str) -> bool:
        return any((bundle_dir / f"{stem}{ext}").exists() for ext in (".joblib", ".pt"))
