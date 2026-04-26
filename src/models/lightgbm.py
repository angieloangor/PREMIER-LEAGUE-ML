from __future__ import annotations

from .base import ModelSpec


def _build_lightgbm_regressor():
    from lightgbm import LGBMRegressor

    return LGBMRegressor(
        random_state=42,
        verbosity=-1,
        n_jobs=1,
    )


def _build_lightgbm_classifier():
    from lightgbm import LGBMClassifier

    return LGBMClassifier(
        random_state=42,
        verbosity=-1,
        n_jobs=1,
        objective="multiclass",
        num_class=3,
    )


def get_model_specs() -> dict[str, ModelSpec]:
    common_grid = {
        "model__n_estimators": [200, 400, 600],
        "model__learning_rate": [0.02, 0.03, 0.05, 0.1],
        "model__num_leaves": [15, 31, 63, 127],
        "model__max_depth": [-1, 4, 6, 8, 10],
        "model__subsample": [0.7, 0.85, 1.0],
        "model__colsample_bytree": [0.7, 0.85, 1.0],
        "model__min_child_samples": [10, 20, 40],
        "model__reg_alpha": [0.0, 0.01, 0.1, 1.0],
        "model__reg_lambda": [0.0, 0.1, 1.0, 5.0],
    }
    return {
        "lightgbm_regressor": ModelSpec(
            key="lightgbm_regressor",
            stage="regression",
            family="lightgbm",
            build_estimator=_build_lightgbm_regressor,
            param_grid=common_grid,
            preprocessor="tree",
            description="LightGBM regressor for total goals.",
        ),
        "lightgbm_classifier": ModelSpec(
            key="lightgbm_classifier",
            stage="classification",
            family="lightgbm",
            build_estimator=_build_lightgbm_classifier,
            param_grid=common_grid,
            preprocessor="tree",
            description="LightGBM classifier for match result.",
        ),
    }
