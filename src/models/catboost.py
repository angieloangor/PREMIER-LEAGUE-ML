from __future__ import annotations

from .base import ModelSpec


def _build_catboost_regressor():
    from catboost import CatBoostRegressor

    return CatBoostRegressor(
        random_state=42,
        verbose=0,
        allow_writing_files=False,
    )


def _build_catboost_classifier():
    from catboost import CatBoostClassifier

    return CatBoostClassifier(
        random_state=42,
        verbose=0,
        allow_writing_files=False,
        loss_function="MultiClass",
    )


def get_model_specs() -> dict[str, ModelSpec]:
    common_grid = {
        "model__depth": [4, 6, 8, 10],
        "model__learning_rate": [0.02, 0.03, 0.05, 0.1],
        "model__iterations": [200, 400, 600],
        "model__l2_leaf_reg": [2, 3, 5, 7, 10],
        "model__random_strength": [0.0, 0.5, 1.0],
        "model__bagging_temperature": [0.0, 0.5, 1.0],
    }
    return {
        "catboost_regressor": ModelSpec(
            key="catboost_regressor",
            stage="regression",
            family="catboost",
            build_estimator=_build_catboost_regressor,
            param_grid=common_grid,
            preprocessor="tree",
            description="CatBoost regressor for total goals.",
        ),
        "catboost_classifier": ModelSpec(
            key="catboost_classifier",
            stage="classification",
            family="catboost",
            build_estimator=_build_catboost_classifier,
            param_grid=common_grid,
            preprocessor="tree",
            description="CatBoost classifier for match result.",
        ),
    }
