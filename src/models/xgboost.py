from __future__ import annotations

from .base import ModelSpec


def _build_xgb_regressor():
    from xgboost import XGBRegressor

    return XGBRegressor(
        objective="reg:squarederror",
        tree_method="hist",
        random_state=42,
        n_jobs=1,
    )


def _build_xgb_classifier():
    from xgboost import XGBClassifier

    return XGBClassifier(
        objective="multi:softprob",
        num_class=3,
        eval_metric="mlogloss",
        tree_method="hist",
        random_state=42,
        n_jobs=1,
    )


def get_model_specs() -> dict[str, ModelSpec]:
    common_grid = {
        "model__n_estimators": [200, 400, 600],
        "model__max_depth": [3, 4, 5, 7],
        "model__learning_rate": [0.02, 0.03, 0.05, 0.1],
        "model__subsample": [0.7, 0.85, 1.0],
        "model__colsample_bytree": [0.7, 0.85, 1.0],
        "model__min_child_weight": [1, 3, 5, 8],
        "model__gamma": [0.0, 0.1, 0.3],
        "model__reg_alpha": [0.0, 0.01, 0.1, 1.0],
        "model__reg_lambda": [0.5, 1.0, 2.0, 5.0],
    }
    return {
        "xgboost_regressor": ModelSpec(
            key="xgboost_regressor",
            stage="regression",
            family="xgboost",
            build_estimator=_build_xgb_regressor,
            param_grid=common_grid,
            preprocessor="tree",
            description="XGBoost regressor for total goals.",
        ),
        "xgboost_classifier": ModelSpec(
            key="xgboost_classifier",
            stage="classification",
            family="xgboost",
            build_estimator=_build_xgb_classifier,
            param_grid=common_grid,
            preprocessor="tree",
            description="XGBoost classifier for match result.",
        ),
    }
