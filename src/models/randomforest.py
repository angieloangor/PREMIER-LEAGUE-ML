from __future__ import annotations

from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

from .base import ModelSpec


def get_model_specs() -> dict[str, ModelSpec]:
    return {
        "random_forest_regressor": ModelSpec(
            key="random_forest_regressor",
            stage="regression",
            family="random_forest",
            build_estimator=lambda: RandomForestRegressor(random_state=42, n_jobs=1),
            param_grid={
                "model__n_estimators": [200, 400, 600],
                "model__max_depth": [5, 8, 12, None],
                "model__min_samples_split": [2, 5, 10],
                "model__min_samples_leaf": [1, 2, 4, 8],
                "model__max_features": ["sqrt", "log2", 0.6, 0.8],
            },
            preprocessor="tree",
            description="Random forest regressor for total goals.",
        ),
        "random_forest_classifier": ModelSpec(
            key="random_forest_classifier",
            stage="classification",
            family="random_forest",
            build_estimator=lambda: RandomForestClassifier(
                random_state=42,
                n_jobs=1,
                class_weight="balanced_subsample",
            ),
            param_grid={
                "model__n_estimators": [200, 400, 600],
                "model__max_depth": [5, 8, 12, None],
                "model__min_samples_split": [2, 5, 10],
                "model__min_samples_leaf": [1, 2, 4, 8],
                "model__max_features": ["sqrt", "log2", 0.6, 0.8],
            },
            preprocessor="tree",
            description="Random forest classifier for match result.",
        ),
    }
