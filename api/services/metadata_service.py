from __future__ import annotations

from api.services.model_loader import ModelRegistryService


class MetadataService:
    def __init__(self, registry: ModelRegistryService) -> None:
        self.registry = registry

    def _display_name(self, bundle) -> str:
        target_metric = bundle.stage1_target_metric or "stage1"
        feature_mode = bundle.summary.get("feature_mode") or "default"
        classifier_name = bundle.summary["classifier"]["name"]
        return f"{target_metric} | {bundle.stage1_model_name} -> {classifier_name} | {feature_mode}"

    def _serialize_model_summary(self, bundle) -> dict:
        return {
            "id": bundle.model_id,
            "name": self._display_name(bundle),
            "default": bundle.is_default,
            "feature_mode": bundle.summary.get("feature_mode"),
            "stages": {
                "stage_1_regressor": bundle.stage1_model_name,
                "stage_1_target_metric": bundle.stage1_target_metric,
                "stage_2_classifier": bundle.summary["classifier"]["name"],
            },
            "performance": bundle.metrics_preview,
        }

    def _serialize_model_variables(self, bundle) -> dict:
        return {
            "id": bundle.model_id,
            "name": self._display_name(bundle),
            "stages": {
                "stage_1_regressor": bundle.stage1_model_name,
                "stage_1_target_metric": bundle.stage1_target_metric,
                "stage_2_classifier": bundle.summary["classifier"]["name"],
            },
            "default": bundle.is_default,
            "variables": {
                "feature_mode": bundle.summary.get("feature_mode"),
                "stage1_input_features": bundle.regressor_features,
                "stage2_base_features": bundle.classifier_base_features,
                "stage2_generated_features": bundle.stage1_generated_features,
                "stage2_features": bundle.classifier_features,
            },
        }

    def list_models(self) -> list[dict]:
        return [self._serialize_model_summary(bundle) for bundle in self.registry.list_models()]

    def get_model(self, model_id: str | None = None) -> dict:
        bundle = self.registry.get_bundle(model_id)
        return self._serialize_model_summary(bundle)

    def list_model_variables(self) -> list[dict]:
        return [self._serialize_model_variables(bundle) for bundle in self.registry.list_models()]

    def get_model_variables(self, model_id: str | None = None) -> dict:
        bundle = self.registry.get_bundle(model_id)
        return self._serialize_model_variables(bundle)
