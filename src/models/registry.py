from __future__ import annotations

from .base import ModelSpec
from .knn import get_model_specs as get_knn_specs
from .catboost import get_model_specs as get_catboost_specs
from .lightgbm import get_model_specs as get_lightgbm_specs
from .randomforest import get_model_specs as get_random_forest_specs
from .ridge_elasticnet import get_model_specs as get_linear_specs
from .torch_nn_model import get_model_specs as get_torch_specs
from .xgboost import get_model_specs as get_xgboost_specs


MODEL_REGISTRY: dict[str, ModelSpec] = {}
for builder in (
    get_linear_specs,
    get_knn_specs,
    get_random_forest_specs,
    get_xgboost_specs,
    get_catboost_specs,
    get_lightgbm_specs,
    get_torch_specs,
):
    MODEL_REGISTRY.update(builder())


def get_model_spec(name: str) -> ModelSpec:
    return MODEL_REGISTRY[name]


def list_models(stage: str | None = None) -> list[str]:
    if stage is None:
        return sorted(MODEL_REGISTRY)
    return sorted(name for name, spec in MODEL_REGISTRY.items() if spec.stage == stage)
