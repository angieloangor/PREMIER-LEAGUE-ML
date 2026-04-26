from __future__ import annotations

from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor

from .base import ModelSpec


def get_model_specs() -> dict[str, ModelSpec]:
    common_grid = {
        "model__n_neighbors": [3, 5, 7, 11, 15],
        "model__weights": ["uniform", "distance"],
        "model__p": [1, 2],
    }
    return {
        "knn_regressor": ModelSpec(
            key="knn_regressor",
            stage="regression",
            family="knn",
            build_estimator=lambda: KNeighborsRegressor(),
            param_grid=common_grid,
            preprocessor="linear",
            description="KNN regressor baseline for feature approximation or total goals.",
        ),
        "knn_classifier": ModelSpec(
            key="knn_classifier",
            stage="classification",
            family="knn",
            build_estimator=lambda: KNeighborsClassifier(),
            param_grid=common_grid,
            preprocessor="linear",
            description="KNN classifier baseline for match result.",
        ),
    }
